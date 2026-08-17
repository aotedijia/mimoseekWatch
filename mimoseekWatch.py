from __future__ import annotations

import json
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn
import webview

from mimoseekwatch.main import DATA_DIR, DB, app
from mimoseekwatch.usage_import import parse_usage_export


def install_automatic_downloads(on_finished=None) -> None:
    """Save WebView2 downloads locally and import recognized usage exports."""
    from webview.platforms.edgechromium import EdgeChrome

    download_dir = DATA_DIR / "usage-sync"
    download_dir.mkdir(parents=True, exist_ok=True)

    def on_download_starting(self, sender, args):
        # WebView2 asks "allow multiple downloads?" per session the second time a
        # download is started. In a hidden background window nobody can answer that
        # prompt, so repeated 5-minute auto-exports stall with no file. Marking the
        # event handled suppresses the prompt while keeping the batch download.
        try:
            args.Handled = True
        except Exception:
            pass
        original_name = Path(str(args.ResultFilePath)).name or "usage.zip"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = download_dir / f"{stamp}-{original_name}"
        args.ResultFilePath = str(target)
        operation = args.DownloadOperation

        def state_changed(download, _event_args):
            if "Completed" not in str(download.State):
                return

            def import_file() -> None:
                for _ in range(20):
                    if target.exists() and target.stat().st_size > 0:
                        break
                    time.sleep(0.25)
                try:
                    records = parse_usage_export(target.name, target.read_bytes())
                    DB.replace_provider_usage("deepseek", records)
                    DB.set_settings({"last_web_import": f"{datetime.now().isoformat(timespec='seconds')}|{len(records)}"})
                    if on_finished:
                        on_finished(True, len(records), "")
                except Exception as exc:
                    DB.set_settings({"last_web_import_error": str(exc)[:300]})
                    if on_finished:
                        on_finished(False, 0, str(exc)[:300])

            threading.Thread(target=import_file, name="usage-import", daemon=True).start()

        operation.StateChanged += state_changed

    EdgeChrome.on_download_starting = on_download_starting


class DesktopAPI:
    def __init__(self) -> None:
        self.login_windows: dict[str, webview.Window] = {}
        self.sync_lock = threading.Lock()
        self.sync_in_progress = False
        self.last_sync_attempt = 0.0
        self.mimo_sync_lock = threading.Lock()
        self.mimo_sync_in_progress = False
        self.mimo_last_sync_attempt = 0.0
        self.stop_event = threading.Event()
        self.manually_opened: set[str] = set()

    def attach_provider_window(self, provider: str, window: webview.Window) -> None:
        self.login_windows[provider] = window
        window.events.loaded += lambda: self._provider_page_loaded(provider)
        window.events.closed += lambda: self._provider_window_closed(provider, window)
        threading.Thread(
            target=self._monitor_provider_window,
            args=(provider, window),
            name=f"{provider}-login-monitor",
            daemon=True,
        ).start()

    def _provider_window_closed(self, provider: str, window: webview.Window) -> None:
        if self.login_windows.get(provider) is window:
            self.login_windows.pop(provider, None)
        self.manually_opened.discard(provider)

    def _monitor_provider_window(self, provider: str, window: webview.Window) -> None:
        """Detect login redirects that do not reliably emit WebView loaded."""
        last_url = ""
        while not self.stop_event.wait(2):
            if self.login_windows.get(provider) is not window:
                return
            try:
                url = window.get_current_url() or ""
            except Exception:
                continue
            if url and url != last_url:
                last_url = url
                self._provider_page_loaded(provider)

    def _provider_page_loaded(self, provider: str) -> None:
        window = self.login_windows.get(provider)
        if not window:
            return
        try:
            url = window.get_current_url() or ""
        except Exception:
            return
        if provider == "deepseek" and "/usage" in url:
            DB.set_settings({
                "web_login_status": "正在同步余额和用量",
                "web_balance_status": "正在同步余额和用量",
            })
            threading.Thread(
                target=self._auto_export_deepseek,
                args=(window,),
                name="deepseek-auto-export",
                daemon=True,
            ).start()
        elif provider == "deepseek" and ("sign_in" in url or "login" in url):
            DB.set_settings({
                "web_login_status": "等待网页登录后同步",
                "web_balance_status": "等待网页登录后同步",
            })
        elif provider == "mimo" and "platform.xiaomimimo.com" in url and "/console/" in url:
            DB.set_settings({"mimo_web_status": "正在同步余额和用量"})
            threading.Thread(
                target=self._auto_sync_mimo,
                args=(window,),
                name="mimo-auto-sync",
                daemon=True,
            ).start()
        elif provider == "mimo":
            DB.set_settings({"mimo_web_status": "等待网页登录后同步"})

    def _auto_export_deepseek(self, window: webview.Window) -> None:
        with self.sync_lock:
            elapsed = time.monotonic() - self.last_sync_attempt
            if self.sync_in_progress and elapsed < 45:
                return
            # Recover from a missed download callback or timer. Without this,
            # one stale flag would block every later five-minute sync.
            if self.sync_in_progress:
                self.sync_in_progress = False
            if elapsed < 20:
                return
            self.sync_in_progress = True
            self.last_sync_attempt = time.monotonic()
        try:
            time.sleep(1.2)
            state = window.evaluate_js(r"""
            (() => {
              const visible = (el) => {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
              };
              const text = (el) => (el.innerText || el.textContent || el.getAttribute?.('aria-label') || '').replace(/\s+/g, ' ').trim();
              const nodes = [...document.querySelectorAll('button, [role="button"], [aria-haspopup], [tabindex]')].filter(visible);
              const needsLogin = !!document.querySelector('input[type="password"]') || /sign_in|login/i.test(location.href);
              if (needsLogin) return { needsLogin: true };
              const hasThirtyDays = nodes.some(el => /^(近|最近)\s*30\s*天$|^last\s*30\s*days?$/i.test(text(el)));
              if (hasThirtyDays) return { ready: true };
              const range = nodes.find(el => /时间维度|时间范围|time range|date range/i.test(text(el)))
                || nodes.find(el => el.hasAttribute('aria-haspopup') && /近7天|近30天|last 7|last 30/i.test(text(el)));
              if (range) { range.click(); return { openedRange: true }; }
              return { ready: true };
            })();
            """) or {}
            if state.get("needsLogin"):
                DB.set_settings({"web_login_status": "登录已失效，请重新登录 DeepSeek"})
                self.sync_in_progress = False
                return
            self._refresh_deepseek_balance(window)
            if state.get("openedRange"):
                time.sleep(0.6)
                window.evaluate_js(r"""
                (() => {
                  const visible = (el) => { const r=el.getBoundingClientRect(),s=getComputedStyle(el); return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'; };
                  const nodes=[...document.querySelectorAll('button,[role="option"],[role="menuitem"],li,div,span')].filter(visible);
                  const option=nodes.find(el => /^(近|最近)\s*30\s*天$|^last\s*30\s*days?$/i.test((el.innerText||el.textContent||'').replace(/\s+/g,' ').trim()));
                  if (!option) return false;
                  (option.closest('button,[role="option"],[role="menuitem"],li')||option).click();
                  return true;
                })();
                """)
                time.sleep(1.2)

            clicked = False
            for _ in range(5):
                result = window.evaluate_js(r"""
                (() => {
                  const visible=(el)=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden';};
                  const nodes=[...document.querySelectorAll('button,[role="button"],a')].filter(visible);
                  const button=nodes.find(el => /^(导出|export)$/i.test((el.innerText||el.textContent||'').replace(/\s+/g,' ').trim()));
                  if (!button) return false;
                  button.scrollIntoView({block:'center'}); button.click(); return true;
                })();
                """)
                if result:
                    clicked = True
                    break
                time.sleep(1)
            if clicked:
                DB.set_settings({"web_login_status": "已登录，等待官方用量下载"})
                threading.Timer(35, self._release_sync).start()
            else:
                DB.set_settings({"web_login_status": "已登录，但没有找到用量导出按钮"})
                self.sync_in_progress = False
        except Exception as exc:
            DB.set_settings({"web_login_status": f"自动同步失败：{str(exc)[:160]}"})
            self.sync_in_progress = False

    def _refresh_deepseek_balance(self, window: webview.Window) -> bool:
        """Read the official wallet summary using the WebView's saved session Cookie."""
        try:
            response = window.evaluate_js(r"""
            (() => {
              const tokenValues = [];
              const collect = (value) => {
                if (typeof value === 'string') {
                  if (value.length > 20) tokenValues.push(value);
                  try { collect(JSON.parse(value)); } catch {}
                } else if (value && typeof value === 'object') {
                  Object.values(value).forEach(collect);
                }
              };
              for (const storage of [localStorage, sessionStorage]) {
                for (let i = 0; i < storage.length; i += 1) {
                  const key = storage.key(i) || '';
                  if (/user.?token|auth.?token|access.?token/i.test(key)) collect(storage.getItem(key));
                }
              }
              const attempts = [null, ...new Set(tokenValues)];
              let last = { status: 0, body: '' };
              try {
                for (const token of attempts) {
                  const request = new XMLHttpRequest();
                  request.open('GET', '/api/v0/users/get_user_summary', false);
                  request.withCredentials = true;
                  request.setRequestHeader('Accept', 'application/json');
                  if (token) request.setRequestHeader('Authorization', `Bearer ${token}`);
                  request.send(null);
                  last = { status: request.status, body: request.responseText };
                  try {
                    const parsed = JSON.parse(request.responseText || '{}');
                    if (request.status === 200 && parsed?.data?.biz_data) return last;
                  } catch {}
                }
                return last;
              } catch (error) {
                return { status: 0, error: String(error) };
              }
            })();
            """) or {}
            if int(response.get("status") or 0) != 200:
                raise ValueError(response.get("error") or f"网页余额接口返回 {response.get('status')}")
            payload = json.loads(response.get("body") or "{}")
            data = payload.get("data") or {}
            summary = data.get("biz_data") or {}
            if not summary:
                raise ValueError(data.get("biz_msg") or payload.get("msg") or "网页余额接口没有返回账户数据")
            normal = summary.get("normal_wallets") or []
            bonus = summary.get("bonus_wallets") or []
            currencies = [str(item.get("currency") or "").upper() for item in normal + bonus]
            currency = "CNY" if "CNY" in currencies else (currencies[0] if currencies else "CNY")
            topped_up = sum(float(item.get("balance") or 0) for item in normal if str(item.get("currency") or "").upper() == currency)
            granted = sum(float(item.get("balance") or 0) for item in bonus if str(item.get("currency") or "").upper() == currency)
            DB.upsert_balance({
                "provider": "deepseek", "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "total_balance": topped_up + granted, "granted_balance": granted,
                "topped_up_balance": topped_up, "currency": currency, "available": 1,
                "source": "official_web_session", "error": None,
            })
            DB.set_settings({"web_balance_status": "DeepSeek 网页余额已更新"})
            return True
        except Exception as exc:
            DB.set_settings({"web_balance_status": f"网页余额读取失败：{str(exc)[:180]}"})
            return False

    def _release_sync(self) -> None:
        self.sync_in_progress = False

    @staticmethod
    def _unwrap_web_data(payload):
        current = payload
        for _ in range(5):
            if isinstance(current, dict):
                if "data" in current:
                    current = current["data"]
                    continue
                if "result" in current:
                    current = current["result"]
                    continue
            break
        return current

    def _mimo_web_request(self, window: webview.Window, method: str, path: str, body=None):
        method_json = json.dumps(method)
        path_json = json.dumps(f"/api/v1{path}")
        body_json = json.dumps(body, ensure_ascii=False) if body is not None else "null"
        script = f"""
        (() => {{
          try {{
            const method = {method_json}.toUpperCase();
            let url = {path_json};
            if (method === 'POST') {{
              const prefix = encodeURIComponent('api-platform_ph') + '=';
              const cookie = document.cookie.split('; ').find((item) => item.startsWith(prefix));
              const ph = cookie ? decodeURIComponent(cookie.slice(prefix.length)).replace(/^\"|\"$/g, '').trim() : '';
              if (ph) {{
                const query = new URLSearchParams({{ 'api-platform_ph': ph }});
                url += (url.includes('?') ? '&' : '?') + query.toString();
              }}
            }}
            const request = new XMLHttpRequest();
            request.open(method, url, false);
            request.withCredentials = true;
            request.setRequestHeader('Accept', 'application/json');
            request.setRequestHeader('Accept-Language', localStorage.getItem('user_language_preference') || 'zh');
            request.setRequestHeader('x-timeZone', Intl.DateTimeFormat().resolvedOptions().timeZone);
            request.setRequestHeader('Content-Type', 'application/json');
            request.send({body_json} === null ? null : JSON.stringify({body_json}));
            return {{ status: request.status, body: request.responseText }};
          }} catch (error) {{
            return {{ status: 0, error: String(error) }};
          }}
        }})();
        """
        response = {}
        for attempt in range(3):
            response = window.evaluate_js(script) or {}
            if isinstance(response, dict) and int(response.get("status") or 0) != 0:
                break
            if attempt < 2:
                time.sleep(1)
        if not isinstance(response, dict):
            raise ValueError(f"MiMo 网页接口 {path} 未返回有效响应")
        if int(response.get("status") or 0) != 200:
            raise ValueError(response.get("error") or f"MiMo 网页接口 {path} 返回 {response.get('status')}")
        payload = json.loads(response.get("body") or "{}")
        code = payload.get("code") if isinstance(payload, dict) else None
        if code not in (None, 0, 200, "0", "200"):
            raise ValueError(str(payload.get("message") or payload.get("msg") or f"业务错误 {code}"))
        return self._unwrap_web_data(payload)

    def _read_mimo_usage_summary(self, window: webview.Window) -> dict:
        # WebView2 throttles layout for a fully hidden window. Render it off-screen
        # briefly so the official React summary cards are mounted and readable.
        window.move(-16000, -16000)
        window.show()
        time.sleep(2)
        script = r"""
        (() => {
          const text = document.body ? document.body.innerText : '';
          const read = (...patterns) => {
            const match = patterns.map((pattern) => text.match(pattern)).find(Boolean);
            return match ? Number(match[1].replaceAll(',', '')) : null;
          };
          return {
            cost: read(
              /累计消费\s*[¥￥$]\s*([\d,]+(?:\.\d+)?)/i,
              /Cumulative Consumption\s*[¥￥$]\s*([\d,]+(?:\.\d+)?)/i
            ),
            cached_tokens: read(
              /输入[（(]命中缓存[）)]\s*Token\s*([\d,]+)/i,
              /Input \(Cache Hit\) Token\s*([\d,]+)/i
            ),
            uncached_tokens: read(
              /输入[（(]未命中缓存[）)]\s*Token\s*([\d,]+)/i,
              /Input \(Cache Miss\) Token\s*([\d,]+)/i
            ),
            page_url: location.href,
            text_length: text.length,
            language: document.documentElement.lang || ''
          };
        })();
        """
        summary = {}
        for _attempt in range(20):
            summary = window.evaluate_js(script) or {}
            required = ("cost", "cached_tokens", "uncached_tokens")
            if isinstance(summary, dict) and all(summary.get(key) is not None for key in required):
                return summary
            time.sleep(1)
        detail = ""
        if isinstance(summary, dict):
            detail = (
                f"（页面字符 {summary.get('text_length', 0)}，"
                f"语言 {summary.get('language') or '未知'}）"
            )
        raise ValueError(f"MiMo 用量页面顶部累计数据尚未加载{detail}")

    def _auto_sync_mimo(self, window: webview.Window) -> None:
        with self.mimo_sync_lock:
            elapsed = time.monotonic() - self.mimo_last_sync_attempt
            if self.mimo_sync_in_progress and elapsed < 90:
                return
            # A WebView request can occasionally fail to return. Recover the
            # stale flag so later five-minute sync cycles are not blocked.
            if self.mimo_sync_in_progress:
                self.mimo_sync_in_progress = False
            if elapsed < 20:
                return
            self.mimo_sync_in_progress = True
            self.mimo_last_sync_attempt = time.monotonic()
        try:
            time.sleep(1.5)
            balance = self._mimo_web_request(window, "GET", "/balance")
            if not isinstance(balance, dict) or balance.get("balance") is None:
                raise ValueError("MiMo 余额接口没有返回账户数据")
            currency = str(balance.get("currency") or "CNY").upper()
            DB.upsert_balance({
                "provider": "mimo", "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "total_balance": float(balance.get("balance") or 0),
                "granted_balance": float(balance.get("giftBalance") or 0),
                "topped_up_balance": float(balance.get("cashBalance") or 0),
                "currency": currency, "available": 1, "source": "official_web_session", "error": None,
            })

            today_utc = datetime.now(timezone.utc).date()
            previous_month = today_utc.replace(day=1) - timedelta(days=1)
            usage_rows = []
            for period in (today_utc, previous_month):
                period_rows = self._mimo_web_request(window, "POST", "/usage/detail/list", {
                    "year": period.year,
                    "month": period.month,
                })
                if isinstance(period_rows, dict):
                    period_rows = (
                        period_rows.get("list") or period_rows.get("records")
                        or period_rows.get("items") or []
                    )
                if not isinstance(period_rows, list):
                    raise ValueError("MiMo 月度用量接口返回格式无法识别")
                usage_rows.extend(period_rows)
            first_day = today_utc - timedelta(days=29)
            recent_rows = []
            for row in usage_rows:
                if not isinstance(row, dict):
                    continue
                try:
                    usage_day = datetime.fromisoformat(str(row.get("date") or "")[:10]).date()
                except ValueError:
                    continue
                if first_day <= usage_day <= today_utc:
                    recent_rows.append(row)
            daily_models = {}
            for row in recent_rows:
                date = str(row.get("date") or "")[:10]
                model = str(row.get("model") or "unknown")
                key = (date, model)
                item = daily_models.setdefault(key, {
                    "cached": 0, "uncached": 0, "output": 0,
                    "cost": 0.0, "requests": 0,
                })
                item["cached"] += int(row.get("inputHitToken") or 0)
                item["uncached"] += int(row.get("inputMissToken") or 0)
                item["output"] += int(row.get("outputToken") or 0)
                item["cost"] += float(row.get("consumedAmount") or 0)
                item["requests"] += int(row.get("requestCount") or 0)
            mimo_records = []
            for (date, model), item in sorted(daily_models.items()):
                input_tokens = item["cached"] + item["uncached"]
                mimo_records.append({
                    "created_at": f"{date}T12:00:00+00:00",
                    "provider": "mimo",
                    "model": model,
                    "endpoint": "sync:web-console",
                    "status_code": 200,
                    "latency_ms": 0,
                    "input_tokens": input_tokens,
                    "cached_tokens": item["cached"],
                    "uncached_tokens": item["uncached"],
                    "output_tokens": item["output"],
                    "total_tokens": input_tokens + item["output"],
                    "cost": item["cost"],
                    "currency": currency,
                    "priced": 1,
                    "request_count": item["requests"],
                    "source_id": f"mimo-official:{date}:{model}:{currency}",
                })
            DB.replace_provider_usage("mimo", mimo_records)
            stamp = datetime.now().isoformat(timespec="seconds")
            DB.set_settings({
                "mimo_last_sync": f"{stamp}|1",
                "mimo_last_error": "",
                "mimo_web_status": "近30天数据已更新",
            })
            if "mimo" not in self.manually_opened:
                try:
                    window.hide()
                except Exception:
                    pass
        except Exception as exc:
            DB.set_settings({
                "mimo_last_error": str(exc)[:300],
                "mimo_web_status": f"自动同步失败：{str(exc)[:160]}",
            })
        finally:
            self.mimo_last_sync_attempt = time.monotonic()
            self.mimo_sync_in_progress = False
            try:
                window.hide()
            except Exception:
                pass

    def on_usage_imported(self, ok: bool, count: int, error: str) -> None:
        self.sync_in_progress = False
        if ok:
            DB.set_settings({
                "web_login_status": f"DeepSeek 已登录，已自动同步 {count} 条官方用量",
                "last_web_import_error": "",
            })
            window = self.login_windows.get("deepseek")
            if window and "deepseek" not in self.manually_opened:
                try:
                    window.hide()
                except Exception:
                    pass
        else:
            DB.set_settings({"web_login_status": f"自动导入失败：{error}"})

    def start_periodic_sync(self) -> None:
        def loop() -> None:
            while not self.stop_event.wait(300):
                self.request_deepseek_sync(show_login=False)
                self.request_mimo_sync(show_login=False)
        threading.Thread(target=loop, name="deepseek-periodic-sync", daemon=True).start()

    def request_deepseek_sync(self, show_login: bool) -> dict:
        window = self.login_windows.get("deepseek")
        if not window:
            return {"ok": False, "error": "后台登录窗口尚未初始化"}
        try:
            current_url = window.get_current_url() or ""
            if "platform.deepseek.com" in current_url and "/usage" in current_url:
                # The hidden WebView normally remains on Usage. Export from
                # the already-loaded page instead of navigating to the same
                # URL again, which WebView2 does not reload reliably.
                threading.Thread(
                    target=self._auto_export_deepseek,
                    args=(window,),
                    name="deepseek-requested-export",
                    daemon=True,
                ).start()
            else:
                window.load_url("https://platform.deepseek.com/usage")
                # The loaded event performs the normal export. Keep a delayed
                # fallback for redirects and cached navigations.
                threading.Timer(2.0, self._auto_export_deepseek, args=(window,)).start()
            if show_login:
                window.show()
            return {"ok": True, "message": "正在使用已保存的登录状态自动同步"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def request_mimo_sync(self, show_login: bool) -> dict:
        window = self.login_windows.get("mimo")
        if not window:
            return {"ok": False, "error": "MiMo 后台登录窗口尚未初始化"}
        try:
            current_url = window.get_current_url() or ""
            if "platform.xiaomimimo.com" in current_url and "/console/" in current_url:
                # As with DeepSeek, navigating a hidden WebView to its current
                # URL does not reliably fire loaded. Sync from the active
                # authenticated page instead.
                threading.Thread(
                    target=self._auto_sync_mimo,
                    args=(window,),
                    name="mimo-requested-sync",
                    daemon=True,
                ).start()
            else:
                window.load_url("https://platform.xiaomimimo.com/console/usage")
            if show_login:
                window.move(120, 80)
                window.show()
            return {"ok": True, "message": "正在使用 MiMo 登录状态同步余额和用量"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def open_provider_login(self, provider: str) -> dict:
        targets = {
            "deepseek": ("DeepSeek 登录与用量", "https://platform.deepseek.com/usage"),
            "mimo": ("MiMo 登录与用量", "https://platform.xiaomimimo.com/console/usage"),
        }
        if provider not in targets:
            return {"ok": False, "error": "未知平台"}
        title, url = targets[provider]
        existing = self.login_windows.get(provider)
        if existing:
            try:
                self.manually_opened.add(provider)
                if provider == "mimo":
                    existing.move(120, 80)
                existing.show()
                return {"ok": True}
            except Exception:
                self.login_windows.pop(provider, None)
                self.manually_opened.discard(provider)

        window = webview.create_window(
            title, url, width=1000, height=720, min_size=(760, 520),
            background_color="#ffffff", text_select=True,
        )
        if window is None:
            return {"ok": False, "error": "无法创建登录窗口"}
        self.manually_opened.add(provider)
        self.attach_provider_window(provider, window)
        return {"ok": True}

    def shutdown(self) -> None:
        self.stop_event.set()
        for window in list(self.login_windows.values()):
            try:
                window.destroy()
            except Exception:
                pass


def free_port(preferred: int = 8765) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])


def wait_until_ready(port: int) -> None:
    for _ in range(100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError("mimoseekWatch 本地服务启动超时")


def main() -> None:
    port = free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(target=server.run, name="mimoseekwatch-server", daemon=True)
    thread.start()
    wait_until_ready(port)

    desktop_api = DesktopAPI()
    webview.settings["ALLOW_DOWNLOADS"] = True
    install_automatic_downloads(desktop_api.on_usage_imported)
    window = webview.create_window(
        "mimoseekWatch · 本地模型账本",
        f"http://127.0.0.1:{port}",
        js_api=desktop_api,
        width=960,
        height=680,
        min_size=(720, 520),
        background_color="#f4f5f8",
    )
    deepseek_window = webview.create_window(
        "DeepSeek 登录与自动同步", "https://platform.deepseek.com/usage",
        width=1000, height=720, min_size=(760, 520), hidden=True,
        background_color="#ffffff", text_select=True,
    )
    desktop_api.attach_provider_window("deepseek", deepseek_window)
    mimo_window = webview.create_window(
        "MiMo 登录与自动同步", "https://platform.xiaomimimo.com/console/usage",
        width=1000, height=720, min_size=(760, 520), hidden=True,
        background_color="#ffffff", text_select=True,
    )
    desktop_api.attach_provider_window("mimo", mimo_window)
    desktop_api.start_periodic_sync()
    def close_app() -> None:
        setattr(server, "should_exit", True)
        desktop_api.shutdown()
    window.events.closed += close_app
    storage_path = DATA_DIR / "webview"
    storage_path.mkdir(parents=True, exist_ok=True)
    webview.start(debug=False, private_mode=False, storage_path=str(storage_path))
    server.should_exit = True
    thread.join(timeout=3)


if __name__ == "__main__":
    main()

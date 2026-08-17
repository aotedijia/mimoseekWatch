const $ = (id) => document.getElementById(id);
let state = null;

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

const number = (value) => new Intl.NumberFormat("zh-CN", { notation: value >= 1_000_000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value || 0);
const money = (value) => `¥${Number(value || 0).toFixed(value >= 100 ? 2 : 4)}`;
const timeLabel = (iso) => iso ? new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(iso)) : "—";
const usageDateLabel = (iso) => iso ? iso.slice(5, 10).replace("-", "/") : "—";
const providerData = (name) => state.providers.find((item) => item.provider === name) || { requests: 0, total_tokens: 0, input_tokens: 0, output_tokens: 0, cached_tokens: 0, cost: 0, unpriced: 0 };

function toast(message, isError = false) {
  const node = $("toast");
  if (!node) return;
  node.textContent = message;
  node.style.background = isError ? "var(--danger)" : "var(--ink)";
  node.classList.add("show");
  clearTimeout(node.timer);
  node.timer = setTimeout(() => node.classList.remove("show"), 2400);
}

function renderProvider(name) {
  const data = providerData(name);
  const input = Number(data.input_tokens || 0);
  const cached = Number(data.cached_tokens || 0);
  const ratio = input ? cached / input * 100 : 0;
  const tokens = $(`${name}Tokens`);
  if (tokens) tokens.textContent = number(data.total_tokens);
  const cost = $(`${name}Cost`);
  if (cost) cost.textContent = money(data.cost);
  const cache = $(`${name}Cache`);
  if (cache) cache.textContent = input ? `${ratio.toFixed(1)}%` : "—";
  const requests = $(`${name}Requests`);
  if (requests) requests.textContent = number(data.requests);
  const status = $(`${name}Status`);
  if (status) {
    const ready = name === "deepseek" ? Boolean(state.web_import?.last_success) : Boolean(state.web_import?.mimo_last_success);
    status.textContent = ready ? "网页登录" : "等待同步";
    status.classList.toggle("ready", ready);
  }
}

function renderBalances() {
  const deepseek = state.balances.find((item) => item.provider === "deepseek");
  const dsBalance = $("deepseekBalance");
  const dsMeta = $("deepseekBalanceMeta");
  const dsWater = $("deepseekWater");
  if (deepseek && deepseek.total_balance !== null) {
    if (dsBalance) dsBalance.textContent = money(deepseek.total_balance);
    if (dsMeta) dsMeta.textContent = deepseek.error ? "上次刷新失败" : `网页同步 · ${timeLabel(deepseek.captured_at)}`;
    if (dsWater) dsWater.style.height = `${Math.max(4, Math.min(46, Number(deepseek.total_balance) / 2))}px`;
  } else {
    if (dsBalance) dsBalance.textContent = "—";
    if (dsMeta) dsMeta.textContent = state.web_import?.balance_status || deepseek?.error || "等待网页登录后同步";
  }
  const mimo = state.balances.find((item) => item.provider === "mimo");
  const mimoBalance = $("mimoBalance");
  const mimoMeta = $("mimoBalanceMeta");
  const mimoWater = $("mimoWater");
  if (mimoBalance) mimoBalance.textContent = mimo?.total_balance != null ? money(mimo.total_balance) : "—";
  if (mimoMeta) mimoMeta.textContent = mimo?.total_balance != null ? `网页同步 · ${timeLabel(mimo.captured_at)}` : (state.web_import?.mimo_status || "等待网页登录后同步");
  if (mimoWater) mimoWater.style.height = `${mimo?.total_balance != null ? Math.max(4, Math.min(46, Number(mimo.total_balance) / 2)) : 4}px`;

  const warning = state.settings?.warning_balance ?? 10;
  [["deepseek", deepseek?.total_balance], ["mimo", mimo?.total_balance]].forEach(([name, balance]) => {
    const water = $(`${name}Water`);
    if (water) water.style.background = balance !== null && balance <= warning ? "var(--warning)" : "var(--safe)";
  });
}

function renderBand() {
  if (!$("tokenBand")) return;
  const ds = Number(providerData("deepseek").total_tokens || 0);
  const mi = Number(providerData("mimo").total_tokens || 0);
  const total = ds + mi;
  $("tokenBand").innerHTML = total
    ? `<div class="deepseek" style="width:${ds / total * 100}%" title="DeepSeek ${number(ds)}"></div><div class="mimo" style="width:${mi / total * 100}%" title="MiMo ${number(mi)}"></div>`
    : '<div class="band-empty">等待第一笔请求</div>';
  const dsShare = $("bandDeepseekShare");
  if (dsShare) dsShare.textContent = total ? `${(ds / total * 100).toFixed(1)}%` : "—";
  const miShare = $("bandMimoShare");
  if (miShare) miShare.textContent = total ? `${(mi / total * 100).toFixed(1)}%` : "—";
}

function renderLedger() {
  const body = $("ledgerBody");
  if (!body) return;
  body.innerHTML = (state.recent || []).length ? state.recent.map((row) => `
    <tr data-provider="${esc(row.provider)}">
      <td>${usageDateLabel(row.created_at)}</td>
      <td><span class="provider-label">${row.provider === "deepseek" ? "DeepSeek" : "MiMo"}</span><span class="model-label">${esc(row.model)}</span></td>
      <td>${number(row.input_tokens)}</td><td>${number(row.cached_tokens)}</td><td>${number(row.output_tokens)}</td>
      <td>${row.priced ? money(row.cost) : "待定价"}</td>
      <td class="${row.status_code < 400 ? "ok" : "bad"}">${row.status_code}</td>
    </tr>`).join("") : '<tr><td colspan="7" class="empty">还没有导入官方用量</td></tr>';
  const notice = $("unpricedNotice");
  if (notice) notice.hidden = !state.providers.some((item) => item.unpriced > 0);
}

function setText(id, value) { const el = $(id); if (el) el.textContent = value; }

function render() {
  setText("asOf", new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short", hour12: false }).format(new Date()));
  const today = state.today || {};
  const todayInput = Number(today.input_tokens || 0);
  const todayCached = Number(today.cached_tokens || 0);
  setText("todayTokens", number(today.total_tokens));
  setText("todayCost", money(today.cost));
  setText("todayCache", todayInput ? `${(todayCached / todayInput * 100).toFixed(1)}%` : "—");
  setText("todayRequests", number(today.requests));
  renderProvider("deepseek"); renderProvider("mimo"); renderBalances(); renderBand(); renderLedger();
  const wb = $("warningBalance");
  if (wb) wb.value = state.settings?.warning_balance ?? 10;
}

async function load() {
  try {
    const response = await fetch("/api/summary");
    if (!response.ok) throw new Error("读取失败");
    state = await response.json(); render();
  } catch (error) { toast(error.message, true); }
}

const dialog = $("settingsDialog");
document.querySelectorAll("nav a").forEach((link) => link.addEventListener("click", () => {
  document.querySelectorAll("nav a").forEach((item) => item.removeAttribute("aria-current"));
  link.setAttribute("aria-current", "page");
}));
const openBtn = $("openSettings");
if (openBtn && dialog) openBtn.addEventListener("click", async () => { dialog.showModal(); });
const closeBtn = $("closeSettings");
if (closeBtn && dialog) closeBtn.addEventListener("click", () => dialog.close());
const settingsForm = $("settingsForm");
if (settingsForm) settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = { warning_balance: Number($("warningBalance")?.value || 10) };
    const response = await fetch("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error("保存失败"); if (dialog) dialog.close(); toast("设置已保存"); await load();
  } catch (error) { toast(error.message, true); }
});

document.querySelectorAll(".web-login-button").forEach((button) => button.addEventListener("click", async () => {
  if (!window.pywebview?.api) { toast("网页登录仅在桌面版可用", true); return; }
  button.disabled = true;
  try {
    const result = await window.pywebview.api.open_provider_login(button.dataset.provider);
    if (!result.ok) throw new Error(result.error || "无法打开登录窗口");
    toast(`${button.dataset.provider === "deepseek" ? "DeepSeek" : "MiMo"} 登录窗口已打开`);
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
}));

load();
setInterval(load, 30_000);

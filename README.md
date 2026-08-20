<p align="center">
  <img src="static/mimoseekWatch-icon-128.png" alt="mimoseekWatch" width="80" height="80">
</p>

<h1 align="center">mimoseekWatch</h1>

<p align="center">
  <strong>DeepSeek / MiMo API 用量看板</strong><br>
  <sub>Windows 本地运行 · WebView2 自动同步 · 数据仅存本机</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows11&logoColor=fff" alt="Windows">&ensp;
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=fff" alt="Python">&ensp;
  <img src="https://img.shields.io/badge/WebView2-0F7EBF?logo=microsoftedge&logoColor=fff" alt="WebView2">&ensp;
  <img src="https://img.shields.io/badge/License-MIT-3DA639" alt="MIT License">
</p>

<p align="center">
  <a href="#中文">中文</a> · <a href="#english">English</a>
</p>

---

## 中文

mimoseekWatch 使用内置 WebView2 保存网页登录状态，自动读取 DeepSeek 和 Xiaomi MiMo 的**官方余额与用量数据**。

> **不代理 API 请求 · 不要求填写 API Key · 不根据公开价格估算费用**
>
> 应用界面品牌为 `TokenWatch`，程序名与可执行文件名为 `mimoseekWatch`。

### 功能一览

| | 功能 | 说明 |
| :--- | :--- | :--- |
| 💰 | 官方余额 | 显示 DeepSeek 与 MiMo 官方账户余额 |
| 📈 | 30 天汇总 | 最近 30 天 Token 用量、消费金额、缓存命中率、请求数 |
| ⚡ | 今日总览 | 当天两家平台合计的 Token、消费、缓存命中与请求数 |
| 📋 | 用量明细 | 按日期展示两家平台的用量明细 |
| 🔄 | 自动同步 | 首次登录后保存会话，启动时同步，之后每 5 分钟一次 |
| 🔒 | 仅存本机 | 所有统计数据和登录会话只保存在本地 |

### 数据来源

**DeepSeek**

| 数据 | 获取方式 |
| :--- | :--- |
| 余额 | 通过已登录的 WebView 会话读取官方账户接口 |
| 用量 | 后台自动打开官方 Usage 页面，导出并解析最近 30 天 ZIP/CSV |
| 消费金额 | 以官方导出文件为准，不在本地重新计价 |

**Xiaomi MiMo**

| 数据 | 获取方式 |
| :--- | :--- |
| 余额 | 通过已登录的 WebView 会话读取官方余额接口 |
| 用量 | 读取本月和上月官方账单明细，合并后筛选最近 30 天 |
| 缓存命中率 | 按 `缓存输入 Token / 总输入 Token` 计算 |

> ℹ️ MiMo 日数据会在次日 07:00 UTC 完成最终校对，当天数据可能继续变化。

### 快速开始

**环境要求**：Windows 10 / 11 · Microsoft Edge WebView2 Runtime（源码运行需 Python 3.11+）

1. 从 GitHub Releases 下载 `mimoseekWatch.exe`
2. 双击运行，打开右上角「设置」
3. 点击「登录 DeepSeek」「登录 MiMo」，在弹出的官方页面完成登录
4. 登录窗口可以关闭，主界面会在后台自动同步，之后每 5 分钟更新一次

> ⚠️ 验证码、短信验证和二次验证必须在官方页面手动完成。

### 开发指南

<details>
<summary><b>从源码运行</b></summary>

```powershell
git clone <your-repository-url>
cd mimoseekWatch
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

`start.ps1` 会创建 `.venv`、安装依赖并启动桌面程序。也可以手动运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\mimoseekWatch.py
```

</details>

<details>
<summary><b>运行测试</b></summary>

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

</details>

<details>
<summary><b>打包 Windows EXE</b></summary>

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm .\mimoseekWatch.spec
```

生成文件位于 `dist\mimoseekWatch.exe`。

</details>

<details>
<summary><b>项目结构</b></summary>

| 路径 | 说明 |
| :--- | :--- |
| `mimoseekWatch.py` | 桌面程序入口与 WebView 自动同步 |
| `mimoseekwatch/` | FastAPI、本地数据库和用量解析 |
| `static/` | 前端页面、样式和应用图标 |
| `tests/` | 数据库与 DeepSeek 导出解析测试 |
| `mimoseekWatch.spec` | PyInstaller 打包配置 |
| `start.ps1` | Windows 本地启动脚本 |
| `requirements.txt` | 运行依赖 |
| `requirements-dev.txt` | 测试与打包依赖 |

</details>

### 本地数据与隐私

默认数据目录：`%LOCALAPPDATA%\mimoseekWatch`

| 目录 / 文件 | 内容 |
| :--- | :--- |
| `mimoseekwatch.db` | 官方同步的余额、用量和本地设置 |
| `webview\` | WebView2 登录会话和 Cookie |
| `usage-sync\` | DeepSeek 后台自动下载的官方用量文件 |

Cookie 不会写入 SQLite 数据库，也不应提交到 Git。`.gitignore` 已排除数据库、日志、WebView 数据、虚拟环境和构建产物。

<details>
<summary><b>自定义数据位置</b></summary>

| 环境变量 | 作用 |
| :--- | :--- |
| `MIMOSEEKWATCH_DATA_DIR` | 本地数据目录 |
| `MIMOSEEKWATCH_DB` | SQLite 数据库文件路径 |

</details>

### 已知限制

- 依赖 DeepSeek 和 MiMo 网页当前的接口及页面结构，平台更新后可能需要同步调整
- DeepSeek 官方导出、MiMo 账单和余额接口可能存在平台侧延迟
- 登录 Cookie 失效后，需要重新打开登录窗口完成登录
- 本项目与 DeepSeek、Xiaomi 或 MiMo 官方无隶属关系

### 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

## English

mimoseekWatch uses a built-in WebView2 to preserve web login sessions and automatically reads **official balance and usage data** from DeepSeek and Xiaomi MiMo.

> **No API proxying · No API Key required · No cost estimates from public pricing**
>
> The in-app UI brand is `TokenWatch`; the program name and executable are `mimoseekWatch`.

### Features

| | Feature | Description |
| :--- | :--- | :--- |
| 💰 | Balances | Official account balances for DeepSeek and MiMo |
| 📈 | 30-day summary | Token usage, spending, cache hit ratio, and request count over the last 30 days |
| ⚡ | Today at a glance | Combined tokens, spending, cache hit ratio, and requests for both providers today |
| 📋 | Daily details | Daily usage breakdown for both providers |
| 🔄 | Auto sync | Sessions saved after first login; syncs on startup, then every 5 minutes |
| 🔒 | Local only | All statistics and login sessions stay on your machine |

### Data Sources

**DeepSeek**

| Data | How it is read |
| :--- | :--- |
| Balance | Official account API via the logged-in WebView session |
| Usage | Background export and parsing of the latest 30-day ZIP/CSV from the Usage page |
| Spending | Taken from the official export; never re-priced locally |

**Xiaomi MiMo**

| Data | How it is read |
| :--- | :--- |
| Balance | Official balance API via the logged-in WebView session |
| Usage | Current and previous month's billing details, filtered to the last 30 days |
| Cache hit ratio | `cached input tokens / total input tokens` |

> ℹ️ MiMo daily data is finalized at 07:00 UTC the next day, so today's figures may still change.

### Quick Start

**Requirements**: Windows 10 / 11 · Microsoft Edge WebView2 Runtime (Python 3.11+ from source)

1. Download `mimoseekWatch.exe` from GitHub Releases
2. Double-click to run, then open **Settings** in the top-right corner
3. Click **Login DeepSeek** and **Login MiMo**, and complete login in the pop-up windows
4. The login windows can be closed; the dashboard syncs in the background every 5 minutes

> ⚠️ CAPTCHAs, SMS verification, and two-factor authentication must be completed manually on the official pages.

### Development

<details>
<summary><b>Running from source</b></summary>

```powershell
git clone <your-repository-url>
cd mimoseekWatch
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

`start.ps1` creates `.venv`, installs dependencies, and launches the desktop app. Manual alternative:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\mimoseekWatch.py
```

</details>

<details>
<summary><b>Running tests</b></summary>

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

</details>

<details>
<summary><b>Building the Windows EXE</b></summary>

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm .\mimoseekWatch.spec
```

Output: `dist\mimoseekWatch.exe`

</details>

<details>
<summary><b>Project structure</b></summary>

| Path | Description |
| :--- | :--- |
| `mimoseekWatch.py` | Desktop entry point & WebView auto-sync |
| `mimoseekwatch/` | FastAPI server, database, and usage parser |
| `static/` | Frontend pages, styles, and app icon |
| `tests/` | Database and DeepSeek export parsing tests |
| `mimoseekWatch.spec` | PyInstaller build spec |
| `start.ps1` | Windows local startup script |
| `requirements.txt` | Runtime dependencies |
| `requirements-dev.txt` | Test & build dependencies |

</details>

### Local Data & Privacy

Default data directory: `%LOCALAPPDATA%\mimoseekWatch`

| Path | Contents |
| :--- | :--- |
| `mimoseekwatch.db` | Balances, usage, and local settings synced from official sources |
| `webview\` | WebView2 login sessions and cookies |
| `usage-sync\` | DeepSeek official usage files downloaded in the background |

Cookies are not stored in the SQLite database and should not be committed to Git. The `.gitignore` already excludes databases, logs, WebView data, virtual environments, and build artifacts.

<details>
<summary><b>Custom data locations</b></summary>

| Variable | Purpose |
| :--- | :--- |
| `MIMOSEEKWATCH_DATA_DIR` | Local data directory |
| `MIMOSEEKWATCH_DB` | SQLite database file path |

</details>

### Known Limitations

- Depends on the current DeepSeek and MiMo web interfaces; platform updates may require changes
- Official exports, billing, and balance APIs may have platform-side delays
- When login cookies expire, you must re-open the login window
- Not affiliated with DeepSeek, Xiaomi, or MiMo

### License

Released under the [MIT License](LICENSE).

---

<p align="center">
  <sub>mimoseekWatch · 本地模型账本 / Local model ledger</sub>
</p>

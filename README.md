<p align="center">
  <img src="static/mimoseekWatch-icon-128.png" alt="mimoseekWatch icon" width="96" height="96">
</p>

<h1 align="center">mimoseekWatch</h1>

<p align="center">
  <strong>DeepSeek / MiMo API usage dashboard for Windows</strong><br>
  <em>Windows 本地 DeepSeek / MiMo 用量看板</em>
</p>

<p align="center">
  <a href="#中文">中文</a> · <a href="#english">English</a>
</p>

---

## 中文

一个运行在 Windows 本地的 DeepSeek / Xiaomi MiMo 用量看板。

mimoseekWatch 使用内置 WebView2 保存网页登录状态，自动读取官方余额和用量数据。它不代理 API 请求，不要求填写 API Key，也不会根据公开价格自行估算费用。

> 应用左上角保留 `TokenWatch` 作为界面品牌，程序名称和可执行文件名为 `mimoseekWatch`。

### 功能

- 显示 DeepSeek 与 MiMo 官方账户余额。
- 汇总最近 30 天 Token 用量、官方消费金额、缓存命中率和请求数。
- 显示当天两家平台合计的 Token、消费金额、缓存命中率和请求数。
- 按日期展示两家平台的用量明细。
- 首次登录后保存 WebView2 会话，软件启动时自动同步，之后每 5 分钟同步一次。
- 所有统计数据和登录会话仅保存在本机。

### 数据来源

#### DeepSeek

- 余额：通过已登录的 DeepSeek WebView 会话读取官方账户接口。
- 用量：后台自动打开官方 Usage 页面，导出并解析官方最近 30 天 ZIP/CSV。
- 消费金额以官方导出文件为准，不在本地重新计价。

#### Xiaomi MiMo

- 余额：通过已登录的 MiMo WebView 会话读取官方余额接口。
- 用量：读取本月和上月官方账单明细，合并后筛选最近 30 天。
- 缓存命中率按 `缓存输入 Token / 总输入 Token` 计算。

MiMo 日数据会在次日 07:00 UTC 完成最终校对，因此当天数据可能继续变化。

### 系统要求

- Windows 10 或 Windows 11
- Microsoft Edge WebView2 Runtime
- 从源码运行时需要 Python 3.11 或更高版本

### 使用发行版

1. 从 GitHub Releases 下载 `mimoseekWatch.exe`。
2. 双击运行，打开"设置"。
3. 分别点击"登录 DeepSeek"和"登录 MiMo"，在弹出的官方页面完成登录。
4. 登录窗口可以关闭，主界面会在后台自动同步。

验证码、短信验证和二次验证必须由用户在官方页面手动完成。

### 使用方法

点击右上角「设置」，分别登录 DeepSeek 与 MiMo 网页即可。登录后程序自动同步余额和用量，之后每 5 分钟更新一次。

### 从源码运行

```powershell
git clone <your-repository-url>
cd mimoseekWatch
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

`start.ps1` 会创建 `.venv`、安装运行依赖并启动桌面程序。

也可以手动运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\mimoseekWatch.py
```

### 测试

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

### 打包 Windows EXE

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm .\mimoseekWatch.spec
```

生成文件位于 `dist\mimoseekWatch.exe`。

### 本地数据与隐私

默认数据目录：

```text
%LOCALAPPDATA%\mimoseekWatch
```

其中：

- `mimoseekwatch.db` 保存官方同步得到的余额、用量和本地设置。
- `webview\` 保存 WebView2 登录会话和 Cookie。
- `usage-sync\` 保存 DeepSeek 后台自动下载的官方用量文件。

Cookie 不会写入 SQLite 数据库，也不应提交到 Git。项目的 `.gitignore` 已排除数据库、日志、WebView 数据、虚拟环境和构建产物。

可通过环境变量修改数据位置：

- `MIMOSEEKWATCH_DATA_DIR`：本地数据目录。
- `MIMOSEEKWATCH_DB`：SQLite 数据库文件路径。

### 项目结构

```text
mimoseekWatch.py          桌面程序入口与 WebView 自动同步
mimoseekwatch/            FastAPI、本地数据库和用量解析
static/                    前端页面、样式和应用图标
tests/                     数据库与 DeepSeek 导出解析测试
mimoseekWatch.spec         PyInstaller 打包配置
start.ps1                  Windows 本地启动脚本
requirements.txt           运行依赖
requirements-dev.txt       测试与打包依赖
```

### 已知限制

- 本项目依赖 DeepSeek 和 MiMo 网页当前使用的接口及页面结构；平台更新后可能需要同步调整。
- DeepSeek 官方导出、MiMo 账单和余额接口可能存在平台侧延迟。
- 登录 Cookie 失效后，需要重新打开登录窗口完成登录。
- 本项目与 DeepSeek、Xiaomi 或 MiMo 官方无隶属关系。


### 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

## English

A local DeepSeek / Xiaomi MiMo usage dashboard for Windows.

mimoseekWatch uses a built-in WebView2 to preserve web login sessions and automatically reads official balance and usage data. It does not proxy API requests, does not require an API Key, and does not estimate costs based on public pricing.

> The in-app header retains `TokenWatch` as the UI brand; the program name and executable are `mimoseekWatch`.

### Features

- Displays official account balances for DeepSeek and MiMo.
- Summarizes the last 30 days of token usage, official spending, cache hit ratio, and request count.
- Shows today's combined tokens, spending, cache hit ratio, and request count across both providers.
- Lists daily usage details for both providers.
- After the first login, the WebView2 session is saved; the app auto-syncs on startup and every 5 minutes thereafter.
- All statistics and login sessions are stored locally only.

### Data Sources

#### DeepSeek

- Balance: read from the official account API via the logged-in DeepSeek WebView session.
- Usage: the background automatically opens the official Usage page, exports and parses the latest 30-day ZIP/CSV.
- Spending figures come from the official export and are not re-priced locally.

#### Xiaomi MiMo

- Balance: read from the official balance API via the logged-in MiMo WebView session.
- Usage: reads the current and previous month's billing details, then filters the last 30 days.
- Cache hit ratio is calculated as `cached input tokens / total input tokens`.

MiMo daily data is finalized at 07:00 UTC the next day, so today's figures may still change.

### System Requirements

- Windows 10 or Windows 11
- Microsoft Edge WebView2 Runtime
- Python 3.11 or later (when running from source)

### Using the Release

1. Download `mimoseekWatch.exe` from GitHub Releases.
2. Double-click to run, then open **Settings**.
3. Click **Login DeepSeek** and **Login MiMo** to complete login in the pop-up windows.
4. The login windows can be closed; the main dashboard syncs in the background.

CAPTCHAs, SMS verification, and two-factor authentication must be completed manually on the official pages.

### Usage

Click **Settings** in the top-right corner, then log in to DeepSeek and MiMo. Once logged in, the app automatically syncs balances and usage, updating every 5 minutes.

### Running from Source

```powershell
git clone <your-repository-url>
cd mimoseekWatch
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

`start.ps1` creates `.venv`, installs dependencies, and launches the desktop app.

Alternatively, run manually:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\mimoseekWatch.py
```

### Testing

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

### Building the Windows EXE

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm .\mimoseekWatch.spec
```

Output: `dist\mimoseekWatch.exe`

### Local Data & Privacy

Default data directory:

```text
%LOCALAPPDATA%\mimoseekWatch
```

Contents:

- `mimoseekwatch.db` — balances, usage, and local settings synced from official sources.
- `webview\` — WebView2 login sessions and cookies.
- `usage-sync\` — DeepSeek official usage files downloaded in the background.

Cookies are not stored in the SQLite database and should not be committed to Git. The `.gitignore` already excludes databases, logs, WebView data, virtual environments, and build artifacts.

Override the data location with environment variables:

- `MIMOSEEKWATCH_DATA_DIR` — local data directory.
- `MIMOSEEKWATCH_DB` — SQLite database file path.

### Project Structure

```text
mimoseekWatch.py          Desktop entry point & WebView auto-sync
mimoseekwatch/            FastAPI server, database, and usage parser
static/                    Frontend pages, styles, and app icon
tests/                     Database and DeepSeek export parsing tests
mimoseekWatch.spec         PyInstaller build spec
start.ps1                  Windows local startup script
requirements.txt           Runtime dependencies
requirements-dev.txt       Test & build dependencies
```

### Known Limitations

- This project depends on the current DeepSeek and MiMo web interfaces and page structures; platform updates may require corresponding changes.
- Official DeepSeek exports, MiMo billing, and balance APIs may have platform-side delays.
- When login cookies expire, you must re-open the login window to log in again.
- This project is not affiliated with DeepSeek, Xiaomi, or MiMo.


### License

This project is licensed under the [MIT License](LICENSE).

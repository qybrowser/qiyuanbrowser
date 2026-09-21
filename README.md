# 启元指纹浏览器（Qiyuan Fingerprint Browser）

启元指纹浏览器是一款基于 Chromium、Firefox 和 Python 的开源指纹浏览器，支持创建相互隔离的浏览器环境，并为不同环境配置独立的浏览器指纹与网络代理。项目在本地运行，提供可视化管理后台，适合多账号管理、跨境电商、广告投放、自动化测试和浏览器指纹研究等场景。

> 请在遵守目标网站服务条款及所在地法律法规的前提下使用本项目。

[项目介绍](#一项目介绍) · [检测结果](#二浏览器指纹检测结果) · [快速开始](#三快速开始) · [商用推荐](#四商用指纹浏览器推荐) · [联系作者](#五联系与讨论)

## 一、项目介绍

浏览器指纹由 User-Agent、操作系统、屏幕参数、字体、Canvas、WebGL、时区、语言等信息共同构成。网站可以组合这些信息来识别浏览器环境。指纹浏览器通过为每个环境提供相对独立且一致的配置，减少多个账号之间因 Cookie、本地存储和设备信息混用而产生的关联。

启元指纹浏览器目前提供：

- 独立浏览器环境与本地数据隔离
- 浏览器指纹生成与环境配置
- HTTP、HTTPS、SOCKS5 代理管理
- 可视化环境管理后台
- 基于 Python 的本地 SDK 和 HTTP API
- 本地 SQLite 数据存储

典型应用场景包括跨境电商、广告投放、社交媒体运营、海外团队协作、联盟营销、网站兼容性测试、QA 自动化测试、合规数据采集以及不同工作身份的隐私隔离。

![指纹浏览器的典型应用场景，包括跨境电商、广告投放、社媒运营和自动化测试](assets/images/fingerprint-browser-use-cases.png)

## 二、浏览器指纹检测结果

以下为 **2026-09-15** 的测试记录：

| 检测平台 | 检测结果 |
| --- | :---: |
| [BrowserScan](https://browserscan.net/) | ✅ 通过 |
| [Sannysoft Bot Test](https://bot.sannysoft.com/) | ✅ 通过 |
| [CreepJS](https://abrahamjuliot.github.io/creepjs/) | ✅ 通过 |
| [FV.PRO Privacy Check](https://fv.pro/check-privacy/general) | ✅ 通过 |
| [Fingerprint.com Demo](https://fingerprint.com/demo/) | ✅ 通过 |
| [PixelScan](https://pixelscan.net/fingerprint-check) | ⚠️ 待优化 |
| [IPHey](https://iphey.com/) | ⚠️ 待优化 |

> 检测结果会受到浏览器版本、操作系统、网络代理、指纹配置以及检测网站规则更新的影响，仅代表测试时的结果，不构成持续通过保证。

## 三、快速开始

当前项目适用于 Windows 系统。开始前请准备：

- Windows 10 或更高版本
- Python 3.10 及以上版本
- Git
- Node.js 18 及以上版本（用于构建管理界面）

启元浏览器由服务端和客户端组成：

- 服务端运行在 `9003` 端口，负责保存和管理环境、代理、扩展等数据；
- 客户端运行在 `9005` 端口，负责管理本机浏览器资源和已安装内核；
- 浏览器内核需要先从 GitHub Releases 下载，再通过客户端页面上传安装。

### 1. 下载项目源码

```bash
git clone https://github.com/qybrowser/qiyuanbrowser.git
cd qiyuanbrowser
```

### 2. 下载浏览器内核

打开项目的 [GitHub Releases](https://github.com/qybrowser/qiyuanbrowser/releases)，进入最新版本，在 **Assets** 中下载需要的浏览器内核压缩包。

当前支持：

- Chromium，例如 `chromium-150.0.7871.115.zip`
- Firefox，例如 `firefox-153.0.4.zip`

不要下载 GitHub 自动生成的 `Source code (zip)` 或 `Source code (tar.gz)`，它们不包含可运行的浏览器内核。

![在 GitHub Releases 的 Assets 中下载 Chromium 和 Firefox 浏览器内核](assets/images/github-release-browser-kernel.png)

下载完成后不要将内核复制到源码目录，后续会通过客户端管理页面上传并安装。

### 3. 构建管理界面

首次启动前，需要先构建前端管理界面。在项目根目录执行：

```powershell
cd admin\frontend
npm install
npm run build
cd ..\..
```

构建完成后，项目会生成 `admin/static/dist/index.html`。如果缺少该文件，启动服务端或客户端后访问页面会提示“管理界面尚未构建”。

### 4. 创建 Python 虚拟环境

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

项目会在根目录创建 `.venv` 虚拟环境。后续启动服务端和客户端时，均使用该虚拟环境中的 Python。

> 如果使用命令提示符（CMD），可将 Python 路径写为 `.venv\Scripts\python.exe`。

### 5. 启动服务端

```powershell
.\.venv\Scripts\python.exe -m admin.server --config browser-config-server.json
```

服务端启动后默认监听：

```text
http://127.0.0.1:9003
```

服务端只负责保存和管理环境、代理、扩展等数据，不负责启动本地浏览器。

### 6. 启动客户端

确认 `browser-config-client.json` 中的地址配置正确：

```json
{
  "base_api_path": "http://127.0.0.1:9003",
  "base_local_api_path": "http://127.0.0.1:9005"
}
```

然后在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m admin.client --config browser-config-client.json
```

客户端启动后，打开：

```text
http://127.0.0.1:9005
```

客户端页面用于管理本机浏览器应用数据目录和浏览器内核。

### 7. 上传并安装浏览器内核

进入客户端 `9005` 地址后，打开左侧的“系统设置”。

在“更新内核”区域中：

1. 选择内核类型：Chromium 或 Firefox；
2. 填写内核版本号；
3. 选择从 GitHub Releases 下载的 ZIP 文件；
4. 如需设置为默认版本，勾选“设为默认版本”；
5. 点击“上传并安装”。

客户端会自动将内核解压到浏览器应用数据目录的 `client/<内核版本>/` 下，无需手动复制文件。

![客户端系统设置和浏览器内核上传页面](assets/images/qiyuan-sdk-settings.png)

安装完成后，返回服务端管理页面：

```text
http://127.0.0.1:9003
```

在“环境管理”中创建浏览器环境，选择 Chromium 或 Firefox 内核，然后配置代理、扩展和指纹参数并启动环境。

![服务端环境管理页面](assets/images/qiyuan-sdk-admin.png)

### 8. 功能测试

启动浏览器环境后，可以测试以下功能：

- 创建和管理多个独立浏览器环境；
- 配置 HTTP、HTTPS 或 SOCKS5 代理；
- 配置浏览器指纹参数；
- 安装和管理浏览器扩展；
- 分别启动 Chromium 和 Firefox 环境；
- 查看启动后的 IP、地理位置、WebRTC、WebGL、时区、语言、Canvas 等相关指纹信息。

### 实际运行效果

启动服务后，可以在启元指纹浏览器管理后台统一管理浏览器环境、代理和指纹配置：

![启元指纹浏览器管理后台，可创建、编辑和启动独立浏览器环境](assets/images/qiyuan-browser-admin.png)

打开浏览器环境后，启动页会显示当前 IP、地理位置、代理方式以及 WebRTC、WebGL、时区、语言、Canvas 等浏览器指纹信息：

![启元指纹浏览器启动后的环境信息与浏览器指纹配置](assets/images/qiyuan-browser-environment.png)

## 四、商用指纹浏览器推荐

本项目适合本地部署、指纹浏览器研究和 Python 二次开发。如果需要成熟的团队协作、账号权限管理、跨平台客户端、云端同步或商业售后服务，可以参考下面的商用指纹浏览器进行选型。

### 国内商用指纹浏览器

| 产品 | 主要特点 | 适用场景 |
| --- | --- | --- |
| [AdsPower](https://www.adspower.com/)（[国内站](https://adspower.net/)） | 中文界面，提供 API、RPA 自动化、窗口同步和多平台客户端 | TikTok Shop、Amazon、社媒矩阵及需要 Python 自动化对接的团队 |
| [比特浏览器 BitBrowser](https://www.bitbrowser.cn/) | Chrome 与 Firefox 双内核、本地 API、团队权限管理 | 中小团队、个人用户及需要双内核测试的场景 |
| [候鸟浏览器 MBBrowser](https://www.mbbrowser.com/) | 支持本地离线模式，可对接 Selenium、Puppeteer，并支持环境批量导入导出 | 重视本地数据存储的开发者和自动化脚本用户 |
| [紫鸟浏览器](https://www.ziniao.com/) | 面向跨境电商团队，提供店铺管理、团队权限及运营相关能力 | Amazon 等跨境电商平台和较大型运营团队 |

### 海外商用指纹浏览器

| 产品 | 主要特点 | 适用场景 |
| --- | --- | --- |
| [Multilogin](https://multilogin.com/) | 面向企业用户，提供多浏览器内核、API 和较完整的指纹参数管理 | 高风控业务及企业级账号矩阵运营 |
| [GoLogin](https://gologin.com/) | 提供云端浏览器模式、Linux 支持和代理相关服务 | 海外社媒、联盟营销和云端无人值守场景 |
| [Dolphin Anty](https://dolphin-anty.com/) | 提供自动化场景构建和批量环境管理能力 | 广告投放、联盟营销、个人用户及小型工作室 |
| [EchoX](https://echoxbrowser.com/)（[GitHub](https://github.com/EchoXBrowser/EchoX)） | 偏重 API、RPA 和二次开发，支持 Windows、macOS 与 Linux | 自研自动化系统及需要深度集成的开发团队 |

选择指纹浏览器时，建议重点比较浏览器内核、指纹一致性、代理支持、API 与自动化能力、团队权限、数据存储方式、操作系统支持和售后服务，而不应只比较可创建的环境数量。

> 上述商用指纹浏览器推荐仅作为选型参考，不代表本项目与相关产品存在合作或背书关系。产品功能、价格、免费额度和平台支持可能发生变化，请以官方网站的最新信息为准。

## 五、联系与讨论

如果在安装、启动或使用过程中遇到问题，欢迎通过 [GitHub Issues](https://github.com/qybrowser/qiyuanbrowser/issues) 反馈。提交问题时建议附上 Windows 版本、Python 版本、错误日志和复现步骤，以便更快定位问题。

也可以扫描下方二维码联系作者：

<img src="https://res.usefullc.com/fingerprint/qiyuan_kefu.jpg" width="260" alt="启元指纹浏览器作者客服微信二维码">

二维码无法显示时，可直接访问：[联系作者](https://res.usefullc.com/fingerprint/qiyuan_kefu.jpg)。

---

<details>
<summary><strong>开发者文档：SDK、HTTP API 与配置参考</strong></summary>

<br>

## Chromium Fingerprint SDK (Python)

A self-contained Python SDK for managing fingerprint-browser environments. It
unifies two surfaces into **one module**:

- **Environment / proxy management** — a simplified reimplementation of the
  cloud backend (`backend/app/api/v1/browser.py`, `proxy.py`, `fingerprint.py`),
  persisted to a local **SQLite** database.
- **Local browser control** — launches the qiyuan client browser in
  `--mode=client` (uuid + token only); the browser pulls and decrypts its own
  fingerprint from the SDK via `GET /api/v1/browser/md5/{uuid}`.
- **Client callbacks** — the 6 endpoints the launched browser calls back into
  (fingerprint, error report, tabs, status, ip-geo, check-proxy), faithfully
  ported from `backend/` and `front-electron/src/main/http-server.ts`.

No cloud backend and no Electron client are required to run it.

## How launching works

`env_open` runs the qiyuan kernel like:

```
%USERPROFILE%\.qiyuan\client\{browser_version}\QyBrowser.exe
  --mode=client --uuid={code} --token={token}
  --user-data-dir=%USERPROFILE%\.qiyuan\user_data\{code}
  --browser_app_data_dir=%USERPROFILE%\.qiyuan
  --enable-logging=stderr --log-level=0 --v=1
  --proxy-bypass-list="localhost;127.0.0.1;<local>"
  --no-first-run --new-window --window-position=0,0 --window-size=1280,720
```

No `--user-agent` / `--proxy-server` / `--remote-debugging-port` — those live
inside the encrypted fingerprint the browser fetches itself. Before launching,
the SDK writes the admin server URL into `%USERPROFILE%\.qiyuan\config\config.json`
(`base_api_path`) so the browser calls back into this SDK. Older kernel folders
may still contain `chrome.exe`; the launcher prefers `QyBrowser.exe` and falls
back to `chrome.exe`.

## Install and prepare the browser

On first admin-server start, the `client`, `config`, and `extends` directories
from this repository's `qiyuan/` directory are copied to `%USERPROFILE%/.qiyuan` without
overwriting existing files. If you choose a custom browser application directory
in the admin UI, copy these three directories there manually. The packaged
directories are:

- `client` — browser kernels and their runtime files.
- `config` — browser configuration and public key.
- `extends` — built-in browser extensions.

For a custom location, open the admin UI's **浏览器设置** tab and set
`browser_app_data_dir` to the copied `qiyuan` root.

```bash
pip install -r requirements.txt   # only needed for the admin web UI
```

Install the listed dependencies for encryption, geo/proxy checks, and the admin UI.

## SDK usage

```python
from chromium_sdk import ChromiumClient

client = ChromiumClient()                       # data in ~/.qiyuan

code = client.env_create(name="env-1", platform="Win32")["code"]
client.env_open(code)                           # launches real Chrome
print(client.env_status(code))                  # {'status': 'running', ...}
client.env_close(code)
```

## The 14 operations

| Group | Method | HTTP route (admin) |
|-------|--------|--------------------|
| Env | `env_list` | `GET /open/env/list` |
| Env | `env_create` | `POST /open/env/create` |
| Env | `env_update` | `POST /open/env/update` |
| Env | `env_delete` | `POST /open/env/delete` |
| Env | `env_open` | `POST /open/env/open` |
| Env | `env_close` | `POST /open/env/close` |
| Env | `env_status` | `GET /open/env/status` |
| Env | `env_clear_cache` | `POST /open/env/clear_cache` |
| Env | `env_randomize_fingerprint` | `POST /open/env/randomize_fingerprint` |
| Proxy | `proxy_list` | `GET /open/proxy/list` |
| Proxy | `proxy_create` | `POST /open/proxy/create` |
| Proxy | `proxy_update` | `POST /open/proxy/update` |
| Proxy | `proxy_delete` | `POST /open/proxy/delete` |
| Fingerprint | `generate_fingerprint` | `POST /open/fingerprint/generate` |

### Client callback endpoints (called by the launched browser)

| Method | Auth | Route |
|--------|------|-------|
| `get_encrypted_fingerprint` | Bearer | `GET /api/v1/browser/md5/{uuid}` |
| `report_error` | — | `POST /api/v1/browser/error/report` |
| `update_tabs` | — | `POST /api/v1/client/browser/tabs` |
| `check_proxy` | — | `POST /api/check-proxy` |
| `ip_geo` | Bearer | `GET /api/ip-geo` |
| `record_status` | — | `POST /api/browser/status` |

Fingerprint encryption (`GET /api/v1/browser/md5/{uuid}?secure=&encrypt_type=&version=`):

- `secure=false` → plaintext JSON (`encrypt_type` ignored).
- `encrypt_type=aes` (default) → `base64(IV[16] + AES-256-CBC(PKCS7(json)))`.
  - `version=1.0` (default) key: `aes-key-32-bytes-change!!!!!` padded to 32 bytes.
  - `version=2.0` key: `SHA-256("aes-key-32-bytes-change!!!!!" + "_qiyuan_" + token)`
    (32 bytes, per-user; token = the Bearer auth token).
- `encrypt_type=rsa` → AES 加密 + RSA 签名: `base64(SIGN[keysize/8] + IV[16] +
  AES-256-CBC(PKCS7(json)))`. AES key 恒由 token 派生（同 v2.0）；`SIGN =
  RSASSA-PKCS1-v1_5(私钥, SHA-256(IV+密文))`。服务端持**私钥签名**，内核只内置
  **公钥验签**后用 token 派生 key 解密——私钥永不下发。Keys in `chromium_sdk/keys/`
  (override via `CHROMIUM_SDK_RSA_PRIVATE_KEY`；公钥下发给内核). SDK 与 backend
  使用各自独立的密钥对。

Full HTTP reference: `backend/app/templates/chromium_api.html`.

## Management admin

```bash
cd qiyuanbrowser
uvicorn admin.server:app --host 127.0.0.1 --port 9003
# or: python -m admin.server
```

Open <http://127.0.0.1:9003> — a single-page UI to manage environments, proxies
and preview generated fingerprints. The admin and the SDK share the same SQLite
store.

## Configuration

| Env var | Purpose                                                         |
|---------|-----------------------------------------------------------------|
| `CHROMIUM_SDK_DATA_DIR` | SDK data dir (SQLite). Default `~/.qiyuan`                      |
| `CHROMIUM_SDK_TOKEN` | Static token; default auto-generated and stored in SQLite       |
| `CHROMIUM_SDK_BASE_API` | URL written into config.json. Default `http://127.0.0.1:9003`   |
| `CHROMIUM_SDK_QIYUAN_DIR` | Complete qiyuan root; overridden by a value saved in the admin UI |

Data layout:

```
$CHROMIUM_SDK_DATA_DIR/db/qiyuan.db           # SQLite (environments, proxies, errors, config)
$CHROMIUM_SDK_DATA_DIR/logs/qiyuan.log        # 服务日志；控制台同步输出，保留最近 7 天
%USERPROFILE%/.qiyuan/client/{version}/QyBrowser.exe  # kernel (fallback: chrome.exe)
%USERPROFILE%/.qiyuan/user_data/{uuid}/                # per-environment user-data-dir
%USERPROFILE%/.qiyuan/config/config.json               # base_api_path -> admin server
%USERPROFILE%/.qiyuan/extends/                          # built-in browser extensions
```

启动时若发现旧版 `$CHROMIUM_SDK_DATA_DIR/chromium_sdk.db` 且新库尚不存在，会将数据迁移到 `db/qiyuan.db`；旧库保留不删除。服务日志按天轮转，当前文件加最近 6 个归档文件共保留 7 天。

</details>

# fast-note-sync-fnos

将 [fast-note-sync-service](https://github.com/haierkeys/fast-note-sync-service) 打包为 **飞牛 fnOS** 应用（`.fpk`）的工程。

本仓库只包含 fnOS 应用包模板（manifest、生命周期脚本、权限/资源声明、桌面入口、图标、向导）。应用二进制本身在 GitHub Actions 构建时从上游 Release 下载，再用飞牛官方 `fnpack` 打包成 `.fpk`，按 x86 / arm 架构分别产出。

## 目录结构

```
.
├── app/
│   ├── ui/
│   │   ├── config          # 桌面入口（iframe，端口与 config.yaml 同步）
│   │   └── images/         # icon_64.png / icon_256.png
│   └── fast-note-sync-service   # CI 下载，已 gitignore
├── cmd/                    # 生命周期脚本（均带可执行位）
│   ├── main                # start / stop / status / restart / sync-entry
│   ├── install_init        # 安装前
│   ├── install_callback    # 安装后：预创建持久数据目录
│   ├── upgrade_init        # 升级前
│   ├── upgrade_callback    # 升级后：停掉旧进程
│   ├── uninstall_init      # 卸载前：停止服务（不删数据）
│   ├── uninstall_callback  # 卸载后：按用户选择删除或保留数据
│   ├── config_init         # 配置变更前
│   └── config_callback     # 配置变更后
├── config/
│   ├── privilege           # run-as=package，专用用户 fastnotesync
│   └── resource            # 无额外系统资源
├── wizard/
│   ├── uninstall           # 卸载向导：保留数据 / 删除所有数据
│   └── config              # 配置向导（应用设置 → 运行设置 → 高级设置：服务端口）
├── manifest
├── ICON.PNG                # 64x64
├── ICON_256.PNG            # 256x256
├── scripts/gen_icons.py    # 图标生成脚本
└── .github/workflows/build.yml
```

## 运行模型

- **访问方式**：端口服务（默认 `9000`）。端口可在「应用设置 → 运行设置 → 高级设置」中修改：保存后写进 `config.yaml` 的 `server.http-port`，同时把 `ui/config` 里桌面入口的端口改掉，然后重启服务。`config.yaml` 是端口的唯一来源，开机自启和升级都不会把它改回 9000。fast-note-sync-service 自带 Web 管理面板与鉴权，无需接入 NAS 登录态。
- **数据持久化**：配置 `config/config.yaml`、SQLite 数据库、上传与临时文件全部落在 `TRIM_PKGVAR`（`/vol*/@appdata/fastnotesync`），重启与升级不丢失。
- **首启**：服务首次启动自动生成 `config/config.yaml`（含随机 `auth-token-key`）；端口由配置向导写入 `config.yaml` 的 `server.http-port`。
- **架构**：二进制与架构相关，故分 `x86`（amd64）与 `arm`（arm64）两个 `.fpk`。

> 改端口后如果桌面图标还指向老端口，是应用中心缓存了入口；在 NAS 上执行 `sudo systemctl restart trim_app_center.service`（或重开应用）刷新即可。

## 外网访问与内网穿透

先给结论：**局域网内直接用 `http://NAS内网IP:9000`，不需要反向代理，也不需要穿透。** 只有「人不在家也要同步」才需要往下看。

### 为什么不能把飞牛「远程访问」的地址填给 Obsidian

飞牛的远程访问（FN Connect，`xxx.fnos.net`）是**给浏览器看页面**的中转：它把网页转发到你的浏览器，不向第三方应用开放端口或通道。Obsidian 的同步客户端要直连 `/api/user/sync` 的 WebSocket，走这个入口会一直提示连接失败。

而授权页给出的地址，是**按你当前打开面板的地址拼出来的**（上游逻辑：`API_URL = localStorage.API_URL || window.location.origin`）。所以「从哪个地址进来，就得到哪个地址」：

| 你从哪打开面板 | 授权页给出的地址 | Obsidian 能用吗 |
|---|---|---|
| `http://192.168.1.10:9000` | 内网地址 | 仅限内网 |
| `https://xxx.fnos.net/...` | 飞牛中转域名 | 不能 |
| `https://note.example.com` | 你的域名 | 任何网络都能用 |

### 方式一：DDNS + IPv6（推荐，不依赖第三方）

1. 飞牛「设置 → 远程访问 → DDNS」开启，挑一个域名（家里宽带有 IPv6 就够）。
2. 路由器放行 IPv6 入站，NAS 防火墙放行本应用端口（默认 9000）。
3. 用 `http://你的域名:9000` 打开面板，授权页给出的就是域名地址，Obsidian 填它。

> 手机流量多数只有 IPv4，纯 IPv6 的场景在外网可能连不上；那就用方式二或方式三。

### 方式二：内网穿透（Lucky / frp / Cloudflare Tunnel / Tailscale）

要点只有两条，踩坑基本都在这：

- **必须支持 WebSocket**。同步协议走 `/api/user/sync` 的 Upgrade，穿透工具不支持就会出现「面板打得开、同步连不上」。
- 穿透要把流量送到 **本应用的端口（默认 9000）**，不是飞牛的 5666。用 Nginx / OpenResty 中转时记得带上 `Upgrade`、`Connection` 头。

### 方式三：自己反向代理（有公网 IP 或已备案域名）

```nginx
location / {
    proxy_pass http://127.0.0.1:9000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;   # WebSocket 必需
    proxy_set_header Connection "upgrade";    # WebSocket 必需
    proxy_read_timeout 3600s;                 # 长连接不要被掐断
}
```

反代好之后用 `https://你的域名/` 打开面板，授权页就会给出 https 地址。如果反代不在 NAS 本机，还要把它的 IP 填进 `config.yaml` 的 `server.trusted-proxies`，否则上游不信任 `X-Forwarded-*` 头。

> 改过端口的话（应用设置里的「服务端口」），上面所有地址里的 9000 要换成你的新端口，Obsidian 里已填的地址也要跟着改。

## 卸载与数据

飞牛 fnOS **卸载应用时默认保留 `@appdata` 数据目录**，这是系统行为，不是卸载残留。因此直接卸载再重装，仍会读到旧的 `config.yaml` 与数据库，表现为「还是原来的账号密码」。

本应用通过 `wizard/uninstall` 让用户在卸载时自行选择：

| 选择 | 行为 |
|---|---|
| 保留数据（默认，推荐） | 数据目录原样保留，重装后恢复笔记与账号 |
| 删除所有数据 | `uninstall_callback` 删除 `TRIM_PKGVAR`，重装为全新状态 |

`uninstall_callback` 只删除 `basename(TRIM_PKGVAR) == appname` 的目录，路径不符时拒绝删除并报错，避免误删。

若需手动彻底清除：

```bash
sudo rm -rf /vol1/@appdata/fastnotesync
```

> 这会连同笔记数据库与附件一起删除。

## 本地复现

```bash
# 1. 下载上游二进制到 app/（版本号按需替换）
curl -L -o fns.tar.gz \
  https://github.com/haierkeys/fast-note-sync-service/releases/download/3.6.1/fast-note-sync-service-3.6.1-linux-amd64.tar.gz
tar -xzf fns.tar.gz -C app/ --strip-components=1 ./fast-note-sync-service

# 2. （arm 构建）把 manifest 的 platform 改为 arm，并下载 linux-arm64 包

# 3. 用 fnpack 打包
fnpack build --directory .
```

## CI

`.github/workflows/build.yml` 在 `ubuntu-latest` 上矩阵构建 x86 / arm 两个包。

### 触发方式

| 触发 | 行为 |
|---|---|
| push 到 `main` | 只产出 workflow artifact，不发 Release |
| push tag `v*` | 构建并发 Release，**tag 名即版本号** |
| 每周一 11:00（北京时间） | 检查上游是否有新版，有则自动发 Release，已发布则整链跳过 |
| 手动 `workflow_dispatch` | 可填 `fns_version` 指定版本，留空取上游最新 |

发新版只需打 tag：

```bash
git tag v3.6.2 && git push origin v3.6.2
```

> 版本号必须是三段式 `x.y.z`（应用商店不接受四段式或带后缀）。工作流解析出版本号后会按 `^[0-9]+\.[0-9]+\.[0-9]+$` 校验，不符合直接构建失败。

### 打包工具与签名

`fnpack` 自 **1.3.3** 起强制要求开发者证书，没有证书会直接拒绝打包。工作流按是否配置了 `FNPACK_CERT` secret 自动选择：

| 证书状态 | 使用的 fnpack | 产物 |
|---|---|---|
| 已配置 `FNPACK_CERT` | 1.3.3 | 签名包（官方推荐，可用于上架） |
| 未配置 | 1.2.3 | 未签名包（可手动安装，构建会输出告警） |

要启用签名，在飞牛开发者平台取得证书后，把证书与私钥写入仓库 Secrets：

- `FNPACK_CERT`：`developer.crt` 内容
- `FNPACK_KEY`：`developer.key` 内容（如有）

无需修改任何代码，下次构建自动切换到签名包。

### 完整性校验

- `fnpack` 二进制按版本 + sha256 双重固定，校验不过即中止
- 上游未提供 tarball 官方校验和，故构建日志会打印其 sha256，并把产物的 `SHA256SUMS` 一并发布

安装前校验：

```bash
sha256sum -c SHA256SUMS
```

## 与官方规范的对应关系

| 官方要求 | 本包实现 |
|---|---|
| `ICON.PNG` 64×64、`ICON_256.PNG` 256×256，≤1024 KB | 由 `scripts/gen_icons.py` 生成，4× 超采样后缩放 |
| `cmd/main` 处理 start/stop/status，status 以 0/3 退出 | 已实现，另支持 restart；start 幂等 |
| 生命周期脚本需可执行 | `cmd/*` 在 git 中记录为 100755 |
| 卸载逻辑应尊重用户数据 | `wizard/uninstall` + `uninstall_callback` 由用户决定 |
| 不要硬编码路径，使用 `TRIM_*` 变量 | 全部使用 `TRIM_APPDEST` / `TRIM_PKGVAR` / `TRIM_APPNAME` / `TRIM_TEMP_LOGFILE` |
| 最小权限运行 | `run-as=package`，专用用户 `fastnotesync` |
| 只声明实际需要的资源 | `config/resource` 为空对象 |
| `desktop_applaunchname` 与入口 ID 一致 | 均为 `fastnotesync.main` |
| 错误信息写入 `TRIM_TEMP_LOGFILE` | 启动失败、路径校验失败等场景均已写入 |

## 上架自查（先锋开发者）

对照官方《提交前自查》七条，逐条结论：

| # | 官方要求 | 本包情况 |
|---|---|---|
| 1 | 不允许 root 权限应用 | 通过。`config/privilege` 是 `run-as: package` + 专用用户 `fastnotesync`，未申请 root，也不写系统路径 |
| 2 | 优先接入统一网关；监听端口需有自己的鉴权，不可免鉴权访问 | 见下方「关于第 2 条」。应用自带登录口令 + 设备令牌，无免鉴权接口 |
| 3 | `platform` 只能 x86 / arm / all，且需自测可安装可运行 | 通过。分别产出 x86 / arm 两个包（二进制与架构绑定，不能用 `all`） |
| 4 | 有文件读写接口需校验路径，避免路径穿越 | 通过。脚本只用 `TRIM_*` 变量拼路径；`uninstall_callback` 额外校验 `basename(TRIM_PKGVAR) == appname`；笔记库路径校验由上游服务实现 |
| 5 | 有付费内容需在介绍首行声明 | 不适用。本应用完全免费、无内购、无功能限制，没有需声明的付费内容 |
| 6 | 版本号必须三段式 `x.y.z` | 通过。CI 解析出版本号后按 `^[0-9]+\.[0-9]+\.[0-9]+$` 校验，四段式直接构建失败 |
| 7 | 应用名称不得以「飞牛」为前缀 | 通过。名称为 `Fast Note Sync` |

### 关于第 2 条：为什么本应用必须监听端口

统一网关（`/app/{appname}` + Unix Socket）是为**浏览器**设计的：它依赖 NAS 的登录态，把页面和接口转发给当前登录的用户会话。而本应用的客户端是 **Obsidian 插件**，不是浏览器 —— 它拿不到 NAS 会话，只会直连 `http://host:port/api/user/sync` 的 WebSocket。所以只能走端口服务。

鉴权由应用自己完成，业务接口都要求登录态或令牌：

- **Web 管理面板**：需要账号口令登录（`server.webgui-login-token-expiry`，默认绑定 IP）；
- **同步 / API**：每台设备一个独立授权令牌（`security.auth-token-key` 派生），可随时在面板里吊销，令牌按 REST + WebSocket 全权限校验；
- **不配置穿透时**，端口只在局域网可达，公网访问不到。



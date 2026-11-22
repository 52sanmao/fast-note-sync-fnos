# fast-note-sync-fnos

将 [fast-note-sync-service](https://github.com/haierkeys/fast-note-sync-service) 打包为 **飞牛 fnOS** 应用（`.fpk`）的工程。

本仓库只包含 fnOS 应用包模板（manifest、生命周期脚本、权限与资源声明、桌面入口、图标、向导）。应用二进制本身在 GitHub Actions 构建时从上游 Release 下载，再由飞牛官方 `fnpack` 打包为 `.fpk`，按 x86 / arm 架构分别产出。

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

- **服务形式**：单二进制 Go 服务，内嵌 Web 管理面板，监听端口，默认 `9000`。
- **端口配置**：可在「应用设置 → 运行设置 → 高级设置」中修改。保存后端口写入 `config.yaml` 的 `server.http-port`，`ui/config` 中桌面入口的端口同步更新，随后服务重启。`config.yaml` 是端口的唯一来源，开机自启与升级均不会将其重置为 `9000`。
- **数据持久化**：`config/config.yaml`、SQLite 数据库、上传与临时文件全部位于 `TRIM_PKGVAR`（`/vol*/@appdata/fastnotesync`），重启与升级不丢失。
- **首次启动**：服务自动生成 `config/config.yaml`，其中包含随机 `auth-token-key`。
- **鉴权**：管理面板需账号口令登录；同步与 API 使用按设备签发的授权令牌，令牌可在面板中吊销，不存在免鉴权接口。
- **架构**：二进制与架构相关，故分为 `x86`（amd64）与 `arm`（arm64）两个 `.fpk`，不使用 `all`。

修改端口后，若桌面图标仍指向旧端口，说明应用中心缓存了入口信息，执行 `sudo systemctl restart trim_app_center.service`（或重新打开应用）即可刷新。

## 安装与升级

- **安装**：飞牛应用中心 → 手动安装 → 选择与设备架构匹配的 `.fpk`（x86_64 选 `x86`，ARM64 选 `arm`）。
- **升级**：覆盖安装即可。`config.yaml`、数据库与附件均保留，已授权的设备无需重新授权。

## 外网访问与内网穿透

局域网内直接访问 `http://<NAS 内网 IP>:9000` 即可，无需反向代理，也无需穿透。仅当需要在局域网之外同步时，才需要考虑以下方式。

### 飞牛远程访问不适用于同步客户端

飞牛的远程访问（FN Connect，`*.fnos.net`）是面向浏览器的中转：它将网页转发至浏览器，不向第三方应用开放端口或独立通道。Obsidian 的同步客户端需要直连 `/api/user/sync` 的 WebSocket，经由该入口会持续提示连接失败。

### 授权地址的生成方式

上游服务在授权页给出的地址，由当前打开面板的地址推导（`API_URL = localStorage.API_URL || window.location.origin`），即从哪个地址进入面板，就得到哪个地址：

| 打开面板的地址 | 授权页给出的地址 | 同步客户端是否可用 |
|---|---|---|
| `http://192.168.1.10:9000` | 内网地址 | 仅限内网 |
| `https://xxx.fnos.net/...` | 飞牛中转域名 | 不可用 |
| `https://note.example.com` | 自有域名 | 任意网络可用 |

### 方式一：DDNS + IPv6

不依赖第三方服务，家庭宽带具备 IPv6 时即可使用。

1. 在飞牛「设置 → 远程访问 → DDNS」中开启并选择一个域名。
2. 路由器放行 IPv6 入站，NAS 防火墙放行本应用端口（默认 `9000`）。
3. 通过 `http://<域名>:9000` 打开面板，授权页给出的即为域名地址，填入 Obsidian 即可。

> 移动网络多数仅提供 IPv4，纯 IPv6 场景在外网可能无法连接，此时应改用方式二或方式三。

### 方式二：内网穿透

适用于 Lucky、frp、Cloudflare Tunnel、Tailscale 等工具，有两条必要条件：

- **必须支持 WebSocket**。同步协议经由 `/api/user/sync` 的 Upgrade 完成，穿透工具不支持时会出现「面板可打开、同步连不上」。
- **流量须指向本应用端口（默认 `9000`）**，而非飞牛的 `5666`。经 Nginx 或 OpenResty 中转时需携带 `Upgrade` 与 `Connection` 头。

### 方式三：反向代理

适用于具备公网 IP 或已完成备案域名的场景。

```nginx
location / {
    proxy_pass http://127.0.0.1:9000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;   # WebSocket 必需
    proxy_set_header Connection "upgrade";    # WebSocket 必需
    proxy_read_timeout 3600s;                 # 保持长连接
}
```

配置完成后通过 `https://<域名>/` 打开面板，授权页给出的即为该 https 地址。若反向代理不在 NAS 本机，还需将其 IP 填入 `config.yaml` 的 `server.trusted-proxies`，否则上游服务不信任 `X-Forwarded-*` 头。

> 若已修改服务端口，上述地址中的 `9000` 需替换为新端口，Obsidian 中已填写的地址也应同步修改。

## 卸载与数据

fnOS 在卸载应用时默认保留 `@appdata` 数据目录，属系统行为而非卸载残留。因此直接卸载后重新安装，仍会读取原有的 `config.yaml` 与数据库，表现为沿用旧账号与口令。

本应用通过 `wizard/uninstall` 让用户在卸载时自行选择：

| 选择 | 行为 |
|---|---|
| 保留数据（默认，推荐） | 数据目录原样保留，重装后恢复笔记与账号 |
| 删除所有数据 | `uninstall_callback` 删除 `TRIM_PKGVAR`，重装为全新状态 |

`uninstall_callback` 仅在 `basename(TRIM_PKGVAR)` 与 `appname` 一致时执行删除，路径不符则拒绝并报错，以避免误删。

手动彻底清除：

```bash
sudo rm -rf /vol1/@appdata/fastnotesync
```

> 该操作会连同笔记数据库与附件一并删除。

## 本地构建

```bash
# 1. 下载上游二进制到 app/（版本号按需替换）
curl -L -o fns.tar.gz \
  https://github.com/haierkeys/fast-note-sync-service/releases/download/3.6.1/fast-note-sync-service-3.6.1-linux-amd64.tar.gz
tar -xzf fns.tar.gz -C app/ --strip-components=1 ./fast-note-sync-service

# 2. （arm 构建）将 manifest 的 platform 改为 arm，并下载 linux-arm64 包

# 3. 使用 fnpack 打包
fnpack build --directory .
```

## CI

`.github/workflows/build.yml` 在 `ubuntu-latest` 上矩阵构建 x86 / arm 两个包。

### 触发方式

| 触发 | 行为 |
|---|---|
| push 到 `main` | 仅产出 workflow artifact，不发布 Release |
| push tag `v*` | 构建并发布 Release，tag 名即版本号 |
| 每周一 11:00（北京时间） | 检查上游是否有新版本，有则自动发布，已发布则整链跳过 |
| 手动 `workflow_dispatch` | 可填写 `fns_version` 指定版本，留空取上游最新 |

发布新版本只需打 tag：

```bash
git tag v3.6.7 && git push origin v3.6.7
```

> 版本号必须为三段式 `x.y.z`。工作流解析出版本号后按 `^[0-9]+\.[0-9]+\.[0-9]+$` 校验，四段式或带后缀将直接构建失败。

### 打包工具与签名

`fnpack` 自 1.3.3 起强制要求开发者证书，未提供证书会拒绝打包。工作流依据是否配置 `FNPACK_CERT` secret 自动选择：

| 证书状态 | 使用的 fnpack | 产物 |
|---|---|---|
| 已配置 `FNPACK_CERT` | 1.3.3 | 签名包，可用于上架 |
| 未配置 | 1.2.3 | 未签名包，可手动安装，构建会输出告警 |

启用签名需在飞牛开发者平台取得证书后，写入仓库 Secrets：

- `FNPACK_CERT`：`developer.crt` 内容
- `FNPACK_KEY`：`developer.key` 内容（如有）

无需修改代码，下次构建自动切换为签名包。

### 完整性校验

- `fnpack` 二进制按版本与 sha256 双重固定，校验不通过即中止构建
- 上游未提供 tarball 官方校验和，构建日志会打印其 sha256，并将产物的 `SHA256SUMS` 一并发布

安装前校验：

```bash
sha256sum -c SHA256SUMS
```

## 与官方规范的对应关系

| 官方要求 | 本包实现 |
|---|---|
| `ICON.PNG` 64×64、`ICON_256.PNG` 256×256，≤1024 KB | 由 `scripts/gen_icons.py` 生成，4× 超采样后缩放 |
| `cmd/main` 处理 start/stop/status，status 以 0/3 退出 | 已实现，另支持 restart 与 sync-entry；start 幂等 |
| 生命周期脚本需可执行 | `cmd/*` 在 git 中记录为 100755 |
| 卸载逻辑应尊重用户数据 | `wizard/uninstall` 与 `uninstall_callback` 由用户决定去留 |
| 不硬编码路径，使用 `TRIM_*` 变量 | 全部使用 `TRIM_APPDEST` / `TRIM_PKGVAR` / `TRIM_APPNAME` / `TRIM_TEMP_LOGFILE` |
| 最小权限运行 | `run-as=package`，专用用户 `fastnotesync` |
| 只声明实际需要的资源 | `config/resource` 为空对象 |
| `desktop_applaunchname` 与入口 ID 一致 | 均为 `fastnotesync.main` |
| 错误信息写入 `TRIM_TEMP_LOGFILE` | 启动失败、路径校验失败等场景均已写入 |
| 版本号三段式 | CI 按 `^[0-9]+\.[0-9]+\.[0-9]+$` 校验 |

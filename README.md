# fast-note-sync-fnos

将 [fast-note-sync-service](https://github.com/haierkeys/fast-note-sync-service) 打包为 **飞牛 fnOS** 应用（`.fpk`）的工程。

本仓库只包含 fnOS 应用包模板（manifest、生命周期脚本、权限/资源声明、桌面入口、图标、向导）。应用二进制本身在 GitHub Actions 构建时从上游 Release 下载，再用飞牛官方 `fnpack` 打包成 `.fpk`，按 x86 / arm 架构分别产出。

## 目录结构

```
.
├── app/
│   ├── ui/
│   │   ├── config          # 桌面入口（端口服务，http:9000）
│   │   └── images/         # icon_64.png / icon_256.png
│   └── fast-note-sync-service   # CI 下载，已 gitignore
├── cmd/                    # 生命周期脚本（均带可执行位）
│   ├── main                # start / stop / status / restart
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
│   └── uninstall           # 卸载向导：保留数据 / 删除所有数据
├── manifest
├── ICON.PNG                # 64x64
├── ICON_256.PNG            # 256x256
├── scripts/gen_icons.py    # 图标生成脚本
└── .github/workflows/build.yml
```

## 运行模型

- **访问方式**：端口服务（`service_port=9000`）。fast-note-sync-service 自带 Web 管理面板与鉴权，无需接入 NAS 登录态。
- **数据持久化**：配置 `config/config.yaml`、SQLite 数据库、上传与临时文件全部落在 `TRIM_PKGVAR`（`/vol*/@appdata/fastnotesync`），重启与升级不丢失。
- **首启**：服务首次启动自动生成 `config/config.yaml`（含随机 `auth-token-key`），无需向导。
- **架构**：二进制与架构相关，故分 `x86`（amd64）与 `arm`（arm64）两个 `.fpk`。

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

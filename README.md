# fast-note-sync-fnos

将 [fast-note-sync-service](https://github.com/haierkeys/fast-note-sync-service) 打包为 **飞牛 fnOS** 应用（`.fpk`）的工程。

本仓库只包含 fnOS 应用包模板（manifest、生命周期脚本、权限/资源声明、桌面入口、图标）。应用二进制本身在 GitHub Actions 构建时从上游 Release 下载，再用飞牛官方 `fnpack` 打包成 `.fpk`，按 x86 / arm 架构分别产出。

## 目录结构

```
fnos-pkg/
├── app/
│   ├── ui/
│   │   ├── config          # 桌面入口（端口服务，http:9000）
│   │   └── images/         # icon_64.png / icon_256.png
│   └── fast-note-sync-service   # CI 下载，已 gitignore
├── cmd/
│   ├── main                # start / stop / status / restart
│   ├── install_callback    # 预创建持久工作目录
│   ├── upgrade_callback    # 升级后停掉旧进程
│   └── uninstall_init      # 卸载前停止服务
├── config/
│   ├── privilege           # run-as=package，专用用户 fastnotesync
│   └── resource            # 无额外系统资源
├── wizard/
├── manifest
├── ICON.PNG / ICON_256.PNG
├── scripts/gen_icons.py    # 图标生成脚本
└── .github/workflows/build.yml
```

## 运行模型

- **访问方式**：端口服务（`service_port=9000`）。fast-note-sync-service 自带 Web 管理面板与鉴权，无需接入 NAS 登录态。
- **数据持久化**：配置 `config/config.yaml`、SQLite 数据库、上传与临时文件全部落在 `TRIM_PKGVAR`（`/vol*/@appdata/fastnotesync`），重启与升级不丢失。
- **首启**：服务首次启动自动生成 `config/config.yaml`（含随机 `auth-token-key`），无需向导。
- **架构**：二进制与架构相关，故分 `x86`（amd64）与 `arm`（arm64）两个 `.fpk`。

## 本地复现

```bash
# 1. 下载上游二进制到 app/
curl -L -o fns.tar.gz \
  https://github.com/haierkeys/fast-note-sync-service/releases/download/3.5.1/fast-note-sync-service-3.5.1-linux-amd64.tar.gz
tar -xzf fns.tar.gz -C app/ --strip-components=1 ./fast-note-sync-service

# 2. （arm 构建）把 manifest 的 platform 改为 arm，并下载 linux-arm64 包

# 3. 用 fnpack 打包
fnpack build --directory .
```

## CI

`.github/workflows/build.yml` 在 `ubuntu-latest` 上矩阵构建 x86 / arm 两个包，产物作为 Release 资产发布。

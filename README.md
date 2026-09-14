# 本地开发工作区

根目录的 Git 仓库统一管理前端及后续后端代码，主分支为 main。

## 前端来源

上游：https://github.com/DanoAndHolidays/Mine.git
核对提交：bf7bf6ffe711a37c3083eeeaa234909299434d8c
完整上游克隆保存在 .local-tools/upstream（含原始 Git 历史，已忽略）。
现有 qianduan/src 与该提交一致；保留本地额外数据和工具文件。
根目录不设置指向前端仓库的 push remote，避免将整个工作区误推到前端仓库。

## 运行

在根目录 PowerShell 中执行：

```powershell
./frontend.ps1 install
./frontend.ps1 dev
```

访问 http://127.0.0.1:5173，按 Ctrl+C 停止。
生产构建：`./frontend.ps1 build`；预览：`./frontend.ps1 preview`（端口 4173）。
脚本优先使用已有 Node/pnpm，否则使用本机 Codex 已提供的运行时，不修改 PATH。
本次验证环境：Node 24.19.0、pnpm 11.19.0；使用 pnpm-lock.yaml 锁定依赖。
package-lock.json 为上游原文件，保留用于溯源，本工作区统一使用 pnpm。
依赖位于 qianduan/node_modules，缓存位于 .pnpm-store，构建位于 qianduan/dist。
端口被占用会明确报错，不会停止其他进程或自动切换端口。

## 后端开发

后续后端代码可放在根目录 backend/，Python 依赖使用该目录的 .venv。
前端当前以 public/data 和 public/models 的静态资源运行，不需要后端即可启动。
接入后端时将 qianduan/.env.example 复制为 qianduan/.env.local，启用并设置两个变量，然后重启：

```dotenv
VITE_APP_BASE_API=/api
VITE_HOST_URL=http://127.0.0.1:8000
```

代理会将 /api 前缀去除，例如 /api/health 转发为后端 /health。
该配置只提供开发代理，业务 API 调用仍需在后续开发中实现。
.env.local 不纳入 Git；不要在 VITE_ 变量中放秘密信息。

## 隔离与版本管理

未安装全局包，未修改系统 PATH 或全局 Git 配置。
.local-tools 中保留上游克隆、初始空 Git 元数据备份及本次收回的缓存。
首次提交使用 Codex Local Setup <codex@local.invalid> 标记自动初始化；后续请按需要设置仓库级提交身份。
生产构建通过；原有 Sass legacy-js-api 与 @import 弃用提示暂保留。

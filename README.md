# AI BatchPic

AI BatchPic 是一个批量 AI 生图工具，当前项目整理为桌面端和网页端双端结构。

## 目录结构

```text
AI_Batchpic/
├─ desktop_app/          # 桌面端 CustomTkinter 应用
│  ├─ main.py
│  ├─ config.py
│  ├─ core/
│  ├─ ui/
│  ├─ data/
│  └─ requirements.txt
├─ web_app/              # 网页端 Vue + Flask
│  ├─ frontend/
│  └─ backend/
├─ deploy/               # 服务器部署脚本
├─ .github/workflows/    # GitHub Actions 自动部署
├─ render.yaml           # Render 部署配置
└─ README.md
```

## 本地启动桌面端

```powershell
cd desktop_app
python main.py
```

或运行：

```powershell
.\start_desktop.bat
```

## 本地启动网页端

后端：

```powershell
cd web_app/backend
python run.py
```

前端开发模式：

```powershell
cd web_app/frontend
npm install
npm run dev
```

生产构建：

```powershell
cd web_app/frontend
npm install
npm run build
```

前端构建产物会输出到 `web_app/backend/app/static/`，由 Flask/Gunicorn 托管。

## 配置说明

不要把真实 API Key 提交到仓库。运行时可使用：

- `desktop_app/data/config.json` 本地配置文件
- 服务器上的 `/opt/ai-batchpic/.env`
- 系统环境变量

示例配置见 `desktop_app/data/config.example.json`。

## 云服务器部署

部署脚本位于 `deploy/server_deploy.sh`。服务器上可执行：

```bash
export REPO_URL=https://github.com/resign13/img.git
export APP_DIR=/opt/ai-batchpic
export DOMAIN_NAME=your-domain.example.com
bash deploy/server_deploy.sh
```

部署后会创建 systemd 服务 `ai-batchpic-web`，并通过 Nginx 反向代理到本机 `10000` 端口。

## GitHub 自动部署

`.github/workflows/deploy.yml` 会在推送 `main` 分支后通过 SSH 连接服务器，执行部署脚本。

需要在 GitHub 仓库 Settings -> Secrets and variables -> Actions 中配置：

- `SERVER_HOST`
- `SERVER_USER`
- `SERVER_PASSWORD`
- `SERVER_PORT`
- `APP_DIR`
- `REPO_URL`
- `DOMAIN_NAME`

详见 `deploy/README.md`。

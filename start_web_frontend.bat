@echo off
setlocal
cd /d "%~dp0"

if not exist "web_app\frontend\package.json" (
  echo [ERROR] 未找到前端项目: web_app\frontend\package.json
  pause
  exit /b 1
)

echo 正在启动网页前端...
cd /d "web_app\frontend"
call npm run dev

endlocal

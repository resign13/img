@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] 未找到项目虚拟环境: .venv\Scripts\python.exe
  pause
  exit /b 1
)

echo 正在启动网页后端...
".venv\Scripts\python.exe" "web_app\backend\run.py"

endlocal

@echo off
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" -m tools.game_update.update %*
if errorlevel 1 (
  echo 更新失败。原数据保留，日志位于 .cache\game_update。
) else (
  echo 更新完成，请重启主程序加载 game_data。
)
pause

@echo off
rem Windows: double-click. Starts the range agent and opens the Practice range page, already connected.
cd /d "%~dp0.."
if not exist site\dist\index.html (
  where npm >nul 2>nul && (echo Building the website once... & call npm --prefix site ci & call npm --prefix site run build)
)
python range\agent.py %*
if errorlevel 1 py -3 range\agent.py %*
pause

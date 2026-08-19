@echo off
setlocal

cd /d "%~dp0"

set "VENV_PY=%~dp0..\..\.venv\Scripts\python.exe"
set "DASHBOARD_URL=http://127.0.0.1:8000/"
set "PORT=8000"

if not exist "%VENV_PY%" goto ERR_VENV

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%PORT%.*LISTENING"') do goto OPEN_BROWSER

powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath '%VENV_PY%' -ArgumentList '-m uvicorn app:app --port %PORT%' -WorkingDirectory '%~dp0'"
powershell -NoProfile -Command "$deadline = (Get-Date).AddSeconds(10); while ((Get-Date) -lt $deadline) { try { $res = Invoke-WebRequest -Uri '%DASHBOARD_URL%' -UseBasicParsing -TimeoutSec 1; if ($res.StatusCode -ge 200) { exit 0 } } catch {} ; Start-Sleep -Milliseconds 500 }; exit 1"
if not errorlevel 1 goto OPEN_BROWSER
goto ERR_HEALTH

:OPEN_BROWSER
start "" "%DASHBOARD_URL%"
exit /b 0

:ERR_VENV
mshta vbscript:Execute("MsgBox ""仮想環境 .venv が見つかりません。リポジトリ直下で python -m venv .venv を実行し、README.md の手順で依存関係をインストールしてください。"", 48, ""ABM Dashboard 起動エラー"":close")
exit /b 1

:ERR_HEALTH
mshta vbscript:Execute("MsgBox ""サーバー起動後の応答確認に失敗しました。ポート 8000 の競合やセキュリティソフト設定をご確認ください。"", 48, ""ABM Dashboard 起動エラー"":close")
exit /b 1

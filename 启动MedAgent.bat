@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title MedAgent Startup

set "NO_PAUSE=0"
if /i "%~1"=="--no-pause" set "NO_PAUSE=1"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PROJECT=%ROOT%\1_core_orchestrator"
set "BACKEND=%PROJECT%\backend"
set "FRONTEND=%PROJECT%\frontend"
set "NGINX_EXE=%PROJECT%\tools\nginx\nginx-1.28.0\nginx.exe"
set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
set "UV_EXE=%LocalAppData%\Programs\Python\Python312\Scripts\uv.exe"

echo.
echo ======================================
echo   MedAgent Starting...
echo ======================================
echo.

if not exist "%PROJECT%" (
  echo [ERROR] Project path not found: %PROJECT%
  echo Put this script in the repository root folder.
  if "%NO_PAUSE%"=="0" pause
  exit /b 1
)

if not exist "%PYTHON_EXE%" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.12 first.
    if "%NO_PAUSE%"=="0" pause
    exit /b 1
  )
)

if not exist "%UV_EXE%" (
  echo [INFO] uv not found, installing...
  if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" -m pip install uv
  ) else (
    python -m pip install uv
  )
)

if not exist "%UV_EXE%" (
  echo [ERROR] uv installation failed. Check Python and pip.
  if "%NO_PAUSE%"=="0" pause
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js not found.
  if "%NO_PAUSE%"=="0" pause
  exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] pnpm not found. Run: npm i -g pnpm
  if "%NO_PAUSE%"=="0" pause
  exit /b 1
)

if not exist "%NGINX_EXE%" (
  echo [ERROR] Nginx not found: %NGINX_EXE%
  echo Put nginx.exe at: 1_core_orchestrator\tools\nginx\nginx-1.28.0\
  if "%NO_PAUSE%"=="0" pause
  exit /b 1
)

if not exist "%PROJECT%\logs" mkdir "%PROJECT%\logs"
if not exist "%PROJECT%\temp" mkdir "%PROJECT%\temp"
if not exist "%PROJECT%\temp\proxy_temp" mkdir "%PROJECT%\temp\proxy_temp"
if not exist "%PROJECT%\temp\fastcgi_temp" mkdir "%PROJECT%\temp\fastcgi_temp"
if not exist "%PROJECT%\temp\uwsgi_temp" mkdir "%PROJECT%\temp\uwsgi_temp"
if not exist "%PROJECT%\temp\scgi_temp" mkdir "%PROJECT%\temp\scgi_temp"
if not exist "%PROJECT%\temp\client_body_temp" mkdir "%PROJECT%\temp\client_body_temp"

if not exist "%FRONTEND%\.env" (
  echo [INFO] Creating frontend/.env for direct :3000 access...
  > "%FRONTEND%\.env" echo NEXT_PUBLIC_BACKEND_BASE_URL="http://localhost:8001"
  >> "%FRONTEND%\.env" echo NEXT_PUBLIC_LANGGRAPH_BASE_URL="http://localhost:2024"
)

findstr /r /c:"^SILICONFLOW_API_KEY=" "%PROJECT%\.env" >nul 2>nul
if errorlevel 1 (
  echo [WARN] SILICONFLOW_API_KEY not found in 1_core_orchestrator\.env
  echo       Gateway may fail to start.
)

if not exist "%BACKEND%\.venv\Scripts\python.exe" (
  echo [INFO] Installing backend dependencies via uv sync...
  cd /d "%BACKEND%"
  "%UV_EXE%" sync
)

if not exist "%FRONTEND%\node_modules" (
  echo [INFO] Installing frontend dependencies via pnpm install...
  cd /d "%FRONTEND%"
  pnpm install
)

echo [1/4] LangGraph Server :2024
call :is_port_listening 2024
if errorlevel 1 (
  start "MedAgent-LangGraph" cmd /k "cd /d ""%BACKEND%"" && ""%UV_EXE%"" run langgraph dev --no-browser --allow-blocking --server-log-level info --no-reload"
  timeout /t 2 /nobreak >nul
) else (
  echo [SKIP] Port 2024 already in use.
)

echo [2/4] Gateway API :8001
call :is_port_listening 8001
if errorlevel 1 (
  start "MedAgent-Gateway" cmd /k "cd /d ""%BACKEND%"" && set ""PYTHONPATH=."" && ""%UV_EXE%"" run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001"
  timeout /t 2 /nobreak >nul
) else (
  echo [SKIP] Port 8001 already in use.
)

echo [3/4] Frontend :3000
call :is_port_listening 3000
if errorlevel 1 (
  start "MedAgent-Frontend" cmd /k "cd /d ""%FRONTEND%"" && pnpm dev"
  timeout /t 2 /nobreak >nul
) else (
  echo [SKIP] Port 3000 already in use.
)

echo [4/4] Nginx :2026
call :is_port_listening 2026
if errorlevel 1 (
  start "MedAgent-Nginx" cmd /k "cd /d ""%PROJECT%"" && ""%NGINX_EXE%"" -g ""daemon off;"" -c ""docker/nginx/nginx.local.conf"" -p ""."""
) else (
  echo [SKIP] Port 2026 already in use.
)

echo.
echo ======================================
echo   MedAgent Started
echo ======================================
echo Frontend      : http://localhost:3000
echo Unified Entry : http://localhost:2026
echo Gateway API   : http://localhost:8001/health
echo LangGraph Docs: http://localhost:2024/docs
echo ======================================
echo.
if "%NO_PAUSE%"=="0" pause
exit /b 0

:is_port_listening
set "PORT=%~1"
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>nul
if errorlevel 1 (
  exit /b 1
) else (
  exit /b 0
)

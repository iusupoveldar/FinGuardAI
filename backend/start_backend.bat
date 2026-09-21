@echo off
setlocal
pushd "%~dp0" || exit /b 1

set "SKIP_DOCKER="
if /I "%~1"=="--no-docker" set "SKIP_DOCKER=1"
if not "%~1"=="" if not defined SKIP_DOCKER goto :usage

if not exist ".venv\Scripts\python.exe" (
    echo Run setup_backend.bat first.
    goto :fail
)
if not exist ".env" (
    echo backend\.env is missing. Run setup_backend.bat first.
    goto :fail
)

if not defined SKIP_DOCKER (
    echo Starting the local PostgreSQL container...
    docker compose up -d --wait database || goto :fail
)

echo Starting FastAPI at http://127.0.0.1:9000
echo Press Ctrl+C to stop the API.
".venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 9000
set "SERVER_EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %SERVER_EXIT_CODE%

:usage
echo Usage: start_backend.bat [--no-docker]
echo Use --no-docker when DATABASE_URL points to an already running PostgreSQL server.
popd
exit /b 2

:fail
popd
exit /b 1

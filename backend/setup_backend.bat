@echo off
setlocal
pushd "%~dp0" || exit /b 1

set "SKIP_DOCKER="
if /I "%~1"=="--no-docker" set "SKIP_DOCKER=1"
if not "%~1"=="" if not defined SKIP_DOCKER goto :usage

if not exist ".env" (
    copy ".env.example" ".env" >nul || goto :fail
    echo Created backend\.env with local database defaults.
)

if not exist ".venv\Scripts\python.exe" (
    call :create_venv || goto :fail
)

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
echo Installing backend dependencies...
"%VENV_PYTHON%" -m pip install -r requirements.txt || goto :fail
"%VENV_PYTHON%" -m pip install -e .. --no-deps || goto :fail

if not defined SKIP_DOCKER (
    echo Starting the local PostgreSQL container...
    docker compose up -d --wait database || goto :fail
)

echo Applying database migrations...
"%VENV_PYTHON%" -m scripts.create_tables || goto :fail
echo Importing the synthetic AMLSim data (safe to rerun)...
"%VENV_PYTHON%" -m data_gen.etl.import_amlsim || goto :fail

echo.
echo Backend setup is complete.
echo Run prepare_demo.bat to train, score, and index the demo data.
echo Run start_backend.bat to start the API.
popd
exit /b 0

:create_venv
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv ".venv"
    if errorlevel 1 exit /b 1
    exit /b 0
)
python -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 (
    python -m venv ".venv"
    if errorlevel 1 exit /b 1
    exit /b 0
)
echo Python 3.11 or newer is required. Install it and rerun this script.
exit /b 1

:usage
echo Usage: setup_backend.bat [--no-docker]
echo Use --no-docker when DATABASE_URL points to an already running PostgreSQL server.
popd
exit /b 2

:fail
echo Backend setup failed. Fix the error above, then rerun this script.
popd
exit /b 1

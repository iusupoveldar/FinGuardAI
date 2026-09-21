@echo off
setlocal
pushd "%~dp0" || exit /b 1

if /I "%~1"=="--help" goto :usage
if "%~1"=="" goto :usage
if not "%~2"=="" goto :usage
set "SPACE_ID=%~1"

for %%F in (
    Dockerfile
    .dockerignore
    README.md
    pyproject.toml
    backend\main.py
    backend\requirements-runtime.txt
    backend\how_to.md
    ai\__init__.py
    docs\hugging-face-backend-deployment.md
) do if not exist "%%F" (
    echo Missing required deployment file: %%F
    goto :fail
)
if not exist "backend\app" (
    echo Missing backend\app.
    goto :fail
)
if not exist "ai\documents" (
    echo Missing ai\documents.
    goto :fail
)

set "HF_CLI="
if exist "backend\.venv\Scripts\hf.exe" set "HF_CLI=%CD%\backend\.venv\Scripts\hf.exe"
if not defined HF_CLI (
    where hf >nul 2>&1 || goto :missing_cli
    set "HF_CLI=hf"
)

call "%HF_CLI%" auth whoami >nul 2>&1 || goto :missing_auth

echo Deploying the FinGuardAI API to %SPACE_ID%...
call "%HF_CLI%" upload "%SPACE_ID%" . . ^
    --repo-type=space ^
    --include="Dockerfile" ^
    --include=".dockerignore" ^
    --include="README.md" ^
    --include="pyproject.toml" ^
    --include="backend/app/**" ^
    --include="backend/main.py" ^
    --include="backend/requirements-runtime.txt" ^
    --include="backend/how_to.md" ^
    --include="ai/*.py" ^
    --include="ai/documents/**" ^
    --exclude="**/.env" ^
    --exclude="**/.env.*" ^
    --exclude="**/__pycache__/**" ^
    --exclude="**/*.pyc" ^
    --commit-message="Deploy FinGuardAI API"
if errorlevel 1 goto :fail

echo Upload complete. Check the Space build logs before using the API.
popd
exit /b 0

:missing_cli
echo Hugging Face CLI was not found. Install it with: pip install -U huggingface_hub
goto :fail

:missing_auth
echo Hugging Face login was not found. Run: hf auth login
goto :fail

:usage
echo Usage: deploy_huggingface.bat USERNAME/SPACE_NAME
echo Create a Docker Space and configure its DATABASE_URL secret before deploying.
popd
exit /b 2

:fail
echo Deployment did not complete.
popd
exit /b 1

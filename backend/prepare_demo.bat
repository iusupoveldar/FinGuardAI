@echo off
setlocal
pushd "%~dp0" || exit /b 1

if not exist ".venv\Scripts\python.exe" (
    echo Run setup_backend.bat first.
    goto :fail
)
if not exist ".env" (
    echo backend\.env is missing. Run setup_backend.bat first.
    goto :fail
)

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
echo Training the risk model from synthetic data...
"%VENV_PYTHON%" -m ml.train || goto :fail
echo Saving customer risk scores...
"%VENV_PYTHON%" -m ml.score || goto :fail
echo Building the synthetic policy search index...
"%VENV_PYTHON%" -m ai.ingestion || goto :fail

echo Demo scoring and policy retrieval are ready.
popd
exit /b 0

:fail
echo Demo preparation failed. Fix the error above, then rerun this script.
popd
exit /b 1

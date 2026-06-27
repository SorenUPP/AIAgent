@echo off
setlocal enabledelayedexpansion
title MedAgent - Starting...
color 0B

echo.
echo  ============================================
echo    MedAgent - AI Medical Data Assistant
echo  ============================================
echo.

cd /d "%~dp0"

:: ── Load paths saved by installer ────────────────────────────
set "PYTHON_CMD=python"
set "OLLAMA_CMD=ollama"
if exist "%~dp0medagent_env.bat" (
    call "%~dp0medagent_env.bat"
)

:: ── Verify python is usable ──────────────────────────────────
"%PYTHON_CMD%" --version >nul 2>&1
if %errorLevel% neq 0 (
    echo  [ERROR] Python not found. Please run INSTALL.bat first.
    pause & exit /b 1
)

:: ── Start Ollama in background if not running ────────────────
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if %errorLevel% neq 0 (
    echo  Starting Ollama AI engine...
    if exist "%OLLAMA_CMD%" (
        start /min "" "%OLLAMA_CMD%" serve
    ) else (
        start /min "" ollama serve
    )
    timeout /t 5 /nobreak >nul
) else (
    echo  Ollama already running.
)

:: ── Launch Streamlit app ─────────────────────────────────────
echo  Starting MedAgent...
echo  (A browser window will open automatically)
echo.
echo  To stop MedAgent, close this window.
echo.

timeout /t 2 /nobreak >nul
start "" http://localhost:8501
"%PYTHON_CMD%" -m streamlit run app.py --server.headless true --server.port 8501 --browser.gatherUsageStats false

echo.
echo  MedAgent has stopped.
pause

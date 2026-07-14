@echo off
setlocal enabledelayedexpansion
title MedAgent - Starting...
color 0B

echo.
echo  ============================================
echo    MedAgent - AI Medical Data Assistant
echo  ============================================
echo.

:: ── Start Ollama in background if not running ───────────────
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if %errorLevel% neq 0 (
    echo  Starting Ollama AI engine...
    start /min "" ollama serve
    :: Give it a few seconds to start
    timeout /t 4 /nobreak >nul
) else (
    echo  Ollama already running.
)

:: ── Launch Streamlit app ─────────────────────────────────────
echo  Starting MedAgent...
echo  (A browser window will open automatically)
echo.
echo  To stop MedAgent, close this window.
echo.

cd /d "%~dp0"
start "" http://localhost:8501
python -m streamlit run app.py --server.headless true --server.port 8501 --browser.gatherUsageStats false

:: If streamlit exits, keep window open so user can see any errors
echo.
echo  MedAgent has stopped.
pause

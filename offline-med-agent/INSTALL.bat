@echo off
setlocal enabledelayedexpansion
title MedAgent Installer
color 0B

echo.
echo  ============================================
echo    MedAgent - AI Medical Data Assistant
echo    Installer v1.1
echo  ============================================
echo.

:: ── Check for admin rights ──────────────────────────────────
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo  [!] Please right-click INSTALL.bat and choose
    echo      "Run as administrator"
    echo.
    pause
    exit /b 1
)

set "INSTALL_DIR=%~dp0"
set "LOG=%INSTALL_DIR%install_log.txt"
echo MedAgent Install Log > "%LOG%"
echo Started: %date% %time% >> "%LOG%"

:: ── [1/5] Python ─────────────────────────────────────────────
echo  [1/5] Checking Python...

set "PYTHON_CMD="

:: Check if python is already on PATH
python --version >nul 2>&1
if %errorLevel% equ 0 (
    set "PYTHON_CMD=python"
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  Found %%v
    echo  Python found on PATH >> "%LOG%"
    goto :python_ok
)

:: Check common install locations
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files\Python311\python.exe"
) do (
    if exist %%P (
        set "PYTHON_CMD=%%~P"
        echo  Found Python at %%P
        echo  Python found at %%P >> "%LOG%"
        goto :python_ok
    )
)

:: Python not found — download and install
echo  Python not found. Downloading Python 3.11.9...
echo  Python not found - downloading >> "%LOG%"
curl -L --progress-bar -o "%TEMP%\python_installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
if %errorLevel% neq 0 (
    echo  [ERROR] Failed to download Python. Check your internet connection.
    echo  Python download failed >> "%LOG%"
    pause & exit /b 1
)

echo  Installing Python 3.11.9 (this may take a minute)...
"%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1
if %errorLevel% neq 0 (
    echo  [ERROR] Python installation failed.
    echo  Python install failed >> "%LOG%"
    pause & exit /b 1
)
echo  Python installed OK >> "%LOG%"

:: After silent install, find the newly installed python
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "C:\Python311\python.exe"
    "C:\Program Files\Python311\python.exe"
) do (
    if exist %%P (
        set "PYTHON_CMD=%%~P"
        echo  Python installed at %%P
        goto :python_ok
    )
)

echo  [ERROR] Could not locate Python after install. Try restarting and running again.
pause & exit /b 1

:python_ok

:: ── [2/5] Python packages ────────────────────────────────────
echo.
echo  [2/5] Installing Python packages...
"%PYTHON_CMD%" -m pip install --upgrade pip --quiet >> "%LOG%" 2>&1
"%PYTHON_CMD%" -m pip install -r "%INSTALL_DIR%requirements.txt" --quiet >> "%LOG%" 2>&1
if %errorLevel% neq 0 (
    echo  [ERROR] Failed to install Python packages.
    echo  Check install_log.txt for details.
    echo  Pip install failed >> "%LOG%"
    pause & exit /b 1
)
echo  Packages installed OK >> "%LOG%"
echo  Done.

:: ── [3/5] Ollama ─────────────────────────────────────────────
echo.
echo  [3/5] Checking Ollama...

set "OLLAMA_CMD="

:: Check PATH first
ollama --version >nul 2>&1
if %errorLevel% equ 0 (
    set "OLLAMA_CMD=ollama"
    echo  Ollama already installed.
    echo  Ollama found on PATH >> "%LOG%"
    goto :ollama_ok
)

:: Check common install locations
for %%O in (
    "%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    "%ProgramFiles%\Ollama\ollama.exe"
    "%USERPROFILE%\AppData\Local\Programs\Ollama\ollama.exe"
) do (
    if exist %%O (
        set "OLLAMA_CMD=%%~O"
        echo  Found Ollama at %%O
        echo  Ollama found at %%O >> "%LOG%"
        goto :ollama_ok
    )
)

:: Ollama not found — download and install
echo  Ollama not found. Downloading...
echo  Ollama not found - downloading >> "%LOG%"
curl -L --progress-bar -o "%TEMP%\OllamaSetup.exe" "https://ollama.com/download/OllamaSetup.exe"
if %errorLevel% neq 0 (
    echo  [ERROR] Failed to download Ollama. Check your internet connection.
    echo  Ollama download failed >> "%LOG%"
    pause & exit /b 1
)

echo  Installing Ollama (silent)...
"%TEMP%\OllamaSetup.exe" /S
echo  Waiting for Ollama installer to finish...
timeout /t 15 /nobreak >nul
echo  Ollama installed OK >> "%LOG%"

:: Find ollama after install
for %%O in (
    "%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    "%ProgramFiles%\Ollama\ollama.exe"
    "%USERPROFILE%\AppData\Local\Programs\Ollama\ollama.exe"
) do (
    if exist %%O (
        set "OLLAMA_CMD=%%~O"
        echo  Ollama installed at %%O
        goto :ollama_ok
    )
)

echo  [WARN] Ollama installed but could not locate executable.
echo  You may need to restart your PC and run this installer again.
echo  Ollama not found after install >> "%LOG%"
goto :skip_model

:ollama_ok

:: ── [4/5] Download AI model ──────────────────────────────────
echo.
echo  [4/5] Downloading AI model (llama3 ~4 GB)...
echo  This only happens once. May take several minutes.
echo.

:: Start ollama serve in background so pull can connect
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if %errorLevel% neq 0 (
    start /min "" "%OLLAMA_CMD%" serve
    timeout /t 5 /nobreak >nul
)

"%OLLAMA_CMD%" pull llama3 >> "%LOG%" 2>&1
if %errorLevel% neq 0 (
    echo  [WARN] Could not pull llama3 automatically.
    echo  Run manually later:  ollama pull llama3
    echo  Ollama pull failed >> "%LOG%"
) else (
    echo  Model ready.
    echo  llama3 pulled OK >> "%LOG%"
)

:skip_model

:: ── [5/5] Desktop shortcut ───────────────────────────────────
echo.
echo  [5/5] Creating desktop shortcut...

set "SHORTCUT=%USERPROFILE%\Desktop\MedAgent.lnk"
set "TARGET=%INSTALL_DIR%Launch MedAgent.bat"

powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%SHORTCUT%'); ^
   $s.TargetPath = '%TARGET%'; ^
   $s.WorkingDirectory = '%INSTALL_DIR%'; ^
   $s.IconLocation = 'shell32.dll,13'; ^
   $s.Description = 'Launch MedAgent AI Medical Assistant'; ^
   $s.Save()" >> "%LOG%" 2>&1

echo  Shortcut created on Desktop.
echo  Shortcut created >> "%LOG%"

:: Save the resolved python path for Launch bat to use
echo set "MEDAGENT_PYTHON=%PYTHON_CMD%"> "%INSTALL_DIR%medagent_env.bat"
echo set "MEDAGENT_OLLAMA=%OLLAMA_CMD%">> "%INSTALL_DIR%medagent_env.bat"

echo.
echo  ============================================
echo    Installation complete!
echo  ============================================
echo.
echo  -> Double-click "MedAgent" on your Desktop to start.
echo  -> Or run "Launch MedAgent.bat" in this folder.
echo.
echo  First launch may take ~30 seconds while the AI warms up.
echo.
echo Install completed: %date% %time% >> "%LOG%"
pause

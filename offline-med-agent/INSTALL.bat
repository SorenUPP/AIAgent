@echo off
setlocal enabledelayedexpansion
title MedAgent Installer
color 0B

echo.
echo  ============================================
echo    MedAgent - AI Medical Data Assistant
echo    Installer v1.0
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

echo  [1/5] Checking Python...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo  Python not found. Downloading Python 3.11...
    echo  Python not found - downloading >> "%LOG%"
    curl -L -o "%TEMP%\python_installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    if %errorLevel% neq 0 (
        echo  [ERROR] Failed to download Python. Check your internet connection.
        pause & exit /b 1
    )
    echo  Installing Python (this may take a minute)...
    "%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1
    if %errorLevel% neq 0 (
        echo  [ERROR] Python installation failed.
        pause & exit /b 1
    )
    :: Refresh PATH
    call refreshenv >nul 2>&1
    set "PATH=%PATH%;C:\Program Files\Python311;C:\Program Files\Python311\Scripts"
    echo  Python installed OK >> "%LOG%"
) else (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  Found %%v
    echo  Python found >> "%LOG%"
)

echo.
echo  [2/5] Installing Python packages...
python -m pip install --upgrade pip --quiet >> "%LOG%" 2>&1
python -m pip install streamlit pandas openpyxl requests --quiet >> "%LOG%" 2>&1
if %errorLevel% neq 0 (
    echo  [ERROR] Failed to install Python packages.
    echo  Check install_log.txt for details.
    pause & exit /b 1
)
echo  Packages installed OK >> "%LOG%"
echo  Done.

echo.
echo  [3/5] Checking Ollama...
ollama --version >nul 2>&1
if %errorLevel% neq 0 (
    echo  Ollama not found. Downloading...
    echo  Ollama not found - downloading >> "%LOG%"
    curl -L -o "%TEMP%\ollama_installer.exe" "https://ollama.com/download/OllamaSetup.exe"
    if %errorLevel% neq 0 (
        echo  [ERROR] Failed to download Ollama. Check your internet connection.
        pause & exit /b 1
    )
    echo  Installing Ollama...
    "%TEMP%\ollama_installer.exe" /S
    :: Wait for install to finish
    timeout /t 10 /nobreak >nul
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama"
    echo  Ollama installed OK >> "%LOG%"
) else (
    echo  Ollama already installed.
    echo  Ollama found >> "%LOG%"
)

echo.
echo  [4/5] Downloading AI model (llama3 ~4GB)...
echo  This only happens once and may take several minutes.
echo  depending on your internet speed.
echo.
ollama pull llama3 >> "%LOG%" 2>&1
if %errorLevel% neq 0 (
    echo  [WARN] Could not pull llama3 automatically.
    echo  You can do it later by running: ollama pull llama3
    echo  Ollama pull failed >> "%LOG%"
) else (
    echo  Model ready.
    echo  llama3 pulled OK >> "%LOG%"
)

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

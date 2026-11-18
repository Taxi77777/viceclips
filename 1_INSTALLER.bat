@echo off
chcp 65001 >nul
title ViceClips - Installation
echo ==========================================
echo   ViceClips - Installation (gratuit)
echo ==========================================
echo.
echo [1/4] Python, FFmpeg et yt-dlp via winget...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
winget install -e --id yt-dlp.yt-dlp --accept-package-agreements --accept-source-agreements
echo.
echo [2/4] Recharge du PATH...
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "UP=%%b"
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SP=%%b"
set "PATH=%SP%;%UP%;%PATH%"
echo.
echo [3/4] Bibliotheques Python (transcription + traduction)...
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -U yt-dlp faster-whisper numpy argostranslate
echo.
echo [4/4] Modeles de traduction EN/ES/DE/FR (hors ligne)...
py -3.12 "%~dp0setup_traduction.py"
echo.
echo ==========================================
echo   Installation terminee !
echo   Etape suivante : double-clic sur 2_TESTER.bat
echo ==========================================
pause

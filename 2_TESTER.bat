@echo off
chcp 65001 >nul
title ViceClips - Test (1 cycle)
cd /d "%~dp0"
py -3.12 -m pip install -U yt-dlp >nul 2>&1
py -3.12 clipper.py
echo.
echo Regarde le dossier PRETS_A_PUBLIER. Si c'est bon : 3_LANCER_24H.bat
start "" "%~dp0PRETS_A_PUBLIER"
pause

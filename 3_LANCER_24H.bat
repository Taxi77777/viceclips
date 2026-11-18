@echo off
chcp 65001 >nul
title ViceClips - EN MARCHE 24h/24 (ne pas fermer)
cd /d "%~dp0"
:boucle
py -3.12 -m pip install -U yt-dlp >nul 2>&1
py -3.12 clipper.py --boucle
echo Redemarrage dans 60 s...
timeout /t 60 >nul
goto boucle

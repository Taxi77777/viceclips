@echo off
chcp 65001 >nul
title ViceClips - Relier les chaines YouTube
cd /d "%~dp0"
py -3.12 autoriser_youtube.py
if errorlevel 9009 python autoriser_youtube.py

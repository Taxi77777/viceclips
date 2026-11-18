@echo off
chcp 65001 >nul
title ViceClips - Demarrage automatique
echo Le bot se lancera tout seul a chaque ouverture de session Windows.
schtasks /Create /F /TN "ViceClips" /SC ONLOGON /RL LIMITED /TR "\"%~dp03_LANCER_24H.bat\""
echo.
echo Pour annuler : schtasks /Delete /TN "ViceClips" /F
echo Conseil : Parametres Windows ^> Alimentation ^> mise en veille = Jamais
pause

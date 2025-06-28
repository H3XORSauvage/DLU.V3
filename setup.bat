@echo off
title DLU V3 - Installation des dependances

echo ===================================================
echo.
echo  Installation des packages Python requis pour DLU V3
echo.
echo ===================================================
echo.

:: Verifie si pip est installe et accessible.
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] La commande 'pip' n'a pas ete trouvee.
    echo Assurez-vous que Python est installe et que son dossier 'Scripts' est ajoute a votre PATH.
    goto :end
)

echo Installation de la bibliotheque pour le glisser-deposer (tkinterdnd2-universal)...
pip install tkinterdnd2-universal

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] L'installation a echoue. Verifiez votre connexion internet ou les messages d'erreur ci-dessus.
) else (
    echo.
    echo Installation terminee avec succes!
)

:end
echo.
echo Appuyez sur n'importe quelle touche pour fermer cette fenetre.
pause >nul
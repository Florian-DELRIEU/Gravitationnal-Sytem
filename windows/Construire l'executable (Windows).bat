@echo off
rem Construit l'application autonome "Simulateur Gravitationnel" (aucun Python a installer pour l'utiliser).
rem A lancer SOUS WINDOWS. Prerequis : l'environnement conda "gravsim" ("Installer (Windows).bat").
rem Resultat : dist\Simulateur Gravitationnel\Simulateur Gravitationnel.exe  (copier le dossier en entier)
setlocal
cd /d "%~dp0.."
set "ENVNAME=gravsim"
set "PY="
for %%D in ("%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\miniconda3" "%LOCALAPPDATA%\anaconda3" "%ProgramData%\miniconda3" "%ProgramData%\anaconda3" "%USERPROFILE%\miniforge3" "%USERPROFILE%\mambaforge") do (
  if exist "%%~D\envs\%ENVNAME%\python.exe" if not defined PY set "PY=%%~D\envs\%ENVNAME%\python.exe"
)
if not defined PY (
  echo Environnement conda "%ENVNAME%" introuvable. Lancez d'abord "Installer (Windows).bat".
  pause
  exit /b 1
)
echo Installation de PyInstaller (si besoin)...
"%PY%" -m pip install -e ".[gui,build]"
if errorlevel 1 (
  echo Echec de l'installation des dependances.
  pause
  exit /b 1
)
echo.
echo Construction (quelques minutes)...
"%PY%" scripts\construire_executable.py
if errorlevel 1 (
  echo Echec de la construction.
  pause
  exit /b 1
)
echo.
echo Termine. Ouverture du dossier dist...
start "" explorer "%CD%\dist"
pause

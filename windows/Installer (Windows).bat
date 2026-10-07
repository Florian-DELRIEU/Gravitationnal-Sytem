@echo off
rem Cree l'environnement conda "gravsim" et installe le simulateur. A faire une seule fois.
setlocal
cd /d "%~dp0.."
where conda >nul 2>nul
if errorlevel 1 (
  echo conda est introuvable dans le PATH.
  echo Ouvrez "Anaconda Prompt" ou "Miniconda Prompt", puis relancez ce fichier depuis cette fenetre,
  echo ou installez Miniconda : https://docs.conda.io/en/latest/miniconda.html
  pause
  exit /b 1
)
call conda env create -f environment.yml
if errorlevel 1 (
  echo.
  echo L'environnement existe peut-etre deja. Mise a jour...
  call conda env update -f environment.yml --prune
)
echo.
echo Installation terminee. Double-cliquez sur "windows\Lancer le simulateur.bat".
pause

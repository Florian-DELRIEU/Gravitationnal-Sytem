@echo off
rem Lance le simulateur avec l'environnement conda "gravsim" (sans console).
rem Prerequis : avoir execute "Installer (Windows).bat" une fois.
setlocal
set "ENVNAME=gravsim"
for %%D in ("%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\miniconda3" "%LOCALAPPDATA%\anaconda3" "%ProgramData%\miniconda3" "%ProgramData%\anaconda3" "%USERPROFILE%\miniforge3" "%USERPROFILE%\mambaforge") do (
  if exist "%%~D\envs\%ENVNAME%\pythonw.exe" (
    start "" "%%~D\envs\%ENVNAME%\pythonw.exe" -m gravsim
    exit /b 0
  )
)
echo Environnement conda "%ENVNAME%" introuvable.
echo Lancez d'abord "Installer (Windows).bat" (conda / Miniconda doit etre installe).
pause

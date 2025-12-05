@echo off
TITLE Pandora Mission Control (Local Mode)

echo ========================================
echo      A INICIAR SISTEMA (LOCALHOST)
echo ========================================

cd src

echo 1. A iniciar Nave-Mae...
start "NAVE-MAE" cmd /k "python navemae.py"

timeout /t 2 /nobreak >nul

echo 2. A lancar Frota (Forcando IP Local)...
REM Passamos "127.0.0.1" como segundo argumento para sobrescrever o default CORE
start "Rover-1" cmd /k "python rover_autonomo.py 1 127.0.0.1"
start "Rover-2" cmd /k "python rover_autonomo.py 2 127.0.0.1"
start "Rover-3" cmd /k "python rover_autonomo.py 3 127.0.0.1"

echo 3. A abrir Dashboards...
cd ..\web
start navemae.html
start groundcontrol.html

echo ========================================
echo      PRONTO
echo ========================================
pause
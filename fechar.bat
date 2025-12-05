@echo off
:: Isto fecha os processos python abertos no pc

echo ================================================
echo          A TERMINAR TODAS AS MISSOES
echo ================================================

echo.
echo 1. A matar processos da Nave-Mae e Rovers...
taskkill /F /IM python.exe /T

echo.
echo 2. A garantir que as portas (4444, 5555, 6000+) ficam livres...
timeout /t 1 /nobreak >nul

echo.
echo ================================================
echo              LIMPEZA CONCLUIDA. 
echo ================================================
pause
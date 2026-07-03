@echo off
title Rulez Anti-DDoS...
color 0B

:: Verificăm dacă avem drepturi de Administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    :: Dacă suntem Admin, mergem mai departe
    goto :START_SCRIPT
) else (
    :: Dacă nu suntem Admin, cerem permisiunea UAC
    echo [*] Se solicita drepturi de Administrator...
    powershell -Command "Start-Process cmd -ArgumentList '/c %~fnx0' -Verb RunAs"
    exit /b
)

:START_SCRIPT
cd /d "%~dp0"
echo [OK] Drepturi de Administrator confirmate.
echo.

:: Verificăm dacă există mediul virtual
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [*] Pornire sistem Anti-DDoS...
    python anti_ddos.py
) else (
    echo [EROARE] Nu am gasit venv. Ruleaza intai install_windows.bat
)

pause
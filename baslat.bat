@echo off
chcp 65001 >nul
title YouTube Muzik - app.articnc.online/muzik

echo.
echo ====================================================
echo   app.articnc.online/muzik baslatiliyor
echo ====================================================
echo.

:: Eski process'leri temizle
echo [1/4] Eski process'ler kapatiliyor...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5051 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 1 /nobreak >nul

:: Muzik app - port 5051
echo [2/4] Muzik servisi baslatiliyor (port 5051)...
start "YouTube Muzik :5051" /MIN C:\visualdeneme\.venv\Scripts\python.exe "%~dp0app.py"
timeout /t 3 /nobreak >nul

:: Ana Flask - port 5000 (proxy blueprint icin gerekli)
echo [3/4] Ana Flask baslatiliyor (port 5000)...
start "Ana Flask :5000" /MIN C:\visualdeneme\.venv\Scripts\python.exe "d:\yazilimyedekler\visualdeneme15\basit_hesap_makinesi.py"
timeout /t 5 /nobreak >nul

:: Cloudflare Tunnel
echo [4/4] Tunnel baslatiliyor...
echo.
echo =^=^> https://app.articnc.online/muzik
echo.
"d:\yazilimyedekler\visualdeneme15\cloudflared.exe" tunnel --config "C:\Users\aytek\.cloudflared\config.yml" run

echo.
echo Tunnel kapandi. Pencereyi kapatabilirsiniz.
pause

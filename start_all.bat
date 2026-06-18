@echo off
echo ========================================
echo   Ad Compliance Agent - Starting...
echo ========================================
echo.
echo [1/2] Starting Backend on port 8000...
start "Backend" cmd /c "cd /d D:\Desktop\黑客松 && python -m uvicorn backend.main:app --reload --port 8000"
timeout /t 3 /nobreak >nul
echo [2/2] Starting Frontend on port 3000...
start "Frontend" cmd /c "cd /d D:\Desktop\黑客松\frontend && npm run dev"
echo.
echo Both services starting...
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Press any key to stop all services...
pause >nul
taskkill /FI "WindowTitle eq Backend*" /F >nul 2>&1
taskkill /FI "WindowTitle eq Frontend*" /F >nul 2>&1
echo Services stopped.

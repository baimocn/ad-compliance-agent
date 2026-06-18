@echo off
echo Starting Ad Compliance Agent Backend...
cd /d D:\Desktop\黑客松
python -m uvicorn backend.main:app --reload --port 8000
pause

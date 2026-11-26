@echo off
set PYTHONPATH=D:\PY-IS\maps-gui\.qa\run5\mut;D:\PY-IS\maps-gui
set QA_MUT_ROOT=D:\PY-IS\maps-gui\.qa\run5\mut
D:\PY-IS\maps-gui\.venv\Scripts\python.exe D:\PY-IS\maps-gui\.qa\run5\mut\tests\test_radar_physics.py >nul 2>&1 || exit /b 1
D:\PY-IS\maps-gui\.venv\Scripts\python.exe D:\PY-IS\maps-gui\.qa\run5\tests\test_r5_radar_algorithmic.py >nul 2>&1 || exit /b 1
exit /b 0

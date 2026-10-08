@echo off
cd /d "%~dp0"
uv run "step by step/0_run_all.py" || pause

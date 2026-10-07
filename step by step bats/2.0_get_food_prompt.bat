@echo off
cd /d "%~dp0.."
uv run "step by step/%~n0.py" || pause
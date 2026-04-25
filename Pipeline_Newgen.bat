@echo off
title Pipeline Newgen Rev1
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
python -m pipeline_newgen_rev1.cli launch-config-gui
pause

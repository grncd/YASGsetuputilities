@echo off
set "BAT_DIR=%~dp0"
set "SYRICS_EXE=%BAT_DIR%venv\Scripts\syrics.exe"

cd %2
"%SYRICS_EXE%" %1

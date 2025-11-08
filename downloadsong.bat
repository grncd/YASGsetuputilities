@echo off
set "BAT_DIR=%~dp0"
set "SPOTDL_EXE=%BAT_DIR%venv\Scripts\spotdl.exe"

cd %2
"%SPOTDL_EXE%" %1 --ffmpeg "C:\Program Files\FFmpeg\bin\ffmpeg.exe"




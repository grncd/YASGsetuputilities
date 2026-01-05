@echo off
set "BAT_DIR=%~dp0"
set "SPOTDL_EXE=%BAT_DIR%venv\Scripts\spotdl.exe"

set "FFMPEG_PATH=%BAT_DIR%vocalremover\ffmpeg_lib\ffmpeg.exe"

cd %2
"%SPOTDL_EXE%" %1 --ffmpeg "%FFMPEG_PATH%"
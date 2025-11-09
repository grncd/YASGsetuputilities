@echo off
set "BAT_DIR=%~dp0"
set "SPOTDL_EXE=%BAT_DIR%venv\Scripts\spotdl.exe"

if exist "C:\Program Files\FFmpeg\bin\ffmpeg.exe" (
    set "FFMPEG_PATH=C:\Program Files\FFmpeg\bin\ffmpeg.exe"
) else (
    set "FFMPEG_PATH=C:\Users\%USERNAME%\AppData\Local\Programs\FFmpeg\bin\ffmpeg.exe"
)

cd %2
"%SPOTDL_EXE%" %1 --ffmpeg "%FFMPEG_PATH%"
@echo off
echo ============================================================
echo   Transient Marker Maker - Installer
echo ============================================================
echo.

:: Install Python dependencies
echo Installing Python dependencies...
pip install numpy scipy soundfile demucs
echo.

:: Ask about GPU
set /p GPU="Do you have an NVIDIA GPU? (y/n): "
if /i "%GPU%"=="y" (
    echo Installing PyTorch with CUDA support...
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
) else (
    echo Installing PyTorch (CPU only)...
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
)
echo.

:: Copy script to Resolve's Scripts folder
set RESOLVE_SCRIPTS=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility
echo.
echo Installing script to Resolve...
echo   Target: %RESOLVE_SCRIPTS%

if not exist "%RESOLVE_SCRIPTS%" (
    mkdir "%RESOLVE_SCRIPTS%"
    echo   Created Utility folder.
)

copy /Y "Transient Marker Maker.py" "%RESOLVE_SCRIPTS%\Transient Marker Maker.py"
echo   Script copied.

echo.
echo ============================================================
echo   Installation complete!
echo.
echo   1. Open DaVinci Resolve
echo   2. Go to: Preferences ^> General
echo   3. Set "External scripting using" to "Local"
echo   4. Restart Resolve
echo   5. Find it at: Workspace ^> Scripts ^> Transient Marker Maker
echo ============================================================
echo.
pause

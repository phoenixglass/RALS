@echo off
REM Build script for RALS executable (Windows)

echo ============================================================
echo RALS Executable Builder (Windows)
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.
    exit /b 1
)

REM Check if PyInstaller is installed
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Clean previous builds
echo Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build executable
echo Building executable with PyInstaller...
echo This may take several minutes...
echo.
pyinstaller rals.spec --clean

REM Check result
if exist "dist\RALS.exe" (
    echo.
    echo Build completed successfully!
    echo Executable created: dist\RALS.exe
    echo.
    echo Next steps:
    echo 1. Test the executable: dist\RALS.exe
    echo 2. Distribute the file: dist\RALS.exe
    echo 3. Users can double-click to launch the GUI
) else (
    echo.
    echo Build failed! Check the output above for errors.
    exit /b 1
)

echo.
echo ============================================================
echo Build process completed!
echo ============================================================

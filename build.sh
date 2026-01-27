#!/bin/bash
# Build script for RALS executable (Linux/macOS)

set -e  # Exit on error

echo "============================================================"
echo "RALS Executable Builder (Shell Script)"
echo "============================================================"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

# Check if PyInstaller is installed
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "PyInstaller not found. Installing..."
    pip3 install pyinstaller
fi

# Clean previous builds
echo "Cleaning previous build artifacts..."
rm -rf build/ dist/

# Build executable
echo "Building executable with PyInstaller..."
echo "This may take several minutes..."
pyinstaller rals.spec --clean

# Check result
if [ -f "dist/RALS" ]; then
    SIZE=$(du -h dist/RALS | cut -f1)
    echo ""
    echo "✓ Build completed successfully!"
    echo "✓ Executable created: dist/RALS"
    echo "  Size: $SIZE"
    echo ""
    echo "Next steps:"
    echo "1. Test the executable: ./dist/RALS"
    echo "2. Distribute the file: dist/RALS"
    echo "3. Users can run it by double-clicking or from terminal"
elif [ -d "dist/RALS.app" ]; then
    SIZE=$(du -sh dist/RALS.app | cut -f1)
    echo ""
    echo "✓ Build completed successfully!"
    echo "✓ Application bundle created: dist/RALS.app"
    echo "  Size: $SIZE"
    echo ""
    echo "Next steps:"
    echo "1. Test the app: open dist/RALS.app"
    echo "2. Distribute the app bundle: dist/RALS.app"
else
    echo ""
    echo "✗ Build failed! Check the output above for errors."
    exit 1
fi

echo ""
echo "============================================================"
echo "Build process completed!"
echo "============================================================"

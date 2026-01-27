#!/usr/bin/env python3
"""
Build script for creating RALS executable.

This script automates the process of building a standalone executable
from the RALS application using PyInstaller.
"""

import sys
import subprocess
import shutil
from pathlib import Path


def check_requirements():
    """Check if required packages are installed."""
    print("Checking requirements...")
    
    required_packages = [
        'pyinstaller',
        'openpyxl',
        'pandas',
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} (missing)")
            missing.append(package)
    
    if missing:
        print("\nMissing packages. Install with:")
        print(f"  pip install {' '.join(missing)}")
        return False
    
    return True


def clean_build():
    """Clean previous build artifacts."""
    print("\nCleaning previous build artifacts...")
    
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"  Removing {dir_name}/")
            shutil.rmtree(dir_path)
    
    # Clean .spec generated files
    for spec_file in Path('.').glob('*.spec~'):
        print(f"  Removing {spec_file}")
        spec_file.unlink()


def build_executable():
    """Build the executable using PyInstaller."""
    print("\nBuilding executable with PyInstaller...")
    print("This may take several minutes...\n")
    
    # Run PyInstaller with the spec file
    result = subprocess.run(
        ['pyinstaller', 'rals.spec', '--clean'],
        capture_output=False
    )
    
    if result.returncode != 0:
        print("\n✗ Build failed!")
        return False
    
    print("\n✓ Build completed successfully!")
    return True


def get_executable_path():
    """Get the path to the built executable."""
    dist_dir = Path('dist')
    
    if sys.platform == 'win32':
        exe_path = dist_dir / 'RALS.exe'
    elif sys.platform == 'darwin':
        exe_path = dist_dir / 'RALS.app'
    else:
        exe_path = dist_dir / 'RALS'
    
    return exe_path


def show_results():
    """Show build results and next steps."""
    exe_path = get_executable_path()
    
    if not exe_path.exists():
        print("\n⚠ Warning: Executable not found at expected location!")
        print(f"   Expected: {exe_path}")
        return
    
    # Get file size
    if exe_path.is_file():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n✓ Executable created: {exe_path}")
        print(f"  Size: {size_mb:.1f} MB")
    else:
        print(f"\n✓ Application bundle created: {exe_path}")
    
    print("\nNext steps:")
    print("1. Test the executable by running it")
    print(f"2. Distribute the file: {exe_path}")
    print("3. Users can double-click to launch the GUI")


def main():
    """Main build process."""
    print("=" * 60)
    print("RALS Executable Builder")
    print("=" * 60)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Clean previous builds
    clean_build()
    
    # Build executable
    if not build_executable():
        sys.exit(1)
    
    # Show results
    show_results()
    
    print("\n" + "=" * 60)
    print("Build process completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

"""PyInstaller build script for Agent Zero Companion.

Builds a standalone executable for the current platform.

Usage:
    python build.py              # Build for current platform
    python build.py --onefile    # Single executable (larger, slower start)
    python build.py --debug      # Debug build with console window
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
ASSETS_DIR = ROOT / "assets"


def ensure_icon():
    """Generate icon if it doesn't exist."""
    icon_png = ASSETS_DIR / "icon.png"
    if not icon_png.exists():
        print("Generating icon...")
        subprocess.run([sys.executable, str(ROOT / "create_icon.py")], check=True)


def get_icon_path() -> str:
    """Get platform-appropriate icon path."""
    system = platform.system()
    if system == "Windows":
        ico = ASSETS_DIR / "icon.ico"
        return str(ico) if ico.exists() else str(ASSETS_DIR / "icon.png")
    elif system == "Darwin":
        icns = ASSETS_DIR / "icon.icns"
        return str(icns) if icns.exists() else str(ASSETS_DIR / "icon.png")
    else:
        return str(ASSETS_DIR / "icon.png")


def build(onefile: bool = False, debug: bool = False):
    """Run PyInstaller to build the executable."""
    ensure_icon()

    system = platform.system()
    print(f"Building for {system} ({platform.machine()})")

    # Base PyInstaller arguments
    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", "agent-zero-companion",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
        "--clean",
        "--noconfirm",
    ]

    # Single file vs directory
    if onefile:
        args.append("--onefile")
    else:
        args.append("--onedir")

    # Console window
    if not debug:
        args.append("--noconsole")

    # Icon
    icon_path = get_icon_path()
    if os.path.exists(icon_path):
        args.extend(["--icon", icon_path])

    # Add data files
    sep = ";" if system == "Windows" else ":"
    args.extend([
        "--add-data", f"{ASSETS_DIR}{sep}assets",
    ])

    # Hidden imports (modules that PyInstaller might miss)
    hidden_imports = [
        "PyQt6.QtCore",
        "PyQt6.QtWidgets",
        "PyQt6.QtGui",
        "pystray._win32",
        "pystray._darwin",
        "pystray._xorg",
        "pynput.keyboard._win32",
        "pynput.keyboard._darwin",
        "pynput.keyboard._xorg",
        "pynput.mouse._win32",
        "pynput.mouse._darwin",
        "pynput.mouse._xorg",
        "PIL._tkinter_finder",
        "sounddevice",
        "soundfile",
        "httpx",
        "edge_tts",
    ]
    for imp in hidden_imports:
        args.extend(["--hidden-import", imp])

    # macOS specific
    if system == "Darwin":
        args.extend([
            "--osx-bundle-identifier", "com.agentzero.companion",
        ])

    # Main script
    args.append(str(ROOT / "main.py"))

    print("Running PyInstaller...")
    print(" ".join(args))
    result = subprocess.run(args)

    if result.returncode == 0:
        print(f"\n✅ Build successful!")
        if onefile:
            exe_name = "agent-zero-companion"
            if system == "Windows":
                exe_name += ".exe"
            print(f"   Executable: {DIST_DIR / exe_name}")
        else:
            print(f"   Output directory: {DIST_DIR / 'agent-zero-companion'}")
    else:
        print(f"\n❌ Build failed with exit code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Agent Zero Companion")
    parser.add_argument("--onefile", action="store_true",
                        help="Build as single executable")
    parser.add_argument("--debug", action="store_true",
                        help="Debug build (show console window)")
    args = parser.parse_args()

    build(onefile=args.onefile, debug=args.debug)

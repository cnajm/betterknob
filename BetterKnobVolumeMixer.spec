# -*- mode: python ; coding: utf-8 -*-
import tomllib
import os
import sys

def get_version():
    try:
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
            return data["project"]["version"]
    except Exception as e:
        print(f"Error reading pyproject.toml: {e}")
        sys.exit(1)

version = get_version()
print(f"Version found: {version}")

# Create version file in spec directory
version_file = os.path.join(SPECPATH, 'version.dat')

try:
    # Ensure directory exists
    os.makedirs(os.path.dirname(version_file), exist_ok=True)
    
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(version)
    
    # Verify file was created
    if not os.path.exists(version_file):
        raise FileNotFoundError(f"Failed to create {version_file}")
    print(f"Successfully created version file")
except Exception as e:
    print(f"Error creating version file: {e}")
    sys.exit(1)

a = Analysis(
    ['src\\keyb.py'],
    pathex=[],
    binaries=[],
    datas=[(version_file, '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BetterKnobVolumeMixer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)

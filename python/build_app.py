#!/usr/bin/env python3
"""
Build Script for FTID Label Generator
Compiles the application into standalone executables for different platforms.
All source code is compiled into bytecode and bundled into a single encrypted executable.
"""

import os
import sys
import subprocess
import shutil
import platform
import secrets
import string
import argparse

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Print a styled header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def generate_encryption_key():
    """Generate a random encryption key for PyInstaller"""
    # Generate a 16-character key for AES encryption
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(16))


def check_dependencies():
    """Check and install required dependencies"""
    dependencies = [
        ('pyinstaller', 'pyinstaller'),
    ]
    
    print_info("Checking dependencies...")
    
    for module, pip_name in dependencies:
        try:
            __import__(module.replace('-', '_'))
            print_success(f"{module} is installed")
        except ImportError:
            print_warning(f"{module} not found. Installing...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print_success(f"{module} installed successfully")
            except subprocess.CalledProcessError:
                print_error(f"Failed to install {module}")
                return False
    return True


def get_data_files_spec():
    """Generate the data files specification for the spec file"""
    return '''
added_files = []

# Add directories (with all contents)
directories = [
    ('ftid_gen', 'ftid_gen'),
    ('user_tracking', 'user_tracking'),
    ('requirements', 'requirements'),
    ('maxicode', 'maxicode'),
    ('barcodes', 'barcodes'),
    ('complete', 'complete'),
    ('progress', 'progress'),
]

for src, dest in directories:
    if os.path.exists(src):
        for root, dirs, files in os.walk(src):
            # Skip __pycache__ directories
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for file in files:
                # Skip .pyc files
                if not file.endswith('.pyc'):
                    file_path = os.path.join(root, file)
                    dest_path = os.path.dirname(file_path)
                    added_files.append((file_path, dest_path))

# Add individual files from root
root_files = [
    'ftid_data.json',
    'ftid_settings.json', 
    'previous_maxicode.json',
    '.encryption.key',
    '.env',
]

for file in root_files:
    if os.path.exists(file):
        added_files.append((file, '.'))
'''


def create_spec_file(target_platform, app_name="FTID_Generator", encryption_key=None, entry_point="main.py", gui_mode=False):
    """Create a PyInstaller spec file"""
    
    # Determine target architecture
    if target_platform == 'mac-universal':
        target_arch = "'universal2'"
    elif target_platform == 'mac-arm':
        target_arch = "'arm64'"
    elif target_platform == 'mac-intel':
        target_arch = "'x86_64'"
    else:
        target_arch = "None"
    
    # Console setting - False for GUI apps
    console_mode = "False" if gui_mode else "True"
    
    # Additional imports for GUI mode
    gui_imports = """
        # GUI dependencies
        'customtkinter',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',""" if gui_mode else ""
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# FTID Generator Build Spec - {target_platform} ({'GUI' if gui_mode else 'Terminal'})
# Generated automatically - DO NOT EDIT

import os

block_cipher = None

{get_data_files_spec()}

a = Analysis(
    ['{entry_point}'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        # Core dependencies
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.PngImagePlugin',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        # Barcode libraries
        'barcode',
        'barcode.writer',
        'barcode.codex',
        'barcode.code128',
        # Google Sheets
        'gspread',
        'oauth2client',
        'oauth2client.service_account',
        # Data processing
        'pandas',
        'openpyxl',
        'requests',
        'pydash',
        # Image/PDF
        'img2pdf',
        'pyperclipimg',
        # Environment
        'dotenv',
        # MaxiCode - zint is optional (may have arch issues)
        # 'zint',{gui_imports}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{app_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip debug symbols
    upx=True,    # Compress with UPX
    upx_exclude=[],
    console={console_mode},
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch={target_arch},
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)
'''
    
    spec_file = f"{app_name}_{target_platform}.spec"
    with open(spec_file, 'w') as f:
        f.write(spec_content)
    
    print_success(f"Created spec file: {spec_file}")
    return spec_file


def build_app(target_platform, encrypt=True, gui_mode=False):
    """Build the application for the specified platform"""
    
    current_platform = platform.system().lower()
    current_arch = platform.machine().lower()
    
    mode_name = "GUI" if gui_mode else "Terminal"
    print_header(f"Building {mode_name} App for {target_platform.upper()}")
    
    # Validation
    if target_platform == 'windows' and current_platform != 'windows':
        print_error("Windows builds must be run on Windows")
        print_info("You'll need to run this script on a Windows machine")
        return False
    
    if target_platform.startswith('mac') and current_platform != 'darwin':
        print_error("macOS builds must be run on macOS")
        return False
    
    # Universal builds require macOS 11+ and Apple Silicon or Intel with lipo
    if target_platform == 'mac-universal':
        print_warning("Universal builds require a Python installation with both Intel and ARM binaries")
        print_info("Your Homebrew Python is ARM-only. Falling back to ARM build...")
        print_info("(ARM binaries work on all Apple Silicon Macs)")
        target_platform = 'mac-arm'
    
    # Code is compiled to bytecode and bundled (not easily readable)
    print_info("Code will be compiled and bundled (source not visible)")
    
    # Create spec file
    if gui_mode:
        app_name = "FTID_Generator_GUI"
        entry_point = "gui_app.py"
    else:
        app_name = "FTID_Generator"
        entry_point = "main.py"
    
    spec_file = create_spec_file(target_platform, app_name, entry_point=entry_point, gui_mode=gui_mode)
    
    # Build command
    print_info("Starting PyInstaller build...")
    print_info("This may take a few minutes...")
    
    try:
        # Clean previous builds
        dist_dir = f'dist/{app_name}_{target_platform}'
        build_dir = f'build/{app_name}_{target_platform}'
        
        for dir_path in [dist_dir, build_dir]:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
        
        # Run PyInstaller
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--clean',
            '--noconfirm',
            f'--distpath=dist/{app_name}_{target_platform}',
            f'--workpath=build/{app_name}_{target_platform}',
            '--log-level=WARN',
            spec_file
        ]
        
        print_info(f"Running PyInstaller...")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print_error("Build failed!")
            print_error(result.stderr[-2000:] if result.stderr else "No error details")
            return False
        
        print_success("Build completed successfully!")
        
        # Show the output location
        if target_platform.startswith('mac'):
            exe_name = app_name
            output_path = os.path.join('dist', f'{app_name}_{target_platform}', exe_name)
            
            # Make executable
            if os.path.exists(output_path):
                os.chmod(output_path, 0o755)
                print_success(f"Executable: {output_path}")
                
                # Get file size
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                print_info(f"Size: {size_mb:.1f} MB")
        else:
            exe_name = f"{app_name}.exe"
            output_path = os.path.join('dist', f'{app_name}_{target_platform}', exe_name)
            if os.path.exists(output_path):
                print_success(f"Executable: {output_path}")
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                print_info(f"Size: {size_mb:.1f} MB")
        
        # Create zip for distribution
        try:
            archive_name = f"{app_name}_{target_platform}"
            archive_path = f'dist/{archive_name}.zip'
            
            # Remove old archive if exists
            if os.path.exists(archive_path):
                os.remove(archive_path)
            
            print_info("Creating distribution archive...")
            shutil.make_archive(
                f'dist/{archive_name}',
                'zip',
                f'dist/{app_name}_{target_platform}'
            )
            
            zip_size = os.path.getsize(archive_path) / (1024 * 1024)
            print_success(f"Archive: {archive_path} ({zip_size:.1f} MB)")
            
        except Exception as e:
            print_warning(f"Could not create archive: {e}")
        
        # Clean up spec file
        if os.path.exists(spec_file):
            os.remove(spec_file)
        
        return True
        
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_menu():
    """Show the build menu and get user selection"""
    print_header("FTID Generator - Build Script")
    
    print("This script creates standalone executable applications")
    print("with all source code compiled and hidden from users.")
    print()
    
    current_os = platform.system()
    current_arch = platform.machine()
    print_info(f"Current platform: {current_os} {current_arch}")
    print()
    
    print("Select build type:")
    print()
    
    if current_os == 'Darwin':
        print("  Terminal Apps:")
        print("    1. macOS ARM (Apple Silicon)")
        print("    2. macOS Intel (x86_64 via Rosetta)")
        print("    3. macOS Universal (ARM + Intel)")
        print()
        print("  GUI Apps (Beautiful native interface):")
        print("    4. GUI - macOS ARM")
        print("    5. GUI - macOS Intel")
        print("    6. GUI - macOS Universal")
        print()
        print("  Note: ARM apps run on Intel Macs via Rosetta 2")
    elif current_os == 'Windows':
        print("  1. Terminal App (Windows x64)")
        print("  2. GUI App (Windows x64)")
    else:
        print("  Linux builds not currently supported")
    
    print()
    print("  0. Exit")
    print()


def parse_args():
    """Parse command-line arguments for non-interactive builds."""
    parser = argparse.ArgumentParser(description="Build standalone FTID Generator applications.")
    parser.add_argument(
        "--target",
        choices=["mac-arm", "mac-intel", "mac-universal", "windows"],
        help="Target platform to build without showing the interactive menu.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Build the GUI entry point instead of the terminal entry point.",
    )
    parser.add_argument(
        "--skip-dependency-check",
        action="store_true",
        help="Skip auto-installing/checking build dependencies.",
    )
    return parser.parse_args()


def run_interactive_build():
    """Interactive build flow preserved for local manual use."""
    show_menu()

    current_os = platform.system()

    if current_os == 'Darwin':
        choice = input("Enter your choice [1-6, 0 to exit]: ").strip()

        if choice == '0':
            print_info("Exiting...")
            sys.exit(0)
        elif choice == '1':
            return build_app('mac-arm')
        elif choice == '2':
            return build_app('mac-intel')
        elif choice == '3':
            return build_app('mac-universal')
        elif choice == '4':
            return build_app('mac-arm', gui_mode=True)
        elif choice == '5':
            return build_app('mac-intel', gui_mode=True)
        elif choice == '6':
            return build_app('mac-universal', gui_mode=True)
        print_error("Invalid choice")
        sys.exit(1)

    if current_os == 'Windows':
        choice = input("Enter your choice [1-2, 0 to exit]: ").strip()

        if choice == '0':
            print_info("Exiting...")
            sys.exit(0)
        elif choice == '1':
            return build_app('windows')
        elif choice == '2':
            return build_app('windows', gui_mode=True)
        print_error("Invalid choice")
        sys.exit(1)

    print_error("Unsupported platform")
    sys.exit(1)


def report_success():
    """Print the standard success summary."""
    print()
    print_header("Build Complete!")
    print_success("Your application is ready in the 'dist' folder")
    print()
    print_info("What's included:")
    print("  • Single executable file with all dependencies bundled")
    print("  • Source code is compiled and encrypted (not visible)")
    print("  • All data files included inside the executable")
    print()
    print_info("Distribution:")
    print("  • Share the .zip file with users")
    print("  • On macOS: Users may need to allow in System Settings > Security")
    print("  • On Windows: Users may need to allow through Windows Defender")
    print()


def main():
    """Main entry point"""
    args = parse_args()

    if not args.skip_dependency_check and not check_dependencies():
        print_error("Cannot proceed without required dependencies")
        sys.exit(1)

    if not os.path.exists('main.py'):
        print_error("main.py not found in current directory")
        print_info("Please run this script from the project root directory")
        sys.exit(1)

    if args.target:
        success = build_app(args.target, gui_mode=args.gui)
    else:
        success = run_interactive_build()

    if success:
        report_success()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_warning("Build cancelled by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

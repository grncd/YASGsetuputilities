import argparse
import subprocess
import sys
import os
import tempfile
import ctypes

# NOTE: We do not import 'requests' here.
# It will be imported dynamically after checking if it's installed.

# --- Script Configuration ---
FFMPEG_URL = "https://github.com/icedterminal/ffmpeg-installer/releases/download/7.0.0.20240429/FFmpeg_Full.msi"
FFMPEG_FILENAME = "FFmpeg_Full.msi"

# --- Helper Functions ---

def print_progress(percentage, message=""):
    """Prints a formatted progress indicator."""
    bar = f"[{percentage:3d}%]"
    # Center the message in the remaining space
    width = 80
    message_part = f" {message} "
    output = f"{bar}{message_part:-<{width - len(bar)}}"
    print(output)

def is_admin():
    """Checks if the script is running with administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def is_ffmpeg_installed():
    """Checks if ffmpeg is available in the system's PATH."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

def is_git_installed():
    """Checks if git is available in the system's PATH."""
    try:
        subprocess.run(
            ["git", "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

def run_command(command, description):
    """Runs a command in the shell and checks for errors."""
    print(f"-> Running: {description}...")
    try:
        subprocess.run(command, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"-> SUCCESS: {description} completed.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to {description.lower()}.")
        print(f"Stderr: {e.stderr.decode('utf-8')}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"ERROR: Command not found. Make sure '{command[0]}' is in your system's PATH.")
        sys.exit(1)

def add_ffmpeg_to_path():
    """Adds FFmpeg bin directory to the user's PATH (registry) and current process if not already present."""
    ffmpeg_bin = os.path.join(
        os.environ["USERPROFILE"],
        "AppData", "Local", "Programs", "FFmpeg", "bin"
    )
    # Check if the directory exists
    if not os.path.isdir(ffmpeg_bin):
        print(f"-> WARNING: FFmpeg bin directory not found at {ffmpeg_bin}. Skipping PATH update.")
        return

    # Get current user PATH from registry
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ
        ) as key:
            try:
                current_path, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_path = ""
    except Exception as e:
        print(f"-> WARNING: Could not read user PATH from registry: {e}")
        current_path = ""

    # Add ffmpeg_bin to registry PATH if not present
    if ffmpeg_bin.lower() not in [p.lower() for p in current_path.split(";")]:
        new_path = current_path + (";" if current_path else "") + ffmpeg_bin
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Environment",
                0,
                winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            print("-> SUCCESS: FFmpeg bin directory added to user PATH (registry).")
            print("NOTE: You may need to restart your terminal or log out/in for PATH changes to take effect.")
        except Exception as e:
            print(f"-> WARNING: Failed to update user PATH in registry: {e}")
    else:
        print("-> INFO: FFmpeg bin already in user PATH (registry). Skipping PATH update.")

    # Add ffmpeg_bin to current process PATH if not present
    process_path = os.environ.get("PATH", "")
    if ffmpeg_bin.lower() not in [p.lower() for p in process_path.split(";")]:
        os.environ["PATH"] = process_path + (";" if process_path else "") + ffmpeg_bin
        print("-> SUCCESS: FFmpeg bin directory added to current process PATH.")
    else:
        print("-> INFO: FFmpeg bin already in current process PATH.")

def install_ffmpeg():
    """Checks for FFmpeg, then downloads and installs it if not found."""
    if is_ffmpeg_installed():
        print("-> SUCCESS: FFmpeg is already installed. Skipping.\n")
        return

    print("-> INFO: FFmpeg not found. Proceeding with installation.")
    try:
        import requests
    except ImportError:
        print("-> INFO: 'requests' library not found. Installing it first...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("-> SUCCESS: 'requests' has been installed.")
            import requests
        except subprocess.CalledProcessError as e:
            print("FATAL ERROR: Could not install 'requests' library, which is required to download FFmpeg.")
            print(f"Stderr: {e.stderr.decode('utf-8')}")
            sys.exit(1)

    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, FFMPEG_FILENAME)

    try:
        print_progress(10, "Downloading FFmpeg")
        print(f"-> Downloading FFmpeg from {FFMPEG_URL}...")
        with requests.get(FFMPEG_URL, stream=True) as r:
            r.raise_for_status()
            with open(installer_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
        print("-> SUCCESS: Download complete.")
        
        print_progress(20, "Installing FFmpeg (per-user, no admin required)")
        # Use /qn ALLUSERS=2 MSIINSTALLPERUSER=1 for per-user install
        msi_command = f'msiexec /i "{installer_path}" /qn ALLUSERS=2 MSIINSTALLPERUSER=1'
        subprocess.run(msi_command, check=True, shell=True)
        print("-> SUCCESS: FFmpeg installation finished.\n")
        print_progress(25, "Adding FFmpeg to PATH")
        add_ffmpeg_to_path()
    except (requests.exceptions.RequestException, subprocess.CalledProcessError) as e:
        print(f"ERROR: Failed during FFmpeg setup. Details: {e}")
        sys.exit(1)
    finally:
        if os.path.exists(installer_path):
            os.remove(installer_path)

def install_git(progress_start=0):
    """Installs Git using winget if not already installed."""
    print_progress(progress_start, "An admin popup will appear to install Git. Please allow it.")
    if is_git_installed():
        print("-> SUCCESS: Git is already installed. Skipping.\n")
        return
    try:
        subprocess.run(
            ["winget", "install", "--id", "Git.Git", "-e", "--source", "winget"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        print("-> SUCCESS: Git installation finished.\n")
    except subprocess.CalledProcessError as e:
        print("ERROR: Failed to install Git.")
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: 'winget' not found. Please install winget and try again.")
        sys.exit(1)

def install_demucs_package(progress_start=70):
    """Installs demucs and its dependencies (PyTorch)."""
    print_progress(progress_start, "Installing PyTorch for demucs (will take a LONG time)")
    run_command(f'"{sys.executable}" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128', "Install PyTorch with custom index URL")
    print_progress(progress_start + 25, "Installing demucs")
    run_command(f'"{sys.executable}" -m pip install demucs', "pip install demucs")

def main():
    """Main function to parse arguments and run installation steps."""

    parser = argparse.ArgumentParser(
        description="A script to set up a Python environment with FFmpeg, spotdl, syrics, and optionally demucs."
    )
    parser.add_argument(
        "install_demucs", choices=['true', 'false'],
        help="Specify 'true' to install demucs, or 'false' to skip it."
    )
    parser.add_argument(
        "only_demucs", nargs='?', default=None,
        help="Optional: If set to 'true', ONLY demucs will be installed."
    )
    args = parser.parse_args()

    if args.only_demucs == 'true':
        print_progress(0, "Starting demucs-only installation.")
        install_demucs_package(progress_start=10)
        print_progress(100, "Setup Complete!")
        print("\n===================================")
        print("Demucs installation completed successfully!")
        print("===================================")
        sys.exit(0)


    # --- SCRIPT EXECUTION START ---
    print_progress(0, "Starting Environment Setup")

    # Install Git first
    install_git(progress_start=5)

    print_progress(10, "Checking/Downloading for FFmpeg")
    install_ffmpeg()

    print_progress(30, "Installing spotdl")
    run_command(f'"{sys.executable}" -m pip install spotdl==4.2.11', "pip install spotdl==4.2.11")

    print_progress(60, "Installing syrics")
    run_command(f'"{sys.executable}" -m pip install syrics', "pip install syrics")

    if args.install_demucs == 'true':
        install_demucs_package()
    else:
        print("\n-> Skipping demucs installation as per argument.")

    print_progress(100, "Setup Complete!")
    print("\n===================================")
    print("All tasks completed successfully!")
    print("===================================")

if __name__ == "__main__":
    main()

import argparse
import subprocess
import sys
import os
import tempfile
import time
import platform
import shutil

is_windows = platform.system() == "Windows"

if is_windows:
    import ctypes
    import winreg

# NOTE: We do not import 'requests' here.
# It will be imported dynamically after checking if it's installed.

# --- Script Configuration ---
FFMPEG_URL = "https://github.com/icedterminal/ffmpeg-installer/releases/download/7.0.0.20240429/FFmpeg_Full.msi"
FFMPEG_FILENAME = "FFmpeg_Full.msi"

# --- Helper Functions ---

def print_progress(percentage, message=""):
    """Prints a formatted progress indicator."""
    bar = f"[{percentage:3d}%]"
    width = 80
    message_part = f" {message} "
    output = f"{bar}{message_part:-<{width - len(bar)}}"
    print(output)

def is_admin():
    """Checks if the script is running with administrative privileges."""
    try:
        if is_windows:
            return ctypes.windll.shell32.IsUserAnAdmin()
        else:
            return os.geteuid() == 0
    except:
        return False

def is_ffmpeg_installed():
    """Checks if ffmpeg is available in either of the common installation paths or PATH."""
    if is_windows:
        ffmpeg_paths = [
            r"C:\Program Files\FFmpeg\bin\ffmpeg.exe",
            os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\Programs\FFmpeg\bin\ffmpeg.exe")
        ]
        
        for path in ffmpeg_paths:
            if os.path.exists(path):
                return True
    
    # Check PATH on both platforms
    return shutil.which("ffmpeg") is not None

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
        # Using sys.executable ensures we use the python interpreter running the script
        # which is more reliable than just 'python' or 'pip'.
        final_command = command.replace("python", f'"{sys.executable}"')
        subprocess.run(final_command, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    if not is_windows:
        return # Skip on Linux

    ffmpeg_bin = os.path.join(
        os.environ["USERPROFILE"],
        "AppData", "Local", "Programs", "FFmpeg", "bin"
    )
    
    # Check if the directory exists
    if not os.path.isdir(ffmpeg_bin):
        print(f"-> WARNING: FFmpeg bin directory not found at {ffmpeg_bin}. Skipping PATH update.")
        return

    # Get current user PATH from registry
    try:
        # First, try to open the Environment key for the current user
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE
        ) as key:
            try:
                current_path, reg_type = winreg.QueryValueEx(key, "Path")
                print(f"-> INFO: Current user PATH found: {current_path[:100]}...")
            except FileNotFoundError:
                print("-> INFO: No user PATH found in registry. Creating new one.")
                current_path = ""
                reg_type = winreg.REG_EXPAND_SZ
            
            # Check if ffmpeg_bin is already in the path (case-insensitive)
            path_entries = [p.strip() for p in current_path.split(";") if p.strip()]
            ffmpeg_in_path = any(entry.lower() == ffmpeg_bin.lower() for entry in path_entries)
            
            if not ffmpeg_in_path:
                # Add ffmpeg_bin to the path
                if current_path and not current_path.endswith(";"):
                    new_path = current_path + ";" + ffmpeg_bin
                else:
                    new_path = current_path + ffmpeg_bin
                
                # Write back to registry
                winreg.SetValueEx(key, "Path", 0, reg_type, new_path)
                print("-> SUCCESS: FFmpeg bin directory added to user PATH (registry).")
                print(f"-> INFO: Added path: {ffmpeg_bin}")
                print("NOTE: You may need to restart your terminal or log out/in for PATH changes to take effect.")
                
                # Broadcast WM_SETTINGCHANGE to notify system of environment change
                try:
                    from ctypes import wintypes
                    
                    HWND_BROADCAST = 0xFFFF
                    WM_SETTINGCHANGE = 0x001A
                    SMTO_ABORTIFHUNG = 0x0002
                    
                    result = ctypes.windll.user32.SendMessageTimeoutW(
                        HWND_BROADCAST,
                        WM_SETTINGCHANGE,
                        0,
                        "Environment",
                        SMTO_ABORTIFHUNG,
                        5000,
                        ctypes.byref(wintypes.DWORD())
                    )
                    if result:
                        print("-> INFO: Notified system of environment variable change.")
                    else:
                        print("-> WARNING: Failed to notify system of environment change.")
                except Exception as e:
                    print(f"-> WARNING: Could not broadcast environment change: {e}")
            else:
                print("-> INFO: FFmpeg bin already in user PATH (registry). Skipping PATH update.")
                
    except PermissionError:
        print("-> ERROR: Permission denied when trying to access user environment registry.")
        # ... setx fallback omitted for brevity as it is extensive and strictly windows ...
    except Exception as e:
        print(f"-> ERROR: Unexpected error when updating user PATH: {e}")

    # Add ffmpeg_bin to current process PATH if not present
    process_path = os.environ.get("PATH", "")
    path_entries = [p.strip() for p in process_path.split(";") if p.strip()]
    if not any(entry.lower() == ffmpeg_bin.lower() for entry in path_entries):
        os.environ["PATH"] = process_path + (";" if process_path and not process_path.endswith(";") else "") + ffmpeg_bin
        print("-> SUCCESS: FFmpeg bin directory added to current process PATH.")
    else:
        print("-> INFO: FFmpeg bin already in current process PATH.")


def install_ffmpeg():
    """Checks for FFmpeg, then downloads and installs it if not found."""
    if is_ffmpeg_installed():
        print("-> SUCCESS: FFmpeg is already installed and in PATH. Skipping.\n")
        return

    print("-> INFO: FFmpeg not found. Proceeding with installation.")
    
    if not is_windows:
        msg = "FFmpeg is not installed.\nPlease install FFmpeg using your package manager.\nExample: sudo apt install ffmpeg\nOr: sudo pacman -S ffmpeg"
        print(f"-> ERROR: {msg}")
        show_linux_error_popup("Missing Dependency: FFmpeg", msg)
        sys.exit(1)

    # Windows installation logic
    try:
        import requests
    except ImportError:
        print("-> INFO: 'requests' library not found. Installing it first...")
        try:
            run_command("python -m pip install requests", "Install 'requests' library")
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
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("-> SUCCESS: Download complete.")
        
        print_progress(20, "Installing FFmpeg (per-user, no admin required)")
        # Use /qn ALLUSERS=2 MSIINSTALLPERUSER=1 for per-user install
        msi_command = f'msiexec /i "{installer_path}" /qn ALLUSERS=2 MSIINSTALLPERUSER=1'
        subprocess.run(msi_command, check=True, shell=True)
        print("-> SUCCESS: FFmpeg installation finished.\n")
        
        print_progress(25, "Adding FFmpeg to PATH")
        add_ffmpeg_to_path()
        
        # Final check
        if not is_ffmpeg_installed():
             print("\n-> WARNING: FFmpeg was installed, but the 'ffmpeg' command is still not available.")
             print("   This can happen due to system delays. Please restart your terminal and try again.")
             print("   If the problem persists, please check your Environment Variables in Windows Settings.\n")

    except (requests.exceptions.RequestException, subprocess.CalledProcessError) as e:
        print(f"ERROR: Failed during FFmpeg setup. Details: {e}")
        sys.exit(1)
    finally:
        if os.path.exists(installer_path):
            os.remove(installer_path)


def install_windows_appruntime():
    """Installs the required Microsoft.WindowsAppRuntime dependency via PowerShell."""
    if not is_windows:
        return True # Not relevant on Linux

    print("-> ERROR: Missing 'Microsoft.WindowsAppRuntime'. Installing it now...")
    
    try:
        # Download the Windows App Runtime package from the official source
        subprocess.run(
            ["powershell", "-Command", "Invoke-WebRequest -Uri 'https://aka.ms/windowsappruntime' -OutFile 'C:\\temp\\Microsoft.WindowsAppRuntime_1.8.0.0_x64.msixbundle'"],
            check=True,
            text=True,
            capture_output=True
        )

        # Install the downloaded .msixbundle package
        subprocess.run(
            ["powershell", "-Command", "Add-AppxPackage -Path 'C:\\temp\\Microsoft.WindowsAppRuntime_1.8.0.0_x64.msixbundle'"],
            check=True,
            text=True,
            capture_output=True
        )
        
        print("-> SUCCESS: 'Microsoft.WindowsAppRuntime' installed successfully.")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install Microsoft.WindowsAppRuntime. {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error during Windows App Runtime installation: {str(e)}")
        return False

def show_linux_error_popup(title, message):
    """Shows a GUI popup on Linux using available tools."""
    # Try Zenity (GNOME/standard)
    if shutil.which("zenity"):
        try:
            subprocess.run(["zenity", "--error", "--title", title, "--text", message], check=False)
            return
        except: pass
    
    # Try KDialog (KDE/SteamOS)
    if shutil.which("kdialog"):
        try:
            subprocess.run(["kdialog", "--error", message, "--title", title], check=False)
            return
        except: pass
        
    # Try xmessage (X11)
    if shutil.which("xmessage"):
        try:
            subprocess.run(["xmessage", "-center", "-title", title, message], check=False)
            return
        except: pass
        
    # Try Tkinter (Python)
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw() # Hide main window
        messagebox.showerror(title, message)
        root.destroy()
        return
    except: pass
    
    print(f"!!! [{title}] {message} !!!")

def is_git_installed():
    """Checks if git is available in the system's PATH."""
    return shutil.which("git") is not None

def install_git(progress_start=0):
    """Installs Git using winget if not already installed, handles winget installation if needed."""
    if is_git_installed():
        print("-> SUCCESS: Git is already installed. Skipping.\n")
        return

    print_progress(progress_start, "Installing git")
    
    if not is_windows:
         msg = "Git is not installed.\nPlease install Git using your package manager.\nExample: sudo apt install git\nOr: sudo pacman -S git"
         print(f"-> ERROR: {msg}")
         show_linux_error_popup("Missing Dependency: Git", msg)
         sys.exit(1)

    print("-> Installing git (be patient, an admin popup might appear)")
    try:
        # Run the winget command to install Git
        result = subprocess.run(
            ["winget", "install", "--id", "Git.Git", "-e", "--source", "winget"],
            check=True, 
            text=True, 
            capture_output=True
        )
        
        # If installation succeeds
        print("-> SUCCESS: Git installation finished.\n")
        print("Winget Output:", result.stdout)

    except subprocess.CalledProcessError as e:
        print("ERROR: Failed to install Git using winget.")
        
        # If the error is related to missing 'Microsoft.WindowsAppRuntime', install it
        if "0x80073CF3" in e.stderr:
            print("ERROR: Dependency 'Microsoft.WindowsAppRuntime' is missing. Attempting to install it...")
            if install_windows_appruntime():
                # Retry Git installation after dependency is installed
                print("Retrying Git installation...")
                try:
                    result = subprocess.run(
                        ["winget", "install", "--id", "Git.Git", "-e", "--source", "winget"],
                        check=True,
                        text=True,
                        capture_output=True
                    )
                    print("-> SUCCESS: Git installation finished after installing the runtime.\n")
                    print("Winget Output:", result.stdout)
                except subprocess.CalledProcessError as retry_err:
                    print("ERROR: Failed to install Git after installing the dependency.")
                    print("Retry Error:", retry_err.stderr)
                    sys.exit(1)
            else:
                print("ERROR: Failed to install the required dependency. Git installation cannot proceed.")
                sys.exit(1)

        # Handle other common installation errors
        elif 'winget' not in e.stderr:
            print("Attempting to install winget...")
            try:
                subprocess.run(
                    ["powershell", "Add-AppxPackage", "https://aka.ms/getwinget"],
                    check=True,
                    text=True,
                    capture_output=True
                )
                print("-> SUCCESS: winget installation finished.")
                
                # Wait a bit for winget to fully install (it may take some time)
                print("Waiting for winget installation to complete...")
                time.sleep(3.1)  # Adjust the wait time as needed

            except subprocess.CalledProcessError as install_err:
                print("ERROR: Failed to install winget.")
                print("Install Error:", install_err.stderr)
                sys.exit(1)
            except Exception as install_ex:
                print("Unexpected error during winget installation:", str(install_ex))
                sys.exit(1)

            # Retry Git installation after winget is installed
            print("Retrying Git installation...")
            try:
                result = subprocess.run(
                    ["winget", "install", "--id", "Git.Git", "-e", "--source", "winget"],
                    check=True,
                    text=True,
                    capture_output=True
                )
                print("-> SUCCESS: Git installation finished after winget install.\n")
                print("Winget Output:", result.stdout)
            except subprocess.CalledProcessError as retry_err:
                print("ERROR: Failed to install Git after winget installation.")
                print("Retry Error:", retry_err.stderr)
                sys.exit(1)

        else:
            # If 'winget' was the cause of the failure (not found)
            print("ERROR: 'winget' not found. Please install winget manually and try again.")
            sys.exit(1)

    except FileNotFoundError:
        print("ERROR: 'winget' not found. Please install winget (App Installer) from the Microsoft Store and try again.")
        sys.exit(1)
    except Exception as ex:
        print("An unexpected error occurred:", str(ex))
        sys.exit(1)



def install_demucs_package(progress_start=70):
    """Installs demucs and its dependencies (PyTorch)."""
    print_progress(progress_start, "Installing PyTorch for demucs")
    if is_windows:
        run_command('python -m pip install torch torchvision torchaudio torchcodec --index-url https://download.pytorch.org/whl/cu128', "Install PyTorch (Windows/CUDA)")
    else:
        # On Linux, default to CPU or standard PyPI to avoid architecture/driver mismatch (e.g. Steam Deck)
        # We also skip 'torchcodec' if it's problematic, or let pip resolve it.
        # Using CPU-only index is safest for a guaranteed runnable state without GPU setup.
        run_command('python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu', "Install PyTorch (Linux/CPU)")
    
    print_progress(progress_start + 25, "Installing demucs")
    run_command('python -m pip install demucs', "pip install demucs")
    

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
        "only_demucs", nargs='?', default='false',
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

    install_git(progress_start=5)
    install_ffmpeg() # This now handles path correctly

    print_progress(30, "Installing spotdl")
    run_command("python -m pip install spotdl", "Installing spotdl")

    print_progress(60, "Installing syrics")
    run_command("python -m pip install syrics", "pip install syrics")

    print_progress(65, "Installing soundfile")
    run_command("python -m pip install soundfile", "pip install soundfile")

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

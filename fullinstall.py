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
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full-shared.7z"
FFMPEG_FILENAME = "ffmpeg-release-full-shared.7z"

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
    """Checks if ffmpeg is available.

    On Windows: Always returns False (uses separate installation logic).
    On Linux: Checks if ffmpeg command exists in PATH.
    """
    if is_windows:
        # Windows uses separate installation logic that can't reuse existing installations
        return False

    # Linux: just check if the command exists
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

def is_vc_redist_installed():
    """Checks if Visual C++ Redistributable 2015-2022 is installed (Windows only)."""
    if not is_windows:
        return True  # Not relevant on Linux

    # Check both x86 and x64 registry keys
    registry_paths = [
        r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x86",
    ]

    for reg_path in registry_paths:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                # If we can open the key, VC Redist is installed
                return True
        except FileNotFoundError:
            continue
        except Exception:
            continue

    return False

def install_vc_redist():
    """Downloads and installs Visual C++ Redistributable silently (Windows only)."""
    if not is_windows:
        return True

    if is_vc_redist_installed():
        print("-> SUCCESS: Visual C++ Redistributable is already installed. Skipping.\n", flush=True)
        return True

    print("-> INFO: Visual C++ Redistributable not found. Installing...", flush=True)

    try:
        import requests
    except ImportError:
        print("-> INFO: 'requests' library not found. Installing it first...", flush=True)
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "requests"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            import requests
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Could not install 'requests' library. {e.stderr.decode('utf-8')}", flush=True)
            return False

    vc_redist_url = "https://aka.ms/vc14/vc_redist.x64.exe"
    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, "vc_redist.x64.exe")

    try:
        print(f"-> Downloading VC Redistributable from {vc_redist_url}...", flush=True)
        with requests.get(vc_redist_url, stream=True) as r:
            r.raise_for_status()
            with open(installer_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("-> SUCCESS: VC Redistributable downloaded.", flush=True)

        print("-> Running VC Redistributable installer silently...", flush=True)
        # /install /quiet /norestart - silent install without restart prompt
        result = subprocess.run(
            [installer_path, "/install", "/quiet", "/norestart"],
            check=False  # Don't raise on non-zero, check manually
        )

        # Return codes: 0 = success, 1638 = already installed (newer version), 3010 = success but reboot required
        if result.returncode in [0, 1638, 3010]:
            print("-> SUCCESS: Visual C++ Redistributable installed.\n", flush=True)
            return True
        else:
            print(f"-> WARNING: VC Redistributable installer returned code {result.returncode}.", flush=True)
            return False

    except Exception as ex:
        print(f"-> ERROR: Failed to install VC Redistributable. Details: {ex}", flush=True)
        return False
    finally:
        if os.path.exists(installer_path):
            try:
                os.remove(installer_path)
            except:
                pass

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
    """Checks for FFmpeg, then downloads and installs it directly if not found."""
    if is_ffmpeg_installed():
        print("-> SUCCESS: FFmpeg is already installed and in PATH. Skipping.\n")
        
        # Try to find the path to report it to the caller
        found_path = shutil.which("ffmpeg")
        if not found_path and is_windows:
             ffmpeg_paths = [
                r"C:\Program Files\FFmpeg\bin\ffmpeg.exe",
                os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\Programs\FFmpeg\bin\ffmpeg.exe")
            ]
             for p in ffmpeg_paths:
                 if os.path.exists(p):
                     found_path = p
                     break
        
        if found_path:
            # We want the directory, not the executable
            bin_dir = os.path.dirname(os.path.abspath(found_path)) if os.path.isfile(found_path) else os.path.abspath(found_path)
            print(f"SETUP_FFMPEG_PATH:{bin_dir}")
        return

    print("-> INFO: FFmpeg not found. Proceeding with installation.")
    
    if not is_windows:
        msg = "FFmpeg is not installed.\nPlease install FFmpeg using your package manager.\nExample: sudo apt install ffmpeg\nOr: sudo pacman -S ffmpeg"
        print(f"-> ERROR: {msg}")
        show_linux_error_popup("Missing Dependency: FFmpeg", msg)
        sys.exit(1)

    # Windows installation logic
    
    # Check for requests
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
    download_path = os.path.join(temp_dir, FFMPEG_FILENAME)
    extract_path = os.path.join(temp_dir, "ffmpeg_extracted")
    
    # Find or download 7-Zip for extraction (py7zr doesn't support BCJ2 filter)
    seven_zip_exe = None
    common_7z_paths = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        os.path.join(temp_dir, "7za.exe")
    ]
    
    for path in common_7z_paths:
        if os.path.exists(path):
            seven_zip_exe = path
            break
    
    # If 7-Zip not found, download portable version
    if not seven_zip_exe:
        print("-> INFO: 7-Zip not found. Downloading portable version...")
        try:
            seven_zip_url = "https://www.7-zip.org/a/7zr.exe"
            seven_zip_path = os.path.join(temp_dir, "7zr.exe")
            with requests.get(seven_zip_url, stream=True) as r:
                r.raise_for_status()
                with open(seven_zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            seven_zip_exe = seven_zip_path
            print("-> SUCCESS: 7-Zip portable downloaded.")
        except Exception as e:
            print(f"FATAL ERROR: Could not download 7-Zip portable: {e}")
            sys.exit(1)

    try:
        # 1. Download
        print_progress(10, "Downloading FFmpeg")
        print(f"-> Downloading FFmpeg from {FFMPEG_URL}...")
        with requests.get(FFMPEG_URL, stream=True) as r:
            r.raise_for_status()
            with open(download_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("-> SUCCESS: Download complete.")
        
        # 2. Extract using 7-Zip command line (supports BCJ2 filter)
        print_progress(15, "Extracting FFmpeg")
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        
        os.makedirs(extract_path, exist_ok=True)
        
        extract_result = subprocess.run(
            [seven_zip_exe, "x", download_path, f"-o{extract_path}", "-y"],
            capture_output=True,
            text=True
        )
        
        if extract_result.returncode != 0:
            print(f"ERROR: 7-Zip extraction failed: {extract_result.stderr}")
            sys.exit(1)
            
        print("-> SUCCESS: Extraction complete.")
        
        # 3. Find 'bin' folder in extracted contents
        print_progress(20, "Installing FFmpeg files")
        
        ffmpeg_bin_source = None
        for root, dirs, files in os.walk(extract_path):
            if "bin" in dirs:
                possible_bin = os.path.join(root, "bin")
                # Verify it contains ffmpeg.exe
                if os.path.exists(os.path.join(possible_bin, "ffmpeg.exe")):
                    ffmpeg_bin_source = possible_bin
                    break
        
        if not ffmpeg_bin_source:
             print("ERROR: Could not find 'bin' folder containing ffmpeg.exe in the downloaded archive.")
             sys.exit(1)

        # 4. Move files to target location
        target_bin_dir = os.path.join(
            os.environ["APPDATA"],
            "YASG", "YASG", "vocalremover", "ffmpeg_lib"
        )
        
        # Create target directory if it doesn't exist
        os.makedirs(target_bin_dir, exist_ok=True)
        
        # Move files
        for filename in os.listdir(ffmpeg_bin_source):
            src_file = os.path.join(ffmpeg_bin_source, filename)
            dst_file = os.path.join(target_bin_dir, filename)
            if os.path.isfile(src_file):
                shutil.copy2(src_file, dst_file)
        
        print(f"-> SUCCESS: FFmpeg installed to {target_bin_dir}")
        
        # Report the path to Unity (or other runners)
        print(f"SETUP_FFMPEG_PATH:{os.path.abspath(target_bin_dir)}")

    except (requests.exceptions.RequestException, subprocess.CalledProcessError) as e:
        print(f"ERROR: Failed during FFmpeg setup. Details: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if os.path.exists(download_path):
            try:
                os.remove(download_path)
            except: pass
        if os.path.exists(extract_path):
            try:
                shutil.rmtree(extract_path)
            except: pass


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

def install_git(progress_start=0):
    """Installs Git using winget, or falls back to direct download/install."""
    if is_git_installed():
        print("-> SUCCESS: Git is already installed. Skipping.\n", flush=True)
        return

    print_progress(progress_start, "Installing git")

    # On Windows, ensure VC Redistributable is installed first (Git requires it)
    if is_windows:
        install_vc_redist()

    if not is_windows:
         msg = "Git is not installed.\nPlease install Git using your package manager.\nExample: sudo apt install git\nOr: sudo pacman -S git"
         print(f"-> ERROR: {msg}", flush=True)
         show_linux_error_popup("Missing Dependency: Git", msg)
         sys.exit(1)

    print("-> Installing git (be patient, an admin popup might appear)", flush=True)
    
    # 1. Try Winget
    try:
        print("-> Attempting installation via Winget...", flush=True)
        # Added --accept-package-agreements and --accept-source-agreements to avoid interactive prompts
        result = subprocess.run(
            ["winget", "install", "--id", "Git.Git", "-e", "--source", "winget", 
             "--accept-package-agreements", "--accept-source-agreements"],
            check=True, 
            text=True, 
            capture_output=True
        )
        print("-> SUCCESS: Git installation via Winget finished.\n", flush=True)
        return

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"-> WARNING: Winget installation failed. Reason: {e}", flush=True)
        if hasattr(e, 'stderr') and e.stderr:
            print(f"   Winget Stderr: {e.stderr}", flush=True)

    # 2. Fallback: Direct Download & Install
    print("-> INFO: Falling back to direct Git installer download...", flush=True)
    
    git_installer_url = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe"
    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, "git-installer.exe")

    try:
        # Check for requests again (should be installed by install_ffmpeg logic checking, but safety first)
        import requests
        
        print(f"-> Downloading Git installer from {git_installer_url}...", flush=True)
        with requests.get(git_installer_url, stream=True) as r:
            r.raise_for_status()
            with open(installer_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("-> SUCCESS: Git installer downloaded.", flush=True)

        print("-> Running Git installer silently...", flush=True)
        # /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS
        # We use /VERYSILENT to show no UI.
        subprocess.run(
            [installer_path, "/VERYSILENT", "/NORESTART", "/NOCANCEL", "/SP-", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
            check=True
        )
        print("-> SUCCESS: Git direct installation finished.\n", flush=True)
        
    except Exception as ex:
        print(f"-> ERROR: Failed to install Git via direct download.", flush=True)
        print(f"   Details: {ex}", flush=True)
        sys.exit(1)
    finally:
        if os.path.exists(installer_path):
            try:
                os.remove(installer_path)
            except: pass



def install_demucs_package(progress_start=70):
    """Installs demucs and its dependencies (PyTorch)."""
    print_progress(progress_start, "Installing PyTorch for demucs")
    if is_windows:
        run_command('python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128', "Install PyTorch (Windows/CUDA)")
        run_command('python -m pip install torchcodec', "Install PyTorch (Windows/CUDA)")
    else:
        # On Linux, use standard PyPI which typically includes CUDA support.
        # User requested CUDA compatible build.
        run_command('python -m pip install torch torchvision torchaudio torchcodec', "Install PyTorch (Linux/CUDA)")
    
    print_progress(progress_start + 25, "Installing demucs")
    run_command('python -m pip install demucs', "pip install demucs")
    

def main():
    """Main function to parse arguments and run installation steps."""
    parser = argparse.ArgumentParser(
        description="A script to set up a Python environment with FFmpeg, syrics, and optionally demucs."
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

    print_progress(45, "Installing syrics")
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

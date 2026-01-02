import os
import time
import sys
import io
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import platform
import subprocess
import time

# Fix console encoding for Unicode support (Russian characters, etc.)
if sys.platform == 'win32':
    try:
        # Force UTF-8 encoding for stdout and stderr
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

def safe_print(message):
    """Safely print messages with potential Unicode characters"""
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        # Fallback: encode with replacement for problematic characters
        try:
            safe_message = message.encode('ascii', errors='replace').decode('ascii')
            print(safe_message, flush=True)
        except Exception:
            print("[Message with special characters]", flush=True)

def focus_window_by_title_substring(substring):
    system = platform.system()
    found = False

    if system == "Windows":
        try:
            import win32gui
            import win32con
            import win32api

            def callback(hwnd, found_hwnds_list_ref):
                try:
                    if not win32gui.IsWindowVisible(hwnd) or not win32gui.IsWindowEnabled(hwnd):
                        return True

                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title and substring.lower() in window_title.lower():
                        try:
                            win32gui.SetForegroundWindow(hwnd)
                        except win32gui.error as e:
                            if e.winerror == 0 or e.winerror == 5:
                                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                                time.sleep(0.05)
                                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                                time.sleep(0.05)
                                win32gui.SetForegroundWindow(hwnd)
                            else:
                                return True
                        
                        found_hwnds_list_ref.append(hwnd)
                        return False
                except Exception:
                    pass
                return True

            hwnds = []
            win32gui.EnumWindows(callback, hwnds)

            if hwnds:
                print(f"Focused window containing '{substring}'.")
                found = True
            else:
                print(f"No visible window found with '{substring}' in title or could not focus.")

        except ImportError:
            print("pywin32 library not found. Please install it: pip install pywin32")
            return False
        except Exception as e_outer:
            print(f"An unexpected error occurred with pywin32: {e_outer}")
            return False

    elif system == "Linux":
        try:
            subprocess.run(["wmctrl", "-m"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, check=True)
            windows = result.stdout.strip().split("\n")
            target_window_id = None
            for window_line in windows:
                if substring.lower() in window_line.lower():
                    target_window_id = window_line.split()[0]
                    break
            if target_window_id:
                subprocess.run(["wmctrl", "-i", "-a", target_window_id], check=True)
                print(f"Focused window containing '{substring}'.")
                found = True
            else:
                print(f"No window found with '{substring}' in title.")
        except FileNotFoundError:
            print("wmctrl not found. Please install it (e.g., 'sudo apt install wmctrl').")
        except subprocess.CalledProcessError as e:
            print(f"Error using wmctrl: {e}")

    elif system == "Darwin":
        script = f'''
        tell application "System Events"
            set procs to processes whose background only is false
            repeat with proc in procs
                repeat with w in windows of proc
                    if name of w is not missing value and name of w contains "{substring}" then
                        tell proc to set frontmost to true
                        delay 0.1
                        perform action "AXRaise" of w
                        return "Focused"
                    end if
                end repeat
            end repeat
            return "Not Found"
        end tell
        '''
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            if "Focused" in result.stdout:
                print(f"Focused window containing '{substring}'.")
                found = True
            else:
                print(f"No window found with '{substring}' in title.")
        except subprocess.CalledProcessError as e:
            print(f"Error running AppleScript: {e.stdout} {e.stderr}")
        except FileNotFoundError:
            print("osascript (AppleScript runner) not found.")

    else:
        print(f"Unsupported operating system: {system}")

    return found

start_time = time.time()

# --- Set download_dir automatically ---
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
download_dir = os.path.join(parent_dir, "output","htdemucs")
os.makedirs(download_dir, exist_ok=True)

if not os.path.isdir(download_dir):
    print(f"Download directory does not exist: {download_dir}")
    sys.exit(1)

chrome_options = Options()
prefs = {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "safebrowsing.enabled": True
}
chrome_options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(options=chrome_options)
driver.set_window_position(-2000,-1920)
focus_window_by_title_substring("YASG")
driver.get("https://vocalremover.org/?patreon=1")
time.sleep(3)

try:
    file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
except Exception as e:
    print("Could not locate file input element:", e)
    driver.quit()
    exit(1)

input_dir = os.path.join(os.getcwd(), "input")
if not os.path.isdir(input_dir):
    print(f"No input folder found at {input_dir}")
    driver.quit()
    exit(1)

wav_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.mp3')]
if not wav_files:
    print("No .wav file found in the 'input' folder.")
    driver.quit()
    exit(1)
elif len(wav_files) > 1:
    # pick the most recently created .mp3 and remove the others
    full_paths = [os.path.join(input_dir, f) for f in wav_files]
    most_recent = max(full_paths, key=os.path.getctime)
    chosen = os.path.basename(most_recent)
    safe_print(f"More than one .mp3 file found in 'input'; selecting most recently created: {chosen}")
    for p in full_paths:
        if p != most_recent:
            try:
                os.remove(p)
                safe_print(f"Deleted older file: {os.path.basename(p)}")
            except Exception as e:
                safe_print(f"Could not delete {os.path.basename(p)}: {e}")
    wav_files = [chosen]
    
file_path = os.path.abspath(os.path.join(input_dir, wav_files[0]))
safe_print(f"Uploading file: {file_path}")
file_input.send_keys(file_path)

wait = WebDriverWait(driver, 120)

print("Progress: 0%",flush=True)

wait.until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Uploading file')]")))
print("Progress: 10%",flush=True)

ai_msg_locator    = (By.XPATH, "//*[contains(text(), 'Artificial intelligence algorithm now works')]")
loading_locator   = (By.XPATH, "//*[contains(text(), 'Loading')]")

start = time.time()
timeout = 120
while time.time() - start < timeout:
    if driver.find_elements(*ai_msg_locator):
        print("AI algorithm message detected")
        print("Progress: 20%",flush=True)
        time.sleep(3)
        wait.until(EC.visibility_of_element_located(loading_locator))
        print("'Loading...' appeared after AI message")
        print("Progress: 30%",flush=True)
        break
    elif driver.find_elements(*loading_locator):
        print("Skipped AI message; 'Loading...' detected directly")
        print("Progress: 30%",flush=True)
        break
    time.sleep(1)
else:
    raise RuntimeError("Neither AI message nor 'Loading...' appeared in time")

wait.until(EC.invisibility_of_element_located(loading_locator))
print("Processing complete")
print("Progress: 60%",flush=True)
time.sleep(0.2)

try:
    save_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Save')]")))
    save_button.click()
    print("Clicked the 'Save' button")
    print("Progress: 70%",flush=True)
except Exception as e:
    print("Could not click the 'Save' button:", e)
time.sleep(0.5)

try:
    vocal_button = wait.until(EC.element_to_be_clickable((
        By.XPATH,
        "//button[contains(@class,'white') and .//span[text()='Vocal']]"
    )))
    vocal_button.click()
    print("Clicked the 'Vocal' download option")
    print("Progress: 80%",flush=True)
except Exception as e:
    print("Could not click the 'Vocal' button:", e)

# Record timestamp before download completes
download_start_time = time.time()

timeout = time.time() + 120
while time.time() < timeout:
    if not any(fname.endswith('.crdownload') for fname in os.listdir(download_dir)):
        break
    elapsed = 120 - (timeout - time.time())
    percent = 80 + int(19 * (elapsed / 120))
    print(f"Progress: {percent}%",flush=True)
    time.sleep(3)

print("Progress: 90%",flush=True)

# Find the .mp3 file that was created after download started
downloaded_file = None
newest_mtime = 0
for fname in os.listdir(download_dir):
    if fname.lower().endswith(".mp3"):
        fpath = os.path.join(download_dir, fname)
        ftime = os.path.getmtime(fpath)
        # Only consider files created after download started
        if ftime >= download_start_time and ftime > newest_mtime:
            newest_mtime = ftime
            downloaded_file = fname

if downloaded_file:
    downloaded_filepath = os.path.join(download_dir, downloaded_file)

    original_filename = wav_files[0]
    base_name, ext = os.path.splitext(original_filename)
    new_filename = f"{base_name} [vocals]{ext}"
    new_filepath = os.path.join(download_dir, new_filename)

    os.rename(downloaded_filepath, new_filepath)
    safe_print(f"Processing track 1/2: {new_filename}")
else:
    print("Download completed, but no new .mp3 file was detected.")

# --- Download instrumental (Music) track ---
try:
    save_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Save')]")))
    save_button.click()
    print("Clicked the 'Save' button")
except Exception as e:
    print("Could not click the 'Save' button:", e)
time.sleep(0.5)

try:
    music_button = wait.until(EC.element_to_be_clickable((
        By.XPATH,
        "/html/body/div/main/div[6]/div[2]/button[1]"
    )))
    music_button.click()
    print("Clicked the 'Music' download option")
    print("Progress: 95%",flush=True)
except Exception as e:
    print("Could not click the 'Music' button:", e)

# Record timestamp before instrumental download completes
download_start_time = time.time()

timeout = time.time() + 120
while time.time() < timeout:
    if not any(fname.endswith('.crdownload') for fname in os.listdir(download_dir)):
        break
    elapsed = 120 - (timeout - time.time())
    percent = 95 + int(4 * (elapsed / 120))
    print(f"Progress: {percent}%",flush=True)
    time.sleep(3)

print("Progress: 99%",flush=True)

# Find the .mp3 file that was created after download started
downloaded_file = None
newest_mtime = 0
for fname in os.listdir(download_dir):
    if fname.lower().endswith(".mp3"):
        fpath = os.path.join(download_dir, fname)
        ftime = os.path.getmtime(fpath)
        # Only consider files created after download started
        if ftime >= download_start_time and ftime > newest_mtime:
            newest_mtime = ftime
            downloaded_file = fname

if downloaded_file:
    downloaded_filepath = os.path.join(download_dir, downloaded_file)

    original_filename = wav_files[0]
    base_name, ext = os.path.splitext(original_filename)
    new_filename = f"{base_name} [no_vocals]{ext}"
    new_filepath = os.path.join(download_dir, new_filename)

    os.rename(downloaded_filepath, new_filepath)
    safe_print(f"Processing track 2/2: {new_filename}")
else:
    print("Download completed, but no new .mp3 file was detected.")

print("Progress: 100%",flush=True)

for fname in os.listdir(input_dir):
    path = os.path.join(input_dir, fname)
    try:
        os.remove(path)
        print(f"Deleted")
    except Exception:
        print(f"Could not delete")

time.sleep(1)
driver.quit()

end_time = time.time()
elapsed_time = end_time - start_time
print(f"Total script time: {elapsed_time:.2f} seconds")

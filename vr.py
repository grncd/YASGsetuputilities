import os
import time
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import platform
import subprocess
import time

def focus_window_by_title_substring(substring):
    system = platform.system()
    found = False

    if system == "Windows":
        try:
            import win32gui
            import win32con
            import win32api # For GetLastError (though pywintypes.error usually has it)

            def callback(hwnd, found_hwnds_list_ref):
                # This inner try-except is crucial for robustness with EnumWindows
                try:
                    if not win32gui.IsWindowVisible(hwnd) or not win32gui.IsWindowEnabled(hwnd):
                        return True # Continue enumeration

                    window_title = win32gui.GetWindowText(hwnd)
                    # Check if window_title is not None or empty before lowercasing
                    if window_title and substring.lower() in window_title.lower():
                        # print(f"Found window: '{window_title}' with HWND: {hwnd}")
                        try:
                            win32gui.SetForegroundWindow(hwnd)
                        except win32gui.error as e:
                            # Error 0 for SetForegroundWindow often means it's "not allowed"
                            # to steal focus without user interaction or specific privileges.
                            # The minimize/restore trick can sometimes bypass this.
                            if e.winerror == 0 or e.winerror == 5: # 0: No error, 5: Access Denied
                                # print(f"SetForegroundWindow failed initially (error {e.winerror}), trying workaround...")
                                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                                time.sleep(0.05) # Give OS a moment
                                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                                time.sleep(0.05) # Give OS a moment
                                win32gui.SetForegroundWindow(hwnd) # Try again
                            else:
                                # print(f"Could not set foreground for HWND {hwnd}: {e}")
                                # Don't stop enumeration if we can't focus, maybe another match will work
                                return True # Continue, maybe another window matches
                        
                        found_hwnds_list_ref.append(hwnd)
                        return False # Stop enumeration, we found and (tried to) focus
                except Exception as e_inner:
                    # Log errors from processing a specific window but continue enumeration
                    # print(f"Error processing HWND {hwnd}: {e_inner}. Last WinAPI Error: {win32api.GetLastError()}")
                    pass # Important to continue enumeration
                return True # Continue enumeration if no match or error for *this* window

            hwnds = []
            win32gui.EnumWindows(callback, hwnds) # Pass the list as the second arg (lParam)

            if hwnds: # hwnds list will contain the HWND if found and callback returned False
                print(f"Focused window containing '{substring}'.")
                found = True
            else:
                print(f"No visible window found with '{substring}' in title or could not focus.")

        except ImportError:
            print("pywin32 library not found. Please install it: pip install pywin32")
            return False # Explicitly return False on import error
        except Exception as e_outer: # Catch other potential errors from pywin32 setup
            print(f"An unexpected error occurred with pywin32: {e_outer}")
            return False

    elif system == "Linux":
        # ... (Linux code remains the same)
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

    elif system == "Darwin": # macOS
        # ... (macOS code remains the same)
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

    return found # Return the status

start_time = time.time()

# --- Set download_dir automatically ---
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
download_dir = os.path.join(parent_dir, "output","htdemucs")
os.makedirs(download_dir, exist_ok=True)

# Remove argument check and assignment
# if len(sys.argv) != 2:
#     print("Usage: python main.py <download_dir>")
#     sys.exit(1)
# download_dir = sys.argv[1]
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

# Initialize the Chrome driver.
driver = webdriver.Chrome(options=chrome_options)
driver.set_window_position(-2000,-3000)
# Open vocalremover.org
focus_window_by_title_substring("YASG")
driver.get("https://vocalremover.org/?patreon=1")
time.sleep(3)  # Allow the page to load

# Locate the file input element.
# Often file upload buttons are hidden behind a styled button.
# Here we use the file input directly.
try:
    file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
except Exception as e:
    print("Could not locate file input element:", e)
    driver.quit()
    exit(1)

# Find the only .wav file in the "input" subfolder.
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
    print("More than one .wav file found in 'input'; picking the first.")
    
file_path = os.path.abspath(os.path.join(input_dir, wav_files[0]))
print("Uploading file:", file_path.encode("utf-8"))

# Send the file path to the file input element.
file_input.send_keys(file_path)
time.sleep(3)

# Set up an explicit wait for various text changes.
wait = WebDriverWait(driver, 120)

# Progress: 0%
print("Progress: 0%",flush=true)

# After sending the file and waiting for "Uploading file…"
wait.until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Uploading file')]")))
print("Progress: 10%",flush=true)
time.sleep(3)

# Step 4/5: Now wait for either the AI message or "Loading..."
ai_msg_locator    = (By.XPATH, "//*[contains(text(), 'Artificial intelligence algorithm now works')]")
loading_locator   = (By.XPATH, "//*[contains(text(), 'Loading')]")

# Wait up to 120s for one of them to appear
start = time.time()
timeout = 120
while time.time() - start < timeout:
    if driver.find_elements(*ai_msg_locator):
        print("AI algorithm message detected")
        print("Progress: 20%",flush=true)
        time.sleep(3)
        wait.until(EC.visibility_of_element_located(loading_locator))
        print("'Loading...' appeared after AI message")
        print("Progress: 30%",flush=true)
        break
    elif driver.find_elements(*loading_locator):
        print("Skipped AI message; 'Loading...' detected directly")
        print("Progress: 30%",flush=true)
        break
    time.sleep(1)
else:
    raise RuntimeError("Neither AI message nor 'Loading...' appeared in time")

# In either case, wait for "Loading..." to finish
wait.until(EC.invisibility_of_element_located(loading_locator))
print("Processing complete")
print("Progress: 60%",flush=true)
time.sleep(0.2)

# Step 6: Click the "Save" button.
try:
    save_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Save')]")))
    save_button.click()
    print("Clicked the 'Save' button")
    print("Progress: 70%",flush=true)
except Exception as e:
    print("Could not click the 'Save' button:", e)
time.sleep(0.5)
existing_mp3s = set(f for f in os.listdir(download_dir) if f.lower().endswith('.mp3'))

# Alternative: match by the span text
try:
    vocal_button = wait.until(EC.element_to_be_clickable((
        By.XPATH,
        "//button[contains(@class,'white') and .//span[text()='Vocal']]"
    )))
    vocal_button.click()
    print("Clicked the 'Vocal' download option")
    print("Progress: 80%",flush=true)
except Exception as e:
    print("Could not click the 'Vocal' button:", e)

# Wait for the download to finish.
timeout = time.time() + 120  # wait up to 2 minutes for the download to complete
while time.time() < timeout:
    # Check for any file ending with .crdownload in the download directory.
    if not any(fname.endswith('.crdownload') for fname in os.listdir(download_dir)):
        break
    # Print progress between 80% and 99% based on elapsed time
    elapsed = 120 - (timeout - time.time())
    percent = 80 + int(19 * (elapsed / 120))
    print(f"Progress: {percent}%",flush=true)
    time.sleep(3)

print("Progress: 99%",flush=true)

all_mp3s = set(f for f in os.listdir(download_dir) if f.lower().endswith('.mp3'))
new_mp3s = all_mp3s - existing_mp3s

if new_mp3s:
    newest_file = max(new_mp3s, key=lambda f: os.path.getmtime(os.path.join(download_dir, f)))
    original_filename = wav_files[0]
    base_name, ext = os.path.splitext(original_filename)
    new_filename = f"{base_name} [vocals]{ext}"
    old_filepath = os.path.join(download_dir, newest_file)
    new_filepath = os.path.join(download_dir, new_filename)
    os.rename(old_filepath, new_filepath)
    print("Processing track 1/1:", new_filename)
else:
    print("Download completed, but no new .mp3 file was detected.")

print("Progress: 100%",flush=true)

# --- Cleanup Input Folder ---
for fname in os.listdir(input_dir):
    path = os.path.join(input_dir, fname)
    try:
        os.remove(path)
        print(f"Deleted")
    except Exception as e:
        print(f"Could not delete")

time.sleep(1)
driver.quit()



end_time = time.time()
elapsed_time = end_time - start_time
print(f"Total script time: {elapsed_time:.2f} seconds")

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import subprocess
import platform
import string
import random
import pyperclip
import sys # Import sys to explicitly flush stdout if needed

# === Utility function to focus window ===
def focus_window_by_title_substring(substring):
    # This function remains unchanged...
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
                                pass
                        
                        found_hwnds_list_ref.append(hwnd)
                        return False
                except Exception:
                    pass
                return True

            hwnds = []
            win32gui.EnumWindows(callback, hwnds)

            if hwnds:
                print(f"Focused window containing '{substring}'.", flush=True)
                found = True
            else:
                print(f"No visible window found with '{substring}' in title or could not focus.", flush=True)

        except ImportError:
            print("pywin32 library not found. Please install it: pip install pywin32", flush=True)
            return False
        except Exception as e_outer:
            print(f"An unexpected error occurred with pywin32: {e_outer}", flush=True)
            return False

    # ... other OS implementations for focus_window ...
    # They should also have flush=True added to their print statements.

    else:
        print(f"Unsupported operating system: {system}", flush=True)

    return found

# === Settings ===
HIDE_WINDOW = True

# === Utility functions ===
def generate_random_string(length=16):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# --- ADDING FLUSH=TRUE TO ALL PRINT STATEMENTS ---

def run_spotifydc():
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_experimental_option("prefs", {
        "profile.content_settings.exceptions.clipboard": {
            "[*.]": {"setting": 1},
        },
        "profile.content_settings.clipboard": 1
    })

    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"ERROR: Could not start Chrome/ChromeDriver. Is it installed? Details: {e}", flush=True)
        sys.exit(1)

    driver.get("https://accounts.spotify.com/en/login?continue=https%3A%2F%2Fopen.spotify.com%2F")
    print("Please log in. Waiting for redirect...", flush=True)

    redirected = False
    while not redirected:
        try:
            current_url = driver.current_url
        except Exception:
            print("Chrome window was closed. Restarting...", flush=True)
            try:
                driver.quit()
            except Exception:
                pass
            return "restart"
        if "open.spotify.com" in current_url and "accounts.spotify.com" not in current_url:
            print("Redirected to open.spotify.com", flush=True)
            redirected = True
        elif "spotify.com" in current_url and "/account/overview" in current_url:
            print("Redirected to account overview. Forcing redirect to open.spotify.com...", flush=True)
            driver.get("https://open.spotify.com/")
            redirected = True
        time.sleep(0.25)

    time.sleep(2)

    try:
        cookies = driver.get_cookies()
    except Exception:
        print("Chrome window was closed. Restarting...", flush=True)
        try:
            driver.quit()
        except Exception:
            pass
        return "restart"

    sp_dc_cookie = next((cookie['value'] for cookie in cookies if cookie['name'] == 'sp_dc'), None)

    if sp_dc_cookie:
        print(f"sp_dc cookie: {sp_dc_cookie}", flush=True)
    else:
        print("sp_dc cookie not found.", flush=True)

    if HIDE_WINDOW:
        try:
            driver.set_window_position(-2000, -3000)
        except Exception:
            print("Chrome window was closed. Restarting...", flush=True)
            try:
                driver.quit()
            except Exception:
                pass
            return "restart"

    focus_window_by_title_substring("YASG")
    try:
        driver.set_window_size(1280, 2000)
        driver.get("https://developer.spotify.com/dashboard")
    except Exception:
        print("Chrome window was closed. Restarting...", flush=True)
        try:
            driver.quit()
        except Exception:
            pass
        return "restart"
    print("Navigating to developer dashboard...", flush=True)
    time.sleep(2)

    try:
        print("Attempting to create a new app...", flush=True)
        create_app_button = driver.find_element(By.CLASS_NAME, "e-9934-visually-hidden")
        driver.execute_script("arguments[0].click();", create_app_button)
        time.sleep(1)

        create_button = driver.find_element(By.CLASS_NAME, "encore-text-body-medium-bold.e-9934-button-primary.e-9934-button")
        driver.execute_script("arguments[0].click();", create_button)
        time.sleep(2)

        create_button = driver.find_element(By.CLASS_NAME, "encore-text-body-medium-bold.e-9934-button-primary.e-9934-button")
        if create_button.text != "Save": 
            driver.execute_script("arguments[0].click();", create_button)
            time.sleep(2)

        print("Filling out app creation form...", flush=True)
        driver.find_element(By.ID, "name").send_keys(generate_random_string())
        driver.find_element(By.ID, "description").send_keys(generate_random_string())
        driver.find_element(By.ID, "newRedirectUri").send_keys("https://example.com/")

        api_checkbox = driver.find_element(By.ID, "apis-used-1")
        driver.execute_script("arguments[0].click();", api_checkbox)

        terms_checkbox = driver.find_element(By.ID, "termsAccepted")
        driver.execute_script("arguments[0].click();", terms_checkbox)

        time.sleep(0.5)

        final_create = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/main/div/div/form/div[2]/button")
        driver.execute_script("arguments[0].click();", final_create)
        print("Submitting form...", flush=True)
        time.sleep(4)

        print("Revealing client secret...", flush=True)
        show_secret_btns = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/main/div/div/div[4]/div/div/div[3]/button")
        driver.execute_script("arguments[0].click();", show_secret_btns)
        time.sleep(1)

        print("Copying client secret to clipboard...", flush=True)
        copy_buttons = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/main/div/div/div[4]/div/div/div[3]/div/button")
        driver.execute_script("arguments[0].click();", copy_buttons)
        time.sleep(1)
        
        client_secret = pyperclip.paste()
        print(f"Client Secret: {client_secret}", flush=True)

    except Exception as e:
        print(f"ERROR: An error occurred during Selenium automation: {e}", flush=True)
        print("This may be due to a change in Spotify's website structure.", flush=True)

    finally:
        print("Script finished. Closing browser.", flush=True)
        try:
            driver.quit()
        except Exception:
            pass
    return True

# Main loop to handle Chrome restarts
while True:
    result = run_spotifydc()
    if result == "restart":
        print("Restarting script due to Chrome window closure...", flush=True)
        continue
    else:
        break

import undetected_chromedriver as uc
import time
import subprocess
import platform
import string
import random
import ctypes
import sys # Import sys to explicitly flush stdout if needed
import requests
import re
import json
import base64

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
HIDE_WINDOW = True if platform.system() == "Windows" else False
errored = False

# === Utility functions ===
def generate_random_string(length=16):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# --- ADDING FLUSH=TRUE TO ALL PRINT STATEMENTS ---

def run_spotifydc():
    # Set up Chrome options
    chrome_options = uc.ChromeOptions()
    chrome_options.add_experimental_option("prefs", {
        "profile.content_settings.exceptions.clipboard": {
            "[*.]": {"setting": 1},
        },
        "profile.content_settings.clipboard": 1
    })

    # Enable performance logging to capture network requests
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    try:
        driver = uc.Chrome(options=chrome_options)
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
        print("sp_dc cookie not found. Closing Chrome and restarting...", flush=True)
        try:
            driver.quit()
        except Exception:
            pass
        return "restart"

    # Navigate to developer dashboard to get tokens
    print("Navigating to developer dashboard to extract tokens...", flush=True)
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

    try:
        driver.get("https://developer.spotify.com/dashboard")
    except Exception:
        print("Chrome window was closed. Restarting...", flush=True)
        try:
            driver.quit()
        except Exception:
            pass
        return "restart"

    # Wait for OAuth flow to complete and capture bearer token from network logs
    print("Waiting for OAuth flow to complete...", flush=True)
    time.sleep(5)  # Give it time for the token exchange to happen

    # Navigate to the create app page to ensure developer profile is initialized
    print("Navigating to create app page to initialize session...", flush=True)
    try:
        driver.get("https://developer.spotify.com/dashboard/create")
        time.sleep(3)  # Wait for page to fully load and session to initialize
    except Exception:
        print("Chrome window was closed. Restarting...", flush=True)
        try:
            driver.quit()
        except Exception:
            pass
        return "restart"

    # Extract bearer token from network logs
    print("Extracting bearer token from network traffic...", flush=True)
    try:
        bearer_token = None
        party_uri = None
        csrf_token = None

        # Get performance logs which contain network requests
        logs = driver.get_log('performance')

        for entry in logs:
            try:
                log_json = json.loads(entry['message'])
                message = log_json.get('message', {})
                method = message.get('method', '')

                # Look for Network.responseReceived events from the token endpoint
                if method == 'Network.responseReceived':
                    response = message.get('params', {}).get('response', {})
                    url = response.get('url', '')

                    # Check if this is the token endpoint
                    if 'accounts.spotify.com/api/token' in url:
                        # Get the request ID to fetch the response body
                        request_id = message.get('params', {}).get('requestId')

                        if request_id:
                            print("Found token endpoint response, extracting token...", flush=True)
                            try:
                                # Get the response body
                                response_body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                                body_content = response_body.get('body', '')

                                if body_content:
                                    token_data = json.loads(body_content)
                                    bearer_token = token_data.get('access_token')

                                    if bearer_token:
                                        print("Bearer token extracted from network response!", flush=True)
                                        break
                            except Exception as e:
                                # Response body might not be available for all requests
                                pass
            except Exception as e:
                continue

        if not bearer_token:
            print("ERROR: Could not extract bearer token from network traffic.", flush=True)
            print("Trying to extract from page source as fallback...", flush=True)

            # Fallback: try to extract from page source
            page_source = driver.page_source
            bearer_match = re.search(r'"accessToken":"([^"]+)"', page_source)
            if bearer_match:
                bearer_token = bearer_match.group(1)
            else:
                bearer_match = re.search(r'accessToken["\']?\s*:\s*["\']([^"\']+)["\']', page_source)
                if bearer_match:
                    bearer_token = bearer_match.group(1)

        if not bearer_token:
            print("ERROR: Could not extract bearer token from dashboard.", flush=True)
            try:
                driver.quit()
            except Exception:
                pass
            return "restart"

        print("Bearer token obtained successfully.", flush=True)

        # Extract CSRF token from network logs (look for API responses that include x-csrf-token header)
        csrf_token = None
        print("Extracting CSRF token from network traffic...", flush=True)

        for entry in logs:
            try:
                log_json = json.loads(entry['message'])
                message = log_json.get('message', {})
                method = message.get('method', '')

                # Look for Network.responseReceived events
                if method == 'Network.responseReceived':
                    response = message.get('params', {}).get('response', {})
                    url = response.get('url', '')
                    headers = response.get('headers', {})

                    # Only get CSRF token from developer.spotify.com API endpoints
                    if 'developer.spotify.com/api' in url:
                        csrf_from_header = headers.get('x-csrf-token') or headers.get('X-CSRF-Token')
                        if csrf_from_header:
                            csrf_token = csrf_from_header
                            print(f"Found CSRF token from developer API response: {url}", flush=True)
                            break
            except Exception:
                continue

        # If not found in network logs, try page source from the create page
        if not csrf_token:
            try:
                page_source = driver.page_source

                # Try multiple patterns to find CSRF token
                patterns = [
                    r'"csrfToken":"([^"]+)"',
                    r'"csrf_token":"([^"]+)"',
                    r'"csrf":"([^"]+)"',
                    r'csrfToken["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'csrf["\']?\s*:\s*["\']([^"\']+)["\']',
                ]

                for pattern in patterns:
                    csrf_match = re.search(pattern, page_source)
                    if csrf_match:
                        csrf_token = csrf_match.group(1)
                        print(f"Found CSRF token in page source with pattern: {pattern}", flush=True)
                        break
            except Exception as e:
                print(f"Could not get page source for CSRF token: {e}", flush=True)

        if not csrf_token:
            print("WARNING: Could not extract CSRF token, attempting without it...", flush=True)
            csrf_token = ""
        else:
            print(f"CSRF token obtained (length: {len(csrf_token)}).", flush=True)

    except Exception as e:
        print(f"ERROR: Failed to extract tokens: {e}", flush=True)
        try:
            driver.quit()
        except Exception:
            pass
        return "restart"

    # Try to extract partyUri from the page before closing
    party_uri = None
    print("Attempting to extract partyUri from page...", flush=True)
    try:
        page_source = driver.page_source
        party_match = re.search(r'"partyUri":"([^"]+)"', page_source)
        if party_match:
            party_uri = party_match.group(1)
            print(f"Party URI extracted from page: {party_uri}", flush=True)
    except Exception as e:
        print(f"Could not extract partyUri from page: {e}", flush=True)

    # Get all cookies from the browser before closing
    print("Extracting all cookies from browser...", flush=True)
    all_cookies = driver.get_cookies()

    # Close the browser - we don't need it anymore
    print("Closing browser, continuing with API requests...", flush=True)
    try:
        driver.quit()
    except Exception:
        pass
    finally:
        # Set driver to None to prevent destructor errors
        driver = None

    # Now use the tokens to make API requests
    try:
        # Create a session and add ALL cookies from the browser
        session = requests.Session()

        # Add all cookies to the session
        for cookie in all_cookies:
            session.cookies.set(
                name=cookie['name'],
                value=cookie['value'],
                domain=cookie.get('domain', '.spotify.com'),
                path=cookie.get('path', '/'),
                secure=cookie.get('secure', False)
            )

        print(f"Added {len(all_cookies)} cookies to session.", flush=True)

        # For brand new accounts, check and accept TOS FIRST before doing anything else
        print("Checking TOS acceptance status...", flush=True)
        try:
            tos_url = "https://developer.spotify.com/api/s4d/v1/tos-accepted-version"
            tos_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://developer.spotify.com/dashboard/create',
                'X-CSRF-Token': csrf_token,
                'Authorization': f'Bearer {bearer_token}',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }

            tos_response = session.get(tos_url, headers=tos_headers)
            print(f"TOS check status code: {tos_response.status_code}", flush=True)

            # Update CSRF token from response
            fresh_csrf = tos_response.headers.get('x-csrf-token') or tos_response.headers.get('X-CSRF-Token')
            if fresh_csrf:
                csrf_token = fresh_csrf
                print(f"Updated CSRF token from TOS check.", flush=True)

            # Check if TOS is accepted
            tos_accepted = False
            if tos_response.status_code == 200:
                try:
                    tos_version = tos_response.text.strip().strip('"')
                    # Version 0 means TOS is NOT accepted, need version 10
                    if tos_version and tos_version != 'null' and tos_version != '' and tos_version != '0':
                        tos_accepted = True
                        print(f"TOS already accepted (version: {tos_version})", flush=True)
                    else:
                        print(f"TOS version is {tos_version}, need to accept latest version", flush=True)
                except:
                    pass

            # If TOS not accepted, accept it now
            if not tos_accepted:
                print("TOS not accepted. Accepting TOS now...", flush=True)

                # Accept TOS version 10 (note: payload uses "value" not "version")
                accept_payload = {"value": 10}
                accept_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Referer': 'https://developer.spotify.com/dashboard',
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrf_token,
                    'Authorization': f'Bearer {bearer_token}',
                    'Origin': 'https://developer.spotify.com',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                }

                accept_response = session.put(tos_url, headers=accept_headers, json=accept_payload)
                print(f"TOS acceptance status: {accept_response.status_code}", flush=True)
                print(f"TOS acceptance response: {accept_response.text}", flush=True)

                if accept_response.status_code == 200:
                    print("TOS acceptance request completed.", flush=True)

                    # Update CSRF token from response
                    fresh_csrf = accept_response.headers.get('x-csrf-token') or accept_response.headers.get('X-CSRF-Token')
                    if fresh_csrf:
                        csrf_token = fresh_csrf
                        print(f"Updated CSRF token after TOS acceptance.", flush=True)

                    # Verify TOS was actually accepted by checking again
                    print("Verifying TOS acceptance...", flush=True)
                    verify_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
                        'Accept': 'application/json',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Referer': 'https://developer.spotify.com/dashboard/create',
                        'X-CSRF-Token': csrf_token,
                        'Authorization': f'Bearer {bearer_token}',
                        'Connection': 'keep-alive',
                        'Sec-Fetch-Dest': 'empty',
                        'Sec-Fetch-Mode': 'cors',
                        'Sec-Fetch-Site': 'same-origin',
                    }
                    verify_response = session.get(tos_url, headers=verify_headers)
                    verify_version = verify_response.text.strip().strip('"')
                    print(f"TOS version after acceptance: {verify_version}", flush=True)

                    # Update CSRF token from verification response
                    fresh_csrf = verify_response.headers.get('x-csrf-token') or verify_response.headers.get('X-CSRF-Token')
                    if fresh_csrf:
                        csrf_token = fresh_csrf
                        print(f"Updated CSRF token from verification.", flush=True)

                    if verify_version == '0' or verify_version == '' or verify_version == 'null':
                        print("WARNING: TOS acceptance did not persist! Version is still 0.", flush=True)
                else:
                    print(f"WARNING: TOS acceptance may have failed. Response: {accept_response.text}", flush=True)

                    # Update CSRF token even if failed
                    fresh_csrf = accept_response.headers.get('x-csrf-token') or accept_response.headers.get('X-CSRF-Token')
                    if fresh_csrf:
                        csrf_token = fresh_csrf
                        print(f"Updated CSRF token after TOS acceptance.", flush=True)
        except Exception as e:
            print(f"Could not check/accept TOS: {e}", flush=True)

        # If we didn't get partyUri from the page, try to fetch it from the applications list
        if not party_uri:
            print("Fetching partyUri from applications list...", flush=True)
            apps_list_url = "https://developer.spotify.com/api/s4d/v1/applications"

            apps_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://developer.spotify.com/dashboard',
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrf_token,
                'Authorization': f'Bearer {bearer_token}',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }

            apps_response = session.get(apps_list_url, headers=apps_headers)

            if apps_response.status_code != 200:
                print(f"ERROR: Failed to fetch applications list. Status code: {apps_response.status_code}", flush=True)
                print(f"Response: {apps_response.text}", flush=True)
                return "restart"

            # Update CSRF token from the response (it gets refreshed with each API call)
            fresh_csrf = apps_response.headers.get('x-csrf-token') or apps_response.headers.get('X-CSRF-Token')
            if fresh_csrf:
                csrf_token = fresh_csrf
                print(f"Updated CSRF token from API response (length: {len(csrf_token)}).", flush=True)

            try:
                apps_data = apps_response.json()
                applications = apps_data.get('applications', [])

                if applications and len(applications) > 0:
                    # Get partyUri from the first application
                    party_uri = applications[0].get('partyUri')
                    if party_uri:
                        print(f"Party URI obtained from applications list: {party_uri}", flush=True)

            except Exception as e:
                print(f"WARNING: Failed to parse applications list: {e}", flush=True)
        else:
            # We already have partyUri from the page, but still make the request to get fresh CSRF token
            print("Fetching fresh CSRF token from applications list...", flush=True)
            apps_list_url = "https://developer.spotify.com/api/s4d/v1/applications"

            apps_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://developer.spotify.com/dashboard',
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrf_token,
                'Authorization': f'Bearer {bearer_token}',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }

            apps_response = session.get(apps_list_url, headers=apps_headers)

            # Update CSRF token from the response (it gets refreshed with each API call)
            if apps_response.status_code == 200:
                fresh_csrf = apps_response.headers.get('x-csrf-token') or apps_response.headers.get('X-CSRF-Token')
                if fresh_csrf:
                    csrf_token = fresh_csrf
                    print(f"Updated CSRF token from API response (length: {len(csrf_token)}).", flush=True)

        # Final check - if we still don't have partyUri, try to decode it from bearer token
        if not party_uri:
            print("Attempting to extract partyUri from bearer token...", flush=True)
            try:
                # JWT tokens have 3 parts separated by dots: header.payload.signature
                parts = bearer_token.split('.')
                if len(parts) >= 2:
                    # Decode the payload (second part)
                    # Add padding if needed
                    payload = parts[1]
                    padding = 4 - len(payload) % 4
                    if padding != 4:
                        payload += '=' * padding

                    decoded = base64.urlsafe_b64decode(payload)
                    token_data = json.loads(decoded)

                    # Look for party URI or user ID in the token
                    if 'partyUri' in token_data:
                        party_uri = token_data['partyUri']
                        print(f"Party URI extracted from bearer token: {party_uri}", flush=True)
                    elif 'sub' in token_data or 'user_id' in token_data:
                        user_id = token_data.get('sub') or token_data.get('user_id')
                        print(f"Found user ID in token: {user_id}, but no partyUri", flush=True)
            except Exception as e:
                print(f"Could not decode bearer token: {e}", flush=True)

        # Try the parties API endpoint - this is the endpoint for new accounts!
        if not party_uri:
            print("Attempting to create/fetch partyUri for new account...", flush=True)
            try:
                # For new accounts, we need to POST to this endpoint to get a party URI
                person_party_url = "https://developer.spotify.com/api/ws4d/v1/parties/person-party-uri"
                person_party_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': 'https://developer.spotify.com/dashboard/create',
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrf_token,
                    'Authorization': f'Bearer {bearer_token}',
                    'Origin': 'https://developer.spotify.com',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                }

                person_party_response = session.post(person_party_url, headers=person_party_headers)
                print(f"Person party URI request status: {person_party_response.status_code}", flush=True)

                if person_party_response.status_code == 200 or person_party_response.status_code == 201:
                    # Update CSRF token from response
                    fresh_csrf = person_party_response.headers.get('x-csrf-token') or person_party_response.headers.get('X-CSRF-Token')
                    if fresh_csrf:
                        csrf_token = fresh_csrf
                        print(f"Updated CSRF token from person-party-uri response.", flush=True)

                    # The response should be the party URI as a JSON string
                    party_uri_response = person_party_response.json()
                    # Response is a JSON string like "spotify:b2b-party:..."
                    if isinstance(party_uri_response, str):
                        party_uri = party_uri_response
                        print(f"Party URI created for new account: {party_uri}", flush=True)
                    else:
                        print(f"Unexpected party URI response format: {party_uri_response}", flush=True)
                else:
                    print(f"Failed to get person party URI. Status: {person_party_response.status_code}", flush=True)
                    print(f"Response: {person_party_response.text}", flush=True)
            except Exception as e:
                print(f"Could not fetch person party URI: {e}", flush=True)

        # If still no party URI, it will be auto-generated when creating the first app
        if not party_uri:
            print("WARNING: No partyUri found. It will be auto-generated when creating the first app.", flush=True)

        # Now create the application
        print("Creating Spotify developer application...", flush=True)
        create_app_url = "https://developer.spotify.com/api/ws4d/v1/applications"

        app_name = generate_random_string()
        app_description = generate_random_string()

        create_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://developer.spotify.com/dashboard/create',
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf_token,
            'Authorization': f'Bearer {bearer_token}',
            'Origin': 'https://developer.spotify.com',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }

        create_payload = {
            "name": app_name,
            "description": app_description,
            "website": "",
            "redirectUris": ["https://example.org"]
        }

        # Only include partyUri if we have one
        if party_uri:
            create_payload["partyUri"] = party_uri

        # Debug output
        print(f"DEBUG: Bearer token length: {len(bearer_token) if bearer_token else 0}", flush=True)
        print(f"DEBUG: CSRF token: {csrf_token[:20]}..." if csrf_token else "DEBUG: CSRF token empty", flush=True)
        print(f"DEBUG: Party URI: {party_uri if party_uri else 'None (will be auto-generated)'}", flush=True)

        create_response = session.post(create_app_url, headers=create_headers, json=create_payload)

        if create_response.status_code != 200 and create_response.status_code != 201:
            print(f"ERROR: Failed to create application. Status code: {create_response.status_code}", flush=True)
            print(f"Response Text: {create_response.text}", flush=True)

            # Check if it's an email verification error
            try:
                error_data = create_response.json()
                error_message = error_data.get('message', '')

                if 'Email not verified' in error_message:
                    print(f"\n{'='*60}", flush=True)
                    print("EMAIL VERIFICATION REQUIRED", flush=True)
                    print(f"{'='*60}", flush=True)

                    # Update CSRF from error response
                    fresh_csrf = create_response.headers.get('x-csrf-token') or create_response.headers.get('X-CSRF-Token')
                    if fresh_csrf:
                        csrf_token = fresh_csrf

                    # Show Windows popup notification
                    if platform.system() == "Windows":
                        try:
                            import ctypes
                            # MB_ICONWARNING = 0x30, MB_TOPMOST = 0x40000, MB_SETFOREGROUND = 0x10000
                            MB_ICONWARNING = 0x30
                            MB_TOPMOST = 0x40000
                            MB_SETFOREGROUND = 0x10000
                            ctypes.windll.user32.MessageBoxW(
                                0,
                                "EMAIL VERIFICATION REQUIRED!\n\nA verification email is being sent to your inbox.\nPlease check your email and click the verification link.\n\nThe script will continue automatically once verified.",
                                "Spotify Developer - Email Verification",
                                MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND
                            )
                        except Exception as e:
                            print(f"Could not show popup notification: {e}", flush=True)
                    else:
                        msg = "EMAIL VERIFICATION REQUIRED!\n\nA verification email is being sent to your inbox.\nPlease check your email and click the verification link.\n\nThe script will continue automatically once verified."
                        title = "Spotify Developer - Email Verification"
                        
                        # Try Zenity (GNOME/standard)
                        import shutil
                        if shutil.which("zenity"):
                            try:
                                subprocess.run(["zenity", "--info", "--title", title, "--text", msg], check=False)
                            except: pass
                        # Try KDialog (KDE)
                        elif shutil.which("kdialog"):
                            try:
                                subprocess.run(["kdialog", "--msgbox", msg, "--title", title], check=False)
                            except: pass
                        # Try xmessage (X11)
                        elif shutil.which("xmessage"):
                            try:
                                subprocess.run(["xmessage", "-center", "-title", title, msg], check=False)
                            except: pass
                        # Try Tkinter (Python)
                        else:
                            try:
                                import tkinter
                                from tkinter import messagebox
                                root = tkinter.Tk()
                                root.withdraw()
                                messagebox.showinfo(title, msg)
                                root.destroy()
                            except: 
                                print("NOTIFICATION: EMAIL VERIFICATION REQUIRED! Check your inbox.", flush=True)

                    # Send verification email
                    print("Sending verification email...", flush=True)
                    send_email_url = "https://spclient.wg.spotify.com/email-verify/v1/send_verification_email"
                    send_email_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
                        'Accept': 'application/json',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Referer': 'https://developer.spotify.com/',
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {bearer_token}',
                        'Origin': 'https://developer.spotify.com',
                        'Connection': 'keep-alive',
                        'Sec-Fetch-Dest': 'empty',
                        'Sec-Fetch-Mode': 'cors',
                        'Sec-Fetch-Site': 'same-site',
                    }

                    try:
                        send_email_response = session.post(send_email_url, headers=send_email_headers)
                        if send_email_response.status_code == 200:
                            print("Verification email sent successfully!", flush=True)
                        else:
                            print(f"Email send status: {send_email_response.status_code}", flush=True)
                    except Exception as e:
                        print(f"Could not send verification email: {e}", flush=True)

                    print("Please check your email and click the verification link.", flush=True)
                    print("Waiting for email verification to complete...", flush=True)
                    print(f"{'='*60}\n", flush=True)

                    # Poll the developer-verified endpoint
                    verified = False
                    poll_count = 0
                    max_polls = 120  # Wait up to 10 minutes (120 * 5 seconds)

                    verify_check_url = "https://developer.spotify.com/api/s4d/v1/developer-verified"

                    while not verified and poll_count < max_polls:
                        poll_count += 1
                        time.sleep(5)  # Wait 5 seconds between checks

                        verify_check_headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
                            'Accept': 'application/json',
                            'Accept-Language': 'en-US,en;q=0.5',
                            'Referer': 'https://developer.spotify.com/dashboard',
                            'Content-Type': 'application/json',
                            'X-CSRF-Token': csrf_token,
                            'Authorization': f'Bearer {bearer_token}',
                            'Connection': 'keep-alive',
                            'Sec-Fetch-Dest': 'empty',
                            'Sec-Fetch-Mode': 'cors',
                            'Sec-Fetch-Site': 'same-origin',
                        }

                        try:
                            verify_check_response = session.get(verify_check_url, headers=verify_check_headers)

                            # Update CSRF token
                            fresh_csrf = verify_check_response.headers.get('x-csrf-token') or verify_check_response.headers.get('X-CSRF-Token')
                            if fresh_csrf:
                                csrf_token = fresh_csrf

                            if verify_check_response.status_code == 200:
                                is_verified = verify_check_response.text.strip().strip('"').lower() == 'true'
                                if is_verified:
                                    verified = True
                                    print(f"\n{'='*60}", flush=True)
                                    print("EMAIL VERIFIED SUCCESSFULLY!", flush=True)
                                    print(f"{'='*60}\n", flush=True)

                                    # Retry creating the application
                                    print("Retrying application creation...", flush=True)
                                    create_headers['X-CSRF-Token'] = csrf_token
                                    create_response = session.post(create_app_url, headers=create_headers, json=create_payload)
                                    break
                                else:
                                    print(f"Still waiting... (check {poll_count}/{max_polls})", flush=True)
                        except Exception as e:
                            print(f"Error checking verification status: {e}", flush=True)

                    if not verified:
                        print("ERROR: Email verification timeout. Please verify your email and try again.", flush=True)
                        return "restart"
                else:
                    print(f"Response JSON: {json.dumps(error_data, indent=2)}", flush=True)
            except:
                pass

            # Check again if the retry was successful
            if create_response.status_code != 200 and create_response.status_code != 201:
                print(f"ERROR: Failed to create application after retry. Status code: {create_response.status_code}", flush=True)
                print(f"Response Headers: {dict(create_response.headers)}", flush=True)

                if create_response.status_code == 403:
                    print("ERROR: 403 Forbidden encountered during application creation. Stopping process.", flush=True)
                    sys.exit(1)

                return "restart"

        # Update CSRF token from response for next request
        fresh_csrf = create_response.headers.get('x-csrf-token') or create_response.headers.get('X-CSRF-Token')
        if fresh_csrf:
            csrf_token = fresh_csrf
            print(f"Updated CSRF token from create response.", flush=True)

        try:
            app_data = create_response.json()

            # Response might be just a string (the client ID) or an object
            if isinstance(app_data, str):
                client_id = app_data
            else:
                client_id = app_data.get('clientId') or app_data.get('client_id') or app_data.get('id')

            if not client_id:
                print(f"ERROR: Could not extract client ID from response: {app_data}", flush=True)
                return "restart"

            print(f"Application created successfully!", flush=True)
            print(f"Client ID: {client_id}", flush=True)

        except Exception as e:
            print(f"ERROR: Failed to parse application creation response: {e}", flush=True)
            print(f"Response: {create_response.text}", flush=True)
            return "restart"

        # Now get the client secret
        print("Fetching client secret...", flush=True)
        secret_url = f"https://developer.spotify.com/api/s4d/v1/applications/{client_id}/secret"

        secret_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': f'https://developer.spotify.com/dashboard/{client_id}',
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf_token,
            'Authorization': f'Bearer {bearer_token}',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }

        secret_response = session.get(secret_url, headers=secret_headers)

        if secret_response.status_code != 200:
            print(f"ERROR: Failed to get client secret. Status code: {secret_response.status_code}", flush=True)
            print(f"Response: {secret_response.text}", flush=True)
            return "restart"

        try:
            secret_data = secret_response.json()

            # Response might be just a string (the secret) or an object
            if isinstance(secret_data, str):
                client_secret = secret_data
            else:
                client_secret = secret_data.get('clientSecret') or secret_data.get('client_secret') or secret_data.get('secret')

            if not client_secret:
                print(f"ERROR: Could not extract client secret from response: {secret_data}", flush=True)
                return "restart"

            print(f"Client Secret: {client_secret}", flush=True)
            print("Script finished successfully!", flush=True)

        except Exception as e:
            print(f"ERROR: Failed to parse client secret response: {e}", flush=True)
            print(f"Response: {secret_response.text}", flush=True)
            return "restart"

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network request failed: {e}", flush=True)
        return "restart"
    except Exception as e:
        print(f"ERROR: An error occurred during API requests: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return "restart"

    return True

# Main loop to handle Chrome restarts
while True:
    result = run_spotifydc()
    if result == "restart":
        print("Restarting script due to Chrome window closure...", flush=True)
    else:
        break






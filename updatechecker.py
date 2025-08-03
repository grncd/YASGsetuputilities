import subprocess
import hashlib
import os
import requests
import sys

UPDATE_URL = "https://raw.githubusercontent.com/grncd/YASGsetuputilities/refs/heads/main/update.py"
LOCAL_UPDATE_PATH = os.path.join(os.getenv("APPDATA") or ".", "syrics_update", "update.py")
LOCAL_HASH_PATH = os.path.join(os.path.dirname(LOCAL_UPDATE_PATH), "update.hash")

def update_syrics():
    print("Updating syrics...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "git+https://github.com/grncd/syrics.git"],
        check=True
    )

def download_update_script():
    print("Downloading update.py...")
    response = requests.get(UPDATE_URL)
    response.raise_for_status()
    return response.content

def file_hash(content):
    return hashlib.sha256(content).hexdigest()

def maybe_run_update_script():
    os.makedirs(os.path.dirname(LOCAL_UPDATE_PATH), exist_ok=True)

    new_content = download_update_script()
    new_hash = file_hash(new_content)

    if not os.path.exists(LOCAL_HASH_PATH):
        # First download: store file and hash, but don't run
        print("First-time download. Storing update.py without executing.")
        with open(LOCAL_UPDATE_PATH, "wb") as f:
            f.write(new_content)
        with open(LOCAL_HASH_PATH, "w") as f:
            f.write(new_hash)
        return

    with open(LOCAL_HASH_PATH, "r") as f:
        old_hash = f.read().strip()

    if new_hash != old_hash:
        print("update.py has changed. Running new update.py...")
        with open(LOCAL_UPDATE_PATH, "wb") as f:
            f.write(new_content)
        with open(LOCAL_HASH_PATH, "w") as f:
            f.write(new_hash)
        subprocess.run([sys.executable, LOCAL_UPDATE_PATH], check=True)
    else:
        print("No changes in update.py.")

if __name__ == "__main__":
    update_syrics()
    maybe_run_update_script()

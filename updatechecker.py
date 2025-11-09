import subprocess
import hashlib
import os
import requests
import sys
import time
import random

UPDATE_URL = "https://raw.githubusercontent.com/grncd/YASGsetuputilities/refs/heads/main/update.py"
LOCAL_UPDATE_PATH = os.path.join(os.getenv("APPDATA") or ".", "syrics_update", "update.py")
LOCAL_HASH_PATH = os.path.join(os.path.dirname(LOCAL_UPDATE_PATH), "update.hash")

def update_syrics():
    print("Updating syrics...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "syrics"],
        check=True
    )

def update_spotdl():
    print("Updating spotdl...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "spotdl"],
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

def get_datapath():
    # Parent directory of the folder containing this script
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_setup_utilities_path(datapath):
    return os.path.join(datapath, "setuputilities")

FILES_TO_UPDATE = [
    # (url, local_path)
    (
        "https://raw.githubusercontent.com/grncd/YASGsetuputilities/refs/heads/main/pyinstall.bat",
        lambda datapath: os.path.join(get_setup_utilities_path(datapath), "pyinstall.bat")
    ),
    (
        "https://raw.githubusercontent.com/grncd/YASGsetuputilities/refs/heads/main/spotifydc.py",
        lambda datapath: os.path.join(get_setup_utilities_path(datapath), "spotifydc.py")
    ),
    (
        "https://raw.githubusercontent.com/grncd/YASGsetuputilities/refs/heads/main/fullinstall.py",
        lambda datapath: os.path.join(get_setup_utilities_path(datapath), "fullinstall.py")
    ),
    (
        "https://raw.githubusercontent.com/grncd/YASGsetuputilities/refs/heads/main/updatechecker.py",
        lambda datapath: os.path.join(get_setup_utilities_path(datapath), "updatechecker.py")
    ),
    (
        "https://raw.githubusercontent.com/grncd/YASGsetuputilities/refs/heads/main/getlyrics.bat",
        lambda datapath: os.path.join(datapath, "getlyrics.bat")
    ),
    (
        "https://raw.githubusercontent.com/grncd/YASGsetuputilities/refs/heads/main/downloadsong.bat",
        lambda datapath: os.path.join(datapath, "downloadsong.bat")
    ),
    (
        "https://raw.githubusercontent.com/grncd/YASGsetuputilities/refs/heads/main/main.py",
        lambda datapath: os.path.join(datapath, "vocalremover", "main.py")
    ),
    (
        "https://raw.githubusercontent.com/grncd/YASGsetuputilities/refs/heads/main/vr.py",
        lambda datapath: os.path.join(datapath, "vocalremover", "vr.py")
    ),
]

def download_and_update_file(url, local_path):
    # Hash file will be local_path + ".hash"
    hash_path = local_path + ".hash"
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    response = requests.get(url)
    response.raise_for_status()
    content = response.content
    new_hash = file_hash(content)
    if not os.path.exists(hash_path):
        with open(local_path, "wb") as f:
            f.write(content)
        with open(hash_path, "w") as f:
            f.write(new_hash)
        print(f"Downloaded {os.path.basename(local_path)} (first time, not running).")
        return
    with open(hash_path, "r") as f:
        old_hash = f.read().strip()
    if new_hash != old_hash:
        with open(local_path, "wb") as f:
            f.write(content)
        with open(hash_path, "w") as f:
            f.write(new_hash)
        print(f"{os.path.basename(local_path)} updated.")
    else:
        print(f"No changes in {os.path.basename(local_path)}.")

def update_all_files():
    datapath = get_datapath()
    # Ensure vocalremover/input exists
    os.makedirs(os.path.join(datapath, "vocalremover", "input"), exist_ok=True)
    for url, path_func in FILES_TO_UPDATE:
        time.sleep(random.randint(1,2))  # Be polite to the server
        local_path = path_func(datapath)
        download_and_update_file(url, local_path)

if __name__ == "__main__":
    update_syrics()
    update_spotdl()
    maybe_run_update_script()
    update_all_files()

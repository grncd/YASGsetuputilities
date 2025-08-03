import os
import sys
import subprocess
import glob
import re # For parsing progress
from concurrent.futures import ThreadPoolExecutor, as_completed

def find_first_mp3(input_dir):
    """Finds the first .mp3 file in the specified directory."""
    mp3_files = glob.glob(os.path.join(input_dir, "*.mp3"))
    if not mp3_files:
        mp3_files = glob.glob(os.path.join(input_dir, "*.MP3")) # Case-insensitive check
    if mp3_files:
        return mp3_files[0]
    return None

def parse_demucs_progress(line):
    """
    Parses a line of Demucs output to find progress percentage.
    Returns percentage as a string (e.g., "75.3%") or None.
    """
    match_tqdm_percent = re.search(r"(\d{1,3}(?:\.\d{1,2})?%)\s*\|", line)
    if match_tqdm_percent:
        return match_tqdm_percent.group(1)

    match_tqdm_segment = re.search(r"(\d+)/(\d+)\s*\[", line)
    if not match_tqdm_segment:
        match_tqdm_segment = re.search(r"Segment\s+(\d+)/(\d+)", line, re.IGNORECASE)
    
    if match_tqdm_segment:
        try:
            done = int(match_tqdm_segment.group(1))
            total = int(match_tqdm_segment.group(2))
            if total > 0:
                percentage = (done / total) * 100
                return f"{percentage:.1f}%"
        except ValueError:
            pass
            
    match_direct_percent = re.search(r"(\d{1,3}(?:\.\d{1,2})?%)", line)
    if match_direct_percent:
        return match_direct_percent.group(1)
        
    return None

def convert_wav_to_mp3(wav_file_path, mp3_file_path, ffmpeg_path="ffmpeg"):
    """
    Converts a single WAV file to MP3 using ffmpeg at 320kbps.
    Returns (True, mp3_filename_basename) on success, or (False, error_message_string) on failure.
    """
    command = [
        ffmpeg_path,
        "-i", wav_file_path,
        "-codec:a", "libmp3lame",
        "-b:a", "320k",
        mp3_file_path,
        "-y",
        "-loglevel", "error"
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            return True, os.path.basename(mp3_file_path)
        else:
            error_message = f"Error converting {os.path.basename(wav_file_path)} to MP3."
            decoded_stdout = stdout.decode(errors='ignore').strip()
            decoded_stderr = stderr.decode(errors='ignore').strip()
            if decoded_stdout:
                error_message += f"\n  FFmpeg stdout: {decoded_stdout}"
            if decoded_stderr:
                error_message += f"\n  FFmpeg stderr: {decoded_stderr}"
            return False, error_message.strip()
            
    except FileNotFoundError:
        return False, f"Error: '{ffmpeg_path}' command not found. Ensure ffmpeg is installed and in PATH."
    except Exception as e:
        return False, f"Unexpected error during ffmpeg conversion of {os.path.basename(wav_file_path)}: {e}"

def main():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    output_directory = os.path.join(parent_dir, "output")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_folder = os.path.join(script_dir, "input")

    if not os.path.isdir(input_folder):
        print(f"Error: 'input' folder not found at {input_folder}")
        sys.exit(1)

    input_mp3_file = find_first_mp3(input_folder)
    if not input_mp3_file:
        print(f"Error: No .mp3 file found in the '{input_folder}' directory.")
        sys.exit(1)

    print(f"Found input MP3: {input_mp3_file}")
    print(f"Output directory: {output_directory}")

    # Use demucs.exe from venv/Scripts in parent directory
    demucs_exe_path = os.path.join(parent_dir, "venv", "Scripts", "demucs.exe")
    if not os.path.isfile(demucs_exe_path):
        print(f"Error: demucs.exe not found at {demucs_exe_path}")
        print("Please ensure Demucs is installed in the venv.")
        sys.exit(1)

    demucs_command = [
        demucs_exe_path,
        "--two-stems=vocals",
        input_mp3_file,
        "-o", output_directory,
        "-j", "4",
        "--filename", "{track} [{stem}].{ext}"
    ]

    print(f"\nRunning command: {' '.join(demucs_command)}\n")
    demucs_succeeded = False
    try:
        process = subprocess.Popen(
            demucs_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        print("--- Demucs Processing (Ctrl+C to interrupt) ---")
        for line in iter(process.stderr.readline, ''): # Reads stderr line by line
            if not line and process.poll() is not None: # Process ended and no more output
                break
            
            stripped_line = line.strip()
            progress_percentage = parse_demucs_progress(stripped_line)
            
            if progress_percentage:
                print(f"Progress: {progress_percentage}") # Print progress on a new line
            else:
                # Print other stderr lines directly (they include a newline)
                sys.stdout.write(line) 
            sys.stdout.flush() # Ensure timely output

        stdout_output, stderr_remaining_output = process.communicate()
        return_code = process.returncode

        if stdout_output: # Should be empty if Demucs only uses stderr for info
            print("\n--- Demucs Standard Output ---")
            print(stdout_output.strip())
        
        # Print any remaining stderr that wasn't line-by-line processed
        if stderr_remaining_output:
            cleaned_stderr_remaining = []
            for err_line in stderr_remaining_output.splitlines():
                if not parse_demucs_progress(err_line):
                    cleaned_stderr_remaining.append(err_line)
            if cleaned_stderr_remaining:
                print("\n--- Demucs Error Output (Final) ---")
                for err_line in cleaned_stderr_remaining:
                    print(err_line.strip())

        if return_code == 0:
            print("\n--- Demucs processing completed successfully. ---")
            demucs_succeeded = True
        else:
            print(f"\n--- Demucs processing failed with return code {return_code}. ---")
            # Script will proceed to input cleanup, then exit if demucs_succeeded is False

    except FileNotFoundError:
        print("Error: 'demucs' command not found.")
        print("Please ensure Demucs is installed and in your system's PATH.")
        sys.exit(1) # Exit early as Demucs is essential
    except Exception as e:
        print(f"An unexpected error occurred during Demucs processing: {e}")
        # Script will proceed to input cleanup, then exit if demucs_succeeded is False


    # --- INPUT FILE DELETION --- (Requirement 2)
    print("\n--- Cleaning up input folder ---")
    if os.path.isdir(input_folder):
        input_files_to_delete = glob.glob(os.path.join(input_folder, "*"))
        if not input_files_to_delete:
            print(f"No files found in '{input_folder}' to delete.")
        else:
            deleted_input_count = 0
            for file_path in input_files_to_delete:
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.remove(file_path)
                        print(f"Deleted from input: {os.path.basename(file_path)}")
                        deleted_input_count +=1
                    # Not attempting to delete subdirectories, only files.
                except OSError as e:
                    print(f"Warning: Could not delete '{os.path.basename(file_path)}' from input folder: {e}")
            print(f"Attempted to delete {len(input_files_to_delete)} item(s), successfully deleted {deleted_input_count} file(s) from input folder.")
    else:
        print(f"Input folder '{input_folder}' not found for cleanup (this shouldn't happen if script started correctly).")

    if not demucs_succeeded:
        print("Exiting due to Demucs processing failure.")
        sys.exit(1) # Exit if Demucs failed, after attempting input cleanup


    # --- BEGIN FFMPEG CONVERSION --- (Only if Demucs succeeded)
    print("\n--- Starting WAV to MP3 conversion (320kbps) ---")
    
    # Path where Demucs is expected to place WAV files, according to user's script
    demucs_output_wav_folder = os.path.join(output_directory,"htdemucs")
    wav_files_to_convert = glob.glob(os.path.join(demucs_output_wav_folder, "*.wav"))
    
    if not wav_files_to_convert:
        print(f"No .wav files found in '{demucs_output_wav_folder}' for conversion.")
    else:
        num_wav_files = len(wav_files_to_convert)
        print(f"Found {num_wav_files} .wav file(s) for conversion in '{demucs_output_wav_folder}':")

        tasks = []
        for wav_file in wav_files_to_convert:
            mp3_file_name = os.path.splitext(os.path.basename(wav_file))[0] + ".mp3"
            mp3_file_path = os.path.join(os.path.dirname(wav_file), mp3_file_name) # MP3 in same dir as WAV
            tasks.append({"wav_path": wav_file, "mp3_path": mp3_file_path})
        
        converted_count = 0
        failed_count = 0
        
        num_workers = os.cpu_count() or 1
        print(f"\nConverting {num_wav_files} file(s) using up to {num_workers} parallel ffmpeg process(es)...")

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_task = {
                executor.submit(convert_wav_to_mp3, task["wav_path"], task["mp3_path"]): task
                for task in tasks
            }

            for i, future in enumerate(as_completed(future_to_task)):
                task_info = future_to_task[future]
                wav_path_basename = os.path.basename(task_info["wav_path"])
                current_progress_prefix = f"  ({i+1}/{num_wav_files})"
                try:
                    success, result_message = future.result()
                    if success:
                        mp3_basename = result_message
                        print(f"{current_progress_prefix} SUCCESS: {wav_path_basename} -> {mp3_basename}")
                        converted_count += 1
                        
                        # --- WAV DELETION --- (Requirement 3)
                        try:
                            os.remove(task_info["wav_path"])
                            print(f"    SUCCESS: Deleted source WAV: {wav_path_basename}")
                        except OSError as e:
                            print(f"    WARNING: Could not delete source WAV {wav_path_basename}: {e}")
                    else:
                        error_details = result_message
                        print(f"{current_progress_prefix} FAILED converting {wav_path_basename}:")
                        for line in error_details.splitlines():
                            print(f"    {line}")
                        failed_count += 1
                except Exception as exc:
                    print(f"{current_progress_prefix} FAILED (unexpected exception) converting {wav_path_basename}: {exc}")
                    failed_count += 1
        
        print("\n--- MP3 Conversion Summary ---")
        print(f"Total WAV files found: {num_wav_files}")
        print(f"Successfully converted to MP3: {converted_count}")
        print(f"Failed conversions: {failed_count}")

        if failed_count > 0:
            print("\nPlease review error messages for failed conversions.")
        elif converted_count == 0 and num_wav_files > 0:
             print("No WAV files were successfully converted to MP3.")
        elif converted_count > 0:
             print("All found WAV files converted to MP3 successfully (and originals deleted).")

        # --- NO_VOCALS MP3 DELETION --- (Requirement 4)
        print("\n--- Deleting [no_vocals].mp3 files ---")
        no_vocals_pattern = os.path.join(demucs_output_wav_folder, "*[no_vocals].mp3")
        no_vocals_files_to_delete = glob.glob(no_vocals_pattern)

        if not no_vocals_files_to_delete:
            print(f"No '*[no_vocals].mp3' files found in '{demucs_output_wav_folder}' to delete.")
        else:
            deleted_no_vocals_count = 0
            for file_path in no_vocals_files_to_delete:
                try:
                    os.remove(file_path)
                    print(f"Deleted: {os.path.basename(file_path)}")
                    deleted_no_vocals_count += 1
                except OSError as e:
                    print(f"Warning: Could not delete '{os.path.basename(file_path)}': {e}")
            print(f"Found {len(no_vocals_files_to_delete)} '*[no_vocals].mp3' file(s), successfully deleted {deleted_no_vocals_count}.")
    
    print(f"\n--- Processing Finished ---")
    print(f"Check the '{demucs_output_wav_folder}' (inside '{output_directory}') for remaining MP3 files.")

if __name__ == "__main__":
    main()

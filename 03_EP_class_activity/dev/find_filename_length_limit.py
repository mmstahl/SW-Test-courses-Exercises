import os
import sys

def find_windows_filename_limits():
    # Get the directory where this script is running
    current_dir = os.path.abspath(os.getcwd())
    dir_len = len(current_dir) + 1 # Include the trailing backslash
    ext = ".obj"
    ext_len = len(ext)
    
    print(f"Current Directory: {current_dir}")
    print(f"Directory Path Length: {dir_len} characters")
    print("--------------------------------------------------")

    # --- PHASE 1: Find Individual Filename Limit (NTFS Max) ---
    # We use the Win32 extended path prefix '\\\\?\\' to completely bypass 
    # the 260 MAX_PATH limit, isolating ONLY the individual filename restriction.
    low = 1
    high = 1000
    individual_max = 0

    while low <= high:
        mid = (low + high) // 2
        # Construct raw name component: e.g., 'p000...' (length = mid)
        name_body = "p" + "0" * (mid - 1 - ext_len)
        filename = name_body + ext
        
        # Extended path syntax bypasses MAX_PATH restrictions
        test_path = "\\\\?\\" + os.path.join(current_dir, filename)
        
        try:
            with open(test_path, 'w') as f:
                f.write('')
            os.remove(test_path)
            individual_max = mid
            low = mid + 1  # Try a longer name
        except OSError:
            high = mid - 1 # Too long, try shorter

    # --- PHASE 2: Find the Standard Path Limit (MAX_PATH) ---
    # We drop the extended path prefix to see where standard Windows API calls fail.
    low = 1
    high = 1000
    standard_max = 0

    while low <= high:
        mid = (low + high) // 2
        name_body = "p" + "0" * (mid - 1 - ext_len)
        filename = name_body + ext
        test_path = os.path.join(current_dir, filename)
        
        try:
            with open(test_path, 'w') as f:
                f.write('')
            os.remove(test_path)
            standard_max = mid
            low = mid + 1
        except OSError:
            high = mid - 1

    # --- OUTPUT RESULTS ---
    print(f"RESULTS FOR THIS ENVIRONMENT:")
    print(f"1. Absolute max length for a single filename (NTFS limit): {individual_max} characters.")
    
    total_path_limit = dir_len + standard_max
    print(f"2. Max length for a filename in THIS specific folder: {standard_max} characters.")
    print(f"   -> (Total full path length reached: {total_path_limit} characters)")
    
    if total_path_limit >= 260:
        print("\n[!] Note: Long Paths appear to be ENABLED in your Windows Registry.")
    else:
        print("\n[!] Note: Standard Windows MAX_PATH (260 char) rules are active.")

if __name__ == "__main__":
    # Ensure we are running on Windows
    if sys.platform != "win32":
        print("This script is designed for Windows environments only.")
        sys.exit(1)
        
    find_windows_filename_limits()
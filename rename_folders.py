import os
import subprocess
import sys

def run_cmd(cmd, check=True):
    """Executes a shell command and returns stdout."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error executing command: {cmd}\n{result.stderr}")
    return result.stdout.strip()

def get_remote_branches():
    """Gets all remote branches excluding HEAD pointer."""
    run_cmd("git fetch --all")
    branches_raw = run_cmd("git branch -r")
    branches = []
    for line in branches_raw.splitlines():
        line = line.strip()
        if "->" in line:
            continue
        if line.startswith("origin/"):
            branches.append(line.replace("origin/", ""))
    return list(set(branches))

def rename_directories_in_current_branch():
    """Renames directories containing spaces to use underscores."""
    renamed_any = False
    
    # We walk bottom-up (topdown=False) so subfolder renames don't break parent path traversals
    for root, dirs, files in os.walk(".", topdown=False):
        # Ignore .git metadata directory
        if ".git" in root.split(os.sep):
            continue

        for dirname in dirs:
            if " " in dirname:
                old_path = os.path.normpath(os.path.join(root, dirname))
                new_dirname = dirname.replace(" ", "_")
                new_path = os.path.normpath(os.path.join(root, new_dirname))
                
                print(f"  [Directory] Renaming: '{old_path}' -> '{new_path}'")
                run_cmd(f'git mv "{old_path}" "{new_path}"')
                renamed_any = True

    return renamed_any

def main():
    if not os.path.exists(".git"):
        print("Error: Run this script from the root of your git repository.")
        sys.exit(1)

    branches = get_remote_branches()
    print(f"Found remote branches: {branches}\n")

    for branch in branches:
        print(f"=== Processing Branch: {branch} ===")
        
        # Checkout branch
        run_cmd(f"git checkout -B {branch} origin/{branch}")
        
        # Perform directory renames
        changes_made = rename_directories_in_current_branch()
        
        if changes_made:
            commit_msg = "refactor: rename directories replacing spaces with underscores"
            run_cmd(f'git commit -m "{commit_msg}"')
            print(f"  Pushing changes to origin/{branch}...")
            run_cmd(f"git push origin {branch}")
            print(f"  Successfully updated branch '{branch}'.\n")
        else:
            print(f"  No folders with spaces found on branch '{branch}'.\n")

    print("All branches processed successfully!")

if __name__ == "__main__":
    main()
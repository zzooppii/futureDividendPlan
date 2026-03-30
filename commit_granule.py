import subprocess

files = [
    "requirements.txt",
    "config.py",
    "README.md",
    "setup_data.py",
    "run_dashboard.py",
]

# Get remaining untracked files
p = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True)
untracked = p.stdout.splitlines()

# Combine lists and unique
all_files = sorted(list(set(files + untracked)))

for file_path in all_files:
    print(f"Adding and committing {file_path}")
    subprocess.run(["git", "add", file_path])
    subprocess.run(["git", "commit", "-m", f"feat: add {file_path}"])

print("All files committed individually.")

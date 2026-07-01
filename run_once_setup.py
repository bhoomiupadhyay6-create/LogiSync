# run_once_setup.py
# Run this file ONCE to create the LogiSync project structure.
# Delete this file after running it.

import os

# ─────────────────────────────────────────────
# Define every file we need to create
# os.path.join() builds file paths correctly on
# Windows (\), Mac (/), and Linux (/) automatically.
# NEVER use hardcoded slashes like "core/api/file.py"
# ─────────────────────────────────────────────

files_to_create = [
    # Entry point
    "LogiSync/main.py",

    # Requirements
    "LogiSync/requirements.txt",

    # Config package
    "LogiSync/config/__init__.py",
    "LogiSync/config/settings.py",

    # Core package
    "LogiSync/core/__init__.py",
    "LogiSync/core/excel_handler.py",
    "LogiSync/core/tracker.py",

    # Core > API sub-package
    "LogiSync/core/api/__init__.py",
    "LogiSync/core/api/base_api.py",
    "LogiSync/core/api/aftership_api.py",

    # GUI package
    "LogiSync/gui/__init__.py",
    "LogiSync/gui/app_window.py",

    # Utils package
    "LogiSync/utils/__init__.py",
    "LogiSync/utils/logger.py",

    # Logs folder placeholder
    "LogiSync/logs/.gitkeep",
]

print("🔧 Creating LogiSync project structure...\n")

for filepath in files_to_create:
    # os.path.dirname() gets the folder part of a path
    # e.g., "LogiSync/core/api/base_api.py" → "LogiSync/core/api"
    folder = os.path.dirname(filepath)

    # os.makedirs() creates the folder AND all parent folders
    # exist_ok=True means: don't crash if the folder already exists
    os.makedirs(folder, exist_ok=True)

    # Only create the file if it doesn't already exist
    # This prevents accidentally wiping a file you've already worked on
    if not os.path.exists(filepath):
        with open(filepath, "w") as f:
            # Write a comment so the file isn't completely empty
            # (some tools complain about completely empty .py files)
            if filepath.endswith(".py"):
                f.write(f"# {os.path.basename(filepath)}\n")
        print(f"  ✅ Created: {filepath}")
    else:
        print(f"  ⏭️  Already exists, skipping: {filepath}")

print("\n✅ LogiSync project skeleton is ready!")
print("📂 Open the LogiSync/ folder in VS Code to begin.")
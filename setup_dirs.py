from pathlib import Path
"""
Run this script ONCE to create the required folder structure.
Usage: python setup_dirs.py
"""
import os

BASE = str(Path(__file__).parent)

dirs = [
    r"data\raw",
    r"data\processed",
    r"outputs\figures",
    r"outputs\predictions",
    r"outputs\results",
    r"outputs\tables",
    r"models",
    r"notebooks",
    r"thesis_app",
]

print(f"Creating directory structure under {BASE}")
for d in dirs:
    full = os.path.join(BASE, d)
    os.makedirs(full, exist_ok=True)
    print(f"  {full}")

print("\nDone. Now run: python main.py")

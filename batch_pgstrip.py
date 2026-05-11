#!/usr/bin/env python3
import os

# -------------------------------
# STEP 0 — Set Tesseract language data path
# -------------------------------
os.environ["TESSDATA_PREFIX"] = os.path.expanduser("~/tessdata_best")
import subprocess
from pathlib import Path
import sys

def run_pgstrip(mkv_path: Path):
    """
    Runs PGSRip on a single MKV file.
    """
    print(f"\nProcessing: {mkv_path}")
    cmd = [
        "pgsrip",                  # make sure 'pgsrip' is in PATH
        str(mkv_path)
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Finished extracting subtitles for {mkv_path.name}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to extract subtitles for {mkv_path.name}")
        print(e)

def process_folder(folder: Path):
    """
    Recursively process all MKV files in a folder.
    """
    mkv_files = list(folder.rglob("*.mkv"))
    if not mkv_files:
        print("No MKV files found in folder.")
        return

    print(f"Found {len(mkv_files)} MKV file(s).")

    for mkv in mkv_files:
        run_pgstrip(mkv)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python batch_pgstrip.py <folder>")
        sys.exit(1)

    folder_path = Path(sys.argv[1])
    if not folder_path.is_dir():
        print(f"{folder_path} is not a valid folder.")
        sys.exit(1)

    process_folder(folder_path)

#!/usr/bin/env python3
import os

# -------------------------------
# STEP 0 — Set Tesseract language data path
# -------------------------------
os.environ["TESSDATA_PREFIX"] = os.path.expanduser("~/tessdata_best")
import subprocess
from pathlib import Path
import sys
import argparse

def run_pgstrip(mkv_path: Path, track_a=None, track_b=None, track_y=None):
    """
    Runs PGSRip on a single MKV file with optional track selection.
    
    Args:
        mkv_path: Path to MKV file
        track_a: Audio track index
        track_b: Subtitle track index  
        track_y: Video track index
    """
    print(f"\nProcessing: {mkv_path}")
    cmd = [
        sys.executable,
        "-m", "pgsrip",
        str(mkv_path)
    ]
    
    if track_a is not None:
        cmd.extend(["-a", str(track_a)])
    if track_b is not None:
        cmd.extend(["-b", str(track_b)])
    if track_y is not None:
        cmd.extend(["-y", str(track_y)])

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Finished extracting subtitles for {mkv_path.name}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to extract subtitles for {mkv_path.name}")
        print(e)

def process_folder(folder: Path, recursive=True, track_a=None, track_b=None, track_y=None):
    """
    Process all MKV files in a folder.
    
    Args:
        folder: Path to folder
        recursive: If True, search subdirectories. If False, only current folder.
        track_a, track_b, track_y: Optional track indices
    """
    if recursive:
        mkv_files = list(folder.rglob("*.mkv"))
    else:
        mkv_files = list(folder.glob("*.mkv"))
    
    if not mkv_files:
        print("No MKV files found in folder.")
        return

    print(f"Found {len(mkv_files)} MKV file(s).")

    for mkv in mkv_files:
        run_pgstrip(mkv, track_a, track_b, track_y)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract PGS subtitles from MKV files using pgsrip"
    )
    parser.add_argument("folder", type=str, help="Folder containing MKV files")
    parser.add_argument("-a", "--audio", type=int, help="Audio track index")
    parser.add_argument("-b", "--subtitle", type=int, help="Subtitle track index")
    parser.add_argument("-y", "--video", type=int, help="Video track index")
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only process MKV files in the specified folder, not subdirectories"
    )
    
    args = parser.parse_args()

    folder_path = Path(args.folder)
    if not folder_path.is_dir():
        print(f"{folder_path} is not a valid folder.")
        sys.exit(1)

    process_folder(
        folder_path,
        recursive=not args.no_recursive,
        track_a=args.audio,
        track_b=args.subtitle,
        track_y=args.video
    )

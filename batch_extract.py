#!/usr/bin/env python3
import os
os.environ["TESSDATA_PREFIX"] = os.path.expanduser("~/tessdata_best")

from pathlib import Path
import sys
import argparse
from subtitle_extractor import extract_subtitle

def process_folder(folder: Path, recursive=True, track_a=None, track_s=None, track_y=None, interactive=True):
    """
    Process all MKV files in a folder.
    
    Args:
        folder: Path to folder
        recursive: If True, search subdirectories. If False, only current folder.
        track_a: Audio track index (for pgsrip)
        track_s: Subtitle track index (auto-select)
        track_y: Video track index (for pgsrip)
        interactive: If True, prompt for subtitle selection
    """
    if recursive:
        mkv_files = list(folder.rglob("*.mkv"))
    else:
        mkv_files = list(folder.glob("*.mkv"))
    
    if not mkv_files:
        print("No MKV files found in folder.")
        return

    print(f"Found {len(mkv_files)} MKV file(s).")
    
    # For batch: interactive only on first file
    first_file = True

    for mkv in mkv_files:
        use_interactive = interactive and first_file and track_s is None
        
        extract_subtitle(
            mkv,
            subtitle_track_index=track_s,
            track_a=track_a,
            track_y=track_y,
            interactive=use_interactive
        )
        
        first_file = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract subtitles from MKV files (supports PGS, SRT, ASS, VobSub)"
    )
    parser.add_argument("path", type=str, help="MKV file or folder containing MKV files")
    parser.add_argument("-a", "--audio", type=int, help="Audio track index (for pgsrip)")
    parser.add_argument("-s", "--subtitle", type=int, help="Subtitle track index (auto-select)")
    parser.add_argument("-y", "--video", type=int, help="Video track index (for pgsrip)")
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only process MKV files in the specified folder, not subdirectories"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive subtitle track selection (use first track or -s index)"
    )
    
    args = parser.parse_args()

    input_path = Path(args.path)
    
    if input_path.is_file():
        if input_path.suffix.lower() != ".mkv":
            print(f"{input_path} is not an MKV file.")
            sys.exit(1)
        
        result = extract_subtitle(
            input_path,
            subtitle_track_index=args.subtitle,
            track_a=args.audio,
            track_y=args.video,
            interactive=not args.no_interactive
        )
        
        if result:
            print(f"\n✅ Success: {result}")
        else:
            print("\n❌ Extraction failed")
            sys.exit(1)
            
    elif input_path.is_dir():
        process_folder(
            input_path,
            recursive=not args.no_recursive,
            track_a=args.audio,
            track_s=args.subtitle,
            track_y=args.video,
            interactive=not args.no_interactive
        )
    else:
        print(f"{input_path} is not a valid file or folder.")
        sys.exit(1)

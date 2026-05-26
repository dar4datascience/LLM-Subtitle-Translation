#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.audio_manager import AudioManager


def process_file(video_path: Path, track_index=None, output_path=None, 
                convert_to=None, interactive=True):
    """Extract audio from single video file."""
    if interactive and track_index is None:
        tracks = AudioManager.list_audio_tracks(video_path)
        if not tracks:
            print(f"No audio tracks found in {video_path}")
            return False
        
        selected = AudioManager.select_audio_track(tracks)
        if not selected:
            print("No track selected")
            return False
        track_index = selected.index
    
    result = AudioManager.extract_audio(
        video_path,
        output_path=output_path,
        track_index=track_index,
        convert_to=convert_to
    )
    
    return result is not None


def process_folder(folder_path: Path, recursive=True, track_index=None, 
                  convert_to=None, interactive=True):
    """Extract audio from all video files in folder."""
    if recursive:
        video_files = list(folder_path.rglob("*.mkv")) + list(folder_path.rglob("*.mp4"))
    else:
        video_files = list(folder_path.glob("*.mkv")) + list(folder_path.glob("*.mp4"))
    
    if not video_files:
        print("No video files found")
        return
    
    print(f"Found {len(video_files)} video file(s)")
    
    first_file = True
    for video in video_files:
        use_interactive = interactive and first_file and track_index is None
        process_file(video, track_index, None, convert_to, use_interactive)
        first_file = False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract audio tracks from video files"
    )
    parser.add_argument("path", type=str, help="Video file or folder containing video files")
    parser.add_argument("-t", "--track", type=int, help="Audio track index to extract")
    parser.add_argument("-o", "--output", type=str, help="Output audio file path")
    parser.add_argument(
        "-f", "--format",
        choices=['aac', 'mp3', 'flac', 'opus'],
        help="Convert audio to specified format (default: copy original codec)"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only process files in specified folder, not subdirectories"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive track selection (use first track or -t index)"
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.path)
    
    if input_path.is_file():
        output_path = Path(args.output) if args.output else None
        success = process_file(
            input_path,
            track_index=args.track,
            output_path=output_path,
            convert_to=args.format,
            interactive=not args.no_interactive
        )
        sys.exit(0 if success else 1)
    
    elif input_path.is_dir():
        process_folder(
            input_path,
            recursive=not args.no_recursive,
            track_index=args.track,
            convert_to=args.format,
            interactive=not args.no_interactive
        )
    
    else:
        print(f"{input_path} is not a valid file or folder")
        sys.exit(1)

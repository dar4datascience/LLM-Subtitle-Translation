#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.audio_manager import AudioManager


def merge_audio_files(video_path: Path, audio_path: Path, output_path=None,
                     replace=False, language="und"):
    """Merge audio file into video."""
    result = AudioManager.merge_audio(
        video_path,
        audio_path,
        output_path=output_path,
        replace=replace,
        audio_language=language
    )
    
    return result is not None


def select_audio_from_video(video_path: Path):
    """Interactive audio track selection from video."""
    tracks = AudioManager.list_audio_tracks(video_path)
    if not tracks:
        print("No audio tracks found")
        return
    
    selected = AudioManager.select_audio_track(tracks)
    if selected:
        print(f"\nSelected track: {selected}")
        print("\nTo use this track, extract it first:")
        print(f"  python scripts/extract_audio.py \"{video_path}\" -t {selected.index}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge audio track into video file"
    )
    parser.add_argument("video", type=str, help="Video file path")
    parser.add_argument("audio", nargs='?', type=str, help="Audio file path to merge")
    parser.add_argument("-o", "--output", type=str, help="Output video file path")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing audio tracks (default: add as new track)"
    )
    parser.add_argument(
        "-l", "--language",
        type=str,
        default="und",
        help="Language code for merged audio track (default: und)"
    )
    parser.add_argument(
        "--select-audio",
        action="store_true",
        help="Interactively select which audio track to use (no merging)"
    )
    
    args = parser.parse_args()
    
    video_path = Path(args.video)
    
    if not video_path.exists():
        print(f"Video file not found: {video_path}")
        sys.exit(1)
    
    if args.select_audio:
        select_audio_from_video(video_path)
        sys.exit(0)
    
    if not args.audio:
        print("Error: audio file required (or use --select-audio)")
        parser.print_help()
        sys.exit(1)
    
    audio_path = Path(args.audio)
    
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}")
        sys.exit(1)
    
    output_path = Path(args.output) if args.output else None
    
    success = merge_audio_files(
        video_path,
        audio_path,
        output_path=output_path,
        replace=args.replace,
        language=args.language
    )
    
    sys.exit(0 if success else 1)

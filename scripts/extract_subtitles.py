#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.subtitle_extractor import SubtitleExtractor
from src.language_detector import LanguageDetector


def process_file(video_path: Path, track_index=None, interactive=True, 
                detect_language=True, use_accurate=False):
    """Extract and tag subtitles from single video file."""
    srt_path = SubtitleExtractor.extract(
        video_path,
        subtitle_track_index=track_index,
        interactive=interactive
    )
    
    if not srt_path:
        print(f"Failed to extract subtitles from {video_path}")
        return False
    
    if detect_language:
        lang_code = LanguageDetector.detect_subtitle_language(
            srt_path,
            video_path=video_path,
            track_index=track_index,
            use_accurate=use_accurate
        )
        LanguageDetector.tag_subtitle_file(srt_path, lang_code)
    
    return True


def process_folder(folder_path: Path, recursive=True, track_index=None,
                  interactive=True, detect_language=True, use_accurate=False):
    """Extract and tag subtitles from all video files in folder."""
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
        process_file(video, track_index, use_interactive, detect_language, use_accurate)
        first_file = False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract subtitles with automatic language detection"
    )
    parser.add_argument("path", type=str, help="Video file or folder containing video files")
    parser.add_argument("-s", "--subtitle", type=int, help="Subtitle track index to extract")
    parser.add_argument(
        "--no-detect",
        action="store_true",
        help="Skip language detection (keep original filename)"
    )
    parser.add_argument(
        "--accurate",
        action="store_true",
        help="Use langid for more accurate detection (slower)"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only process files in specified folder, not subdirectories"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive track selection (use first track or -s index)"
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.path)
    
    if input_path.is_file():
        success = process_file(
            input_path,
            track_index=args.subtitle,
            interactive=not args.no_interactive,
            detect_language=not args.no_detect,
            use_accurate=args.accurate
        )
        sys.exit(0 if success else 1)
    
    elif input_path.is_dir():
        process_folder(
            input_path,
            recursive=not args.no_recursive,
            track_index=args.subtitle,
            interactive=not args.no_interactive,
            detect_language=not args.no_detect,
            use_accurate=args.accurate
        )
    
    else:
        print(f"{input_path} is not a valid file or folder")
        sys.exit(1)

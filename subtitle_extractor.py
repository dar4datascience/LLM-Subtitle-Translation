#!/usr/bin/env python3
import os
os.environ["TESSDATA_PREFIX"] = os.path.expanduser("~/tessdata_best")

import subprocess
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

class SubtitleTrack:
    def __init__(self, index: int, codec: str, language: str = "und"):
        self.index = index
        self.codec = codec
        self.language = language
    
    def __repr__(self):
        return f"Track {self.index}: {self.codec} ({self.language})"
    
    @property
    def is_text_based(self) -> bool:
        """Check if subtitle format is text-based (no OCR needed)"""
        text_codecs = ['subrip', 'srt', 'ass', 'ssa', 'webvtt', 'mov_text']
        return self.codec.lower() in text_codecs
    
    @property
    def is_image_based(self) -> bool:
        """Check if subtitle format is image-based (needs OCR)"""
        image_codecs = ['hdmv_pgs_subtitle', 'dvd_subtitle', 'dvdsub', 'vobsub']
        return self.codec.lower() in image_codecs

def detect_subtitle_tracks(video_path: Path) -> List[SubtitleTrack]:
    """
    Detect all subtitle tracks in video file using ffprobe.
    Returns list of SubtitleTrack objects.
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 's',
        '-show_entries', 'stream=index,codec_name:stream_tags=language',
        '-of', 'json',
        str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        tracks = []
        for stream in data.get('streams', []):
            index = stream.get('index')
            codec = stream.get('codec_name', 'unknown')
            language = stream.get('tags', {}).get('language', 'und')
            tracks.append(SubtitleTrack(index, codec, language))
        
        return tracks
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error detecting subtitle tracks: {e}")
        return []

def select_subtitle_track(tracks: List[SubtitleTrack], auto_select: Optional[int] = None) -> Optional[SubtitleTrack]:
    """
    Interactive subtitle track selection.
    
    Args:
        tracks: List of available subtitle tracks
        auto_select: If provided, auto-select this track index (for batch processing)
    
    Returns:
        Selected SubtitleTrack or None
    """
    if not tracks:
        print("No subtitle tracks found")
        return None
    
    if len(tracks) == 1:
        print(f"Found 1 subtitle track: {tracks[0]}")
        return tracks[0]
    
    # Auto-select if index provided
    if auto_select is not None:
        for track in tracks:
            if track.index == auto_select:
                print(f"Auto-selected: {track}")
                return track
        print(f"Warning: Track index {auto_select} not found, falling back to interactive selection")
    
    # Interactive selection
    print(f"\nFound {len(tracks)} subtitle tracks:")
    for i, track in enumerate(tracks):
        format_type = "text-based" if track.is_text_based else "image-based (OCR)"
        print(f"  {i+1}. {track} - {format_type}")
    
    while True:
        try:
            choice = input(f"\nSelect track (1-{len(tracks)}) or 'q' to skip: ").strip()
            if choice.lower() == 'q':
                return None
            
            idx = int(choice) - 1
            if 0 <= idx < len(tracks):
                return tracks[idx]
            else:
                print(f"Invalid choice. Enter 1-{len(tracks)}")
        except (ValueError, KeyboardInterrupt):
            print("\nSkipping subtitle extraction")
            return None

def extract_subtitle_ffmpeg(video_path: Path, track: SubtitleTrack) -> Optional[Path]:
    """
    Extract text-based subtitle using ffmpeg.
    Returns path to extracted SRT file or None if failed.
    """
    output_path = video_path.with_suffix('.en.srt')
    
    # Skip if already exists
    if output_path.exists():
        print(f"Subtitle already exists: {output_path}")
        return output_path
    
    print(f"Extracting {track.codec} subtitle from track {track.index}...")
    
    cmd = [
        'ffmpeg',
        '-i', str(video_path),
        '-map', f'0:{track.index}',
        '-c:s', 'srt',  # Convert to SRT format
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ Extracted: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to extract subtitle: {e}")
        return None

def extract_subtitle_pgsrip(video_path: Path, track: SubtitleTrack, track_a=None, track_y=None) -> Optional[Path]:
    """
    Extract image-based subtitle using pgsrip (with OCR).
    Returns path to extracted SRT file or None if failed.
    """
    output_path = video_path.with_suffix('.en.srt')
    
    # Skip if already exists
    if output_path.exists():
        print(f"Subtitle already exists: {output_path}")
        return output_path
    
    print(f"Extracting {track.codec} subtitle with OCR from track {track.index}...")
    
    cmd = [sys.executable, "-m", "pgsrip", str(video_path)]
    
    # pgsrip uses -b for subtitle track
    cmd.extend(["-b", str(track.index)])
    
    if track_a is not None:
        cmd.extend(["-a", str(track_a)])
    if track_y is not None:
        cmd.extend(["-y", str(track_y)])
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # Check for generated file
        if output_path.exists():
            print(f"✅ Extracted: {output_path}")
            return output_path
        else:
            # Try without language suffix
            alt_path = video_path.with_suffix('.srt')
            if alt_path.exists():
                print(f"✅ Extracted: {alt_path}")
                return alt_path
            else:
                print(f"❌ SRT file not found after extraction")
                return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to extract subtitle: {e}")
        return None

def extract_subtitle(video_path: Path, subtitle_track_index: Optional[int] = None, 
                    track_a=None, track_y=None, interactive: bool = True) -> Optional[Path]:
    """
    Main extraction function. Auto-detects format and uses appropriate extractor.
    
    Args:
        video_path: Path to video file
        subtitle_track_index: Optional subtitle track index for auto-selection
        track_a: Audio track index (for pgsrip)
        track_y: Video track index (for pgsrip)
        interactive: If True, prompt user for track selection. If False, use first track.
    
    Returns:
        Path to extracted SRT file or None
    """
    print(f"\nProcessing: {video_path}")
    
    # Detect subtitle tracks
    tracks = detect_subtitle_tracks(video_path)
    if not tracks:
        print("No subtitle tracks found")
        return None
    
    # Select track
    if interactive:
        selected_track = select_subtitle_track(tracks, auto_select=subtitle_track_index)
    else:
        # Non-interactive: use provided index or first track
        if subtitle_track_index is not None:
            selected_track = next((t for t in tracks if t.index == subtitle_track_index), None)
            if not selected_track:
                print(f"Track {subtitle_track_index} not found, using first track")
                selected_track = tracks[0]
        else:
            selected_track = tracks[0]
        print(f"Using: {selected_track}")
    
    if not selected_track:
        return None
    
    # Extract based on format
    if selected_track.is_text_based:
        return extract_subtitle_ffmpeg(video_path, selected_track)
    elif selected_track.is_image_based:
        return extract_subtitle_pgsrip(video_path, selected_track, track_a, track_y)
    else:
        print(f"Unsupported subtitle codec: {selected_track.codec}")
        return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract subtitles from video files")
    parser.add_argument("path", type=str, help="Video file path")
    parser.add_argument("-s", "--subtitle", type=int, help="Subtitle track index (auto-select)")
    parser.add_argument("-a", "--audio", type=int, help="Audio track index (for pgsrip)")
    parser.add_argument("-y", "--video", type=int, help="Video track index (for pgsrip)")
    parser.add_argument("--no-interactive", action="store_true", help="Disable interactive selection")
    
    args = parser.parse_args()
    
    video_path = Path(args.path)
    if not video_path.exists():
        print(f"File not found: {video_path}")
        sys.exit(1)
    
    result = extract_subtitle(
        video_path,
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

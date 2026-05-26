#!/usr/bin/env python3
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class AudioTrack:
    def __init__(self, index: int, codec: str, language: str = "und", 
                 channels: int = 2, sample_rate: int = 48000, bitrate: Optional[int] = None):
        self.index = index
        self.codec = codec
        self.language = language
        self.channels = channels
        self.sample_rate = sample_rate
        self.bitrate = bitrate
    
    def __repr__(self):
        bitrate_str = f"{self.bitrate//1000}kbps" if self.bitrate else "N/A"
        return f"Track {self.index}: {self.codec} ({self.language}) - {self.channels}ch, {self.sample_rate}Hz, {bitrate_str}"


class AudioManager:
    """Manage audio track extraction, merging, and conversion for video files."""
    
    @staticmethod
    def list_audio_tracks(video_path: Path) -> List[AudioTrack]:
        """
        List all audio tracks in video file using ffprobe.
        
        Args:
            video_path: Path to video file
            
        Returns:
            List of AudioTrack objects
        """
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'a',
            '-show_entries', 'stream=index,codec_name,channels,sample_rate,bit_rate:stream_tags=language',
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
                channels = stream.get('channels', 2)
                sample_rate = stream.get('sample_rate', 48000)
                bitrate = stream.get('bit_rate')
                
                if bitrate:
                    bitrate = int(bitrate)
                
                if isinstance(sample_rate, str):
                    sample_rate = int(sample_rate)
                
                tracks.append(AudioTrack(index, codec, language, channels, sample_rate, bitrate))
            
            return tracks
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(f"Error detecting audio tracks: {e}")
            return []
    
    @staticmethod
    def extract_audio(video_path: Path, output_path: Optional[Path] = None, 
                     track_index: Optional[int] = None, convert_to: Optional[str] = None) -> Optional[Path]:
        """
        Extract audio track from video file.
        
        Args:
            video_path: Path to video file
            output_path: Output audio file path (auto-generated if None)
            track_index: Specific audio track index (first track if None)
            convert_to: Convert to format (aac, mp3, flac, opus) or None to copy codec
            
        Returns:
            Path to extracted audio file or None if failed
        """
        tracks = AudioManager.list_audio_tracks(video_path)
        if not tracks:
            print("No audio tracks found")
            return None
        
        if track_index is not None:
            selected_track = next((t for t in tracks if t.index == track_index), None)
            if not selected_track:
                print(f"Track {track_index} not found, using first track")
                selected_track = tracks[0]
        else:
            selected_track = tracks[0]
        
        if output_path is None:
            if convert_to:
                ext = convert_to
            else:
                codec_ext_map = {
                    'aac': 'aac',
                    'mp3': 'mp3',
                    'flac': 'flac',
                    'opus': 'opus',
                    'vorbis': 'ogg',
                    'ac3': 'ac3',
                    'eac3': 'eac3',
                    'dts': 'dts',
                }
                ext = codec_ext_map.get(selected_track.codec, 'aac')
            
            output_path = video_path.with_name(f"{video_path.stem}_audio_track{selected_track.index}.{ext}")
        
        if output_path.exists():
            print(f"Audio file already exists: {output_path}")
            return output_path
        
        print(f"Extracting audio from track {selected_track.index} ({selected_track.codec})...")
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-map', f'0:{selected_track.index}',
        ]
        
        if convert_to:
            codec_map = {
                'aac': 'aac',
                'mp3': 'libmp3lame',
                'flac': 'flac',
                'opus': 'libopus',
            }
            codec = codec_map.get(convert_to, 'aac')
            cmd.extend(['-c:a', codec])
            
            if convert_to == 'mp3':
                cmd.extend(['-q:a', '2'])
            elif convert_to == 'aac':
                cmd.extend(['-b:a', '192k'])
        else:
            cmd.extend(['-c:a', 'copy'])
        
        cmd.append(str(output_path))
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ Extracted: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to extract audio: {e}")
            print(f"stderr: {e.stderr.decode()}")
            return None
    
    @staticmethod
    def merge_audio(video_path: Path, audio_path: Path, output_path: Optional[Path] = None,
                   replace: bool = False, audio_language: str = "und") -> Optional[Path]:
        """
        Merge audio track into video file.
        
        Args:
            video_path: Path to video file
            audio_path: Path to audio file to merge
            output_path: Output video file path (auto-generated if None)
            replace: If True, replace existing audio. If False, add as new track.
            audio_language: Language tag for merged audio track
            
        Returns:
            Path to output video file or None if failed
        """
        if output_path is None:
            output_path = video_path.with_name(f"{video_path.stem}_merged{video_path.suffix}")
        
        if output_path.exists():
            print(f"Output file already exists: {output_path}")
            return output_path
        
        print(f"Merging audio into video (replace={replace})...")
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-i', str(audio_path),
        ]
        
        if replace:
            cmd.extend([
                '-map', '0:v',
                '-map', '1:a',
            ])
        else:
            cmd.extend([
                '-map', '0',
                '-map', '1:a',
            ])
        
        cmd.extend([
            '-c:v', 'copy',
            '-c:a', 'copy',
            f'-metadata:s:a:0', f'language={audio_language}',
            str(output_path)
        ])
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ Merged: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to merge audio: {e}")
            print(f"stderr: {e.stderr.decode()}")
            return None
    
    @staticmethod
    def select_audio_track(tracks: List[AudioTrack], auto_select: Optional[int] = None) -> Optional[AudioTrack]:
        """
        Interactive audio track selection.
        
        Args:
            tracks: List of available audio tracks
            auto_select: If provided, auto-select this track index
            
        Returns:
            Selected AudioTrack or None
        """
        if not tracks:
            print("No audio tracks found")
            return None
        
        if len(tracks) == 1:
            print(f"Found 1 audio track: {tracks[0]}")
            return tracks[0]
        
        if auto_select is not None:
            for track in tracks:
                if track.index == auto_select:
                    print(f"Auto-selected: {track}")
                    return track
            print(f"Warning: Track index {auto_select} not found, falling back to interactive selection")
        
        print(f"\nFound {len(tracks)} audio tracks:")
        for i, track in enumerate(tracks):
            print(f"  {i+1}. {track}")
        
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
                print("\nSkipping audio selection")
                return None

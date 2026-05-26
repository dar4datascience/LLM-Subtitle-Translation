#!/usr/bin/env python3
from pathlib import Path
from typing import Optional, Tuple
import logging

from .subtitle_extractor import SubtitleExtractor
from .translator import Translator
from .language_detector import LanguageDetector
from .audio_manager import AudioManager


class VideoProcessor:
    """High-level coordinator for video processing operations."""
    
    def __init__(self, translator: Optional[Translator] = None):
        """
        Initialize video processor.
        
        Args:
            translator: Optional Translator instance (created if None)
        """
        self.translator = translator or Translator()
    
    def process_subtitles(self, video_path: Path, 
                         subtitle_track_index: Optional[int] = None,
                         track_a: Optional[int] = None,
                         track_y: Optional[int] = None,
                         interactive: bool = True,
                         detect_language: bool = True,
                         translate: bool = True,
                         batch_size: int = 50,
                         cleanup_original: bool = False) -> Tuple[bool, Optional[Path], Optional[Path]]:
        """
        Complete subtitle processing pipeline.
        
        Args:
            video_path: Path to video file
            subtitle_track_index: Optional subtitle track index
            track_a: Audio track index (for pgsrip)
            track_y: Video track index (for pgsrip)
            interactive: If True, prompt for track selection
            detect_language: If True, auto-detect and tag language
            translate: If True, translate to target language
            batch_size: Subtitle blocks per translation batch
            cleanup_original: If True, delete original SRT after translation
            
        Returns:
            Tuple of (success, original_srt_path, translated_srt_path)
        """
        logging.info(f"Processing video: {video_path}")
        
        srt_path = SubtitleExtractor.extract(
            video_path,
            subtitle_track_index=subtitle_track_index,
            track_a=track_a,
            track_y=track_y,
            interactive=interactive
        )
        
        if not srt_path:
            logging.error("Failed to extract subtitles")
            return (False, None, None)
        
        if detect_language:
            lang_code = LanguageDetector.detect_subtitle_language(
                srt_path,
                video_path=video_path,
                track_index=subtitle_track_index
            )
            srt_path = LanguageDetector.tag_subtitle_file(srt_path, lang_code)
        
        if not translate:
            return (True, srt_path, None)
        
        translated_path = self.translator.translate_srt(srt_path, batch_size=batch_size)
        
        if not translated_path:
            logging.error("Failed to translate subtitles")
            return (False, srt_path, None)
        
        if cleanup_original and srt_path.suffix.lower() == '.srt':
            try:
                srt_path.unlink()
                logging.info(f"Deleted original SRT: {srt_path}")
                return (True, None, translated_path)
            except Exception as e:
                logging.warning(f"Could not delete original SRT {srt_path}: {e}")
        
        return (True, srt_path, translated_path)
    
    def extract_audio_track(self, video_path: Path,
                          track_index: Optional[int] = None,
                          output_path: Optional[Path] = None,
                          convert_to: Optional[str] = None,
                          interactive: bool = True) -> Optional[Path]:
        """
        Extract audio track from video.
        
        Args:
            video_path: Path to video file
            track_index: Optional audio track index
            output_path: Optional output audio file path
            convert_to: Optional format to convert to (aac, mp3, flac, opus)
            interactive: If True, prompt for track selection
            
        Returns:
            Path to extracted audio file or None
        """
        if interactive and track_index is None:
            tracks = AudioManager.list_audio_tracks(video_path)
            selected = AudioManager.select_audio_track(tracks)
            if selected:
                track_index = selected.index
        
        return AudioManager.extract_audio(
            video_path,
            output_path=output_path,
            track_index=track_index,
            convert_to=convert_to
        )
    
    def merge_audio_track(self, video_path: Path, audio_path: Path,
                        output_path: Optional[Path] = None,
                        replace: bool = False,
                        audio_language: str = "und") -> Optional[Path]:
        """
        Merge audio track into video.
        
        Args:
            video_path: Path to video file
            audio_path: Path to audio file
            output_path: Optional output video path
            replace: If True, replace existing audio
            audio_language: Language tag for audio track
            
        Returns:
            Path to output video file or None
        """
        return AudioManager.merge_audio(
            video_path,
            audio_path,
            output_path=output_path,
            replace=replace,
            audio_language=audio_language
        )

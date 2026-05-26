#!/usr/bin/env python3
import subprocess
import json
from pathlib import Path
from typing import Optional, Tuple

try:
    from langdetect import detect, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException
    LANGDETECT_AVAILABLE = True
    DetectorFactory.seed = 0
except ImportError:
    LANGDETECT_AVAILABLE = False

try:
    import langid
    LANGID_AVAILABLE = True
except ImportError:
    LANGID_AVAILABLE = False


class LanguageDetector:
    """Detect language of subtitle files using text analysis and metadata."""
    
    ISO_639_1_TO_639_2 = {
        'en': 'eng', 'es': 'spa', 'fr': 'fra', 'de': 'deu', 'it': 'ita',
        'pt': 'por', 'ru': 'rus', 'ja': 'jpn', 'ko': 'kor', 'zh': 'zho',
        'ar': 'ara', 'hi': 'hin', 'nl': 'nld', 'pl': 'pol', 'tr': 'tur',
        'sv': 'swe', 'da': 'dan', 'no': 'nor', 'fi': 'fin', 'cs': 'ces',
        'el': 'ell', 'he': 'heb', 'th': 'tha', 'vi': 'vie', 'id': 'ind',
        'ro': 'ron', 'hu': 'hun', 'uk': 'ukr', 'bg': 'bul', 'hr': 'hrv',
        'sk': 'slk', 'sl': 'slv', 'sr': 'srp', 'ca': 'cat', 'et': 'est',
        'lv': 'lav', 'lt': 'lit', 'fa': 'fas', 'ur': 'urd', 'bn': 'ben',
    }
    
    @staticmethod
    def extract_text_from_srt(srt_path: Path, max_blocks: int = 10, min_chars: int = 100) -> str:
        """
        Extract text content from SRT file for language detection.
        
        Args:
            srt_path: Path to SRT file
            max_blocks: Maximum number of subtitle blocks to extract
            min_chars: Minimum characters needed for reliable detection
            
        Returns:
            Concatenated text from subtitle blocks
        """
        text_parts = []
        total_chars = 0
        blocks_read = 0
        
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                current_block = []
                for line in f:
                    line = line.strip()
                    
                    if line == "":
                        if current_block:
                            text_lines = [l for l in current_block if not l.isdigit() and '-->' not in l]
                            if text_lines:
                                text = ' '.join(text_lines)
                                text_parts.append(text)
                                total_chars += len(text)
                                blocks_read += 1
                                
                                if blocks_read >= max_blocks or total_chars >= min_chars * 2:
                                    break
                            current_block = []
                    else:
                        current_block.append(line)
                
                if current_block and blocks_read < max_blocks:
                    text_lines = [l for l in current_block if not l.isdigit() and '-->' not in l]
                    if text_lines:
                        text_parts.append(' '.join(text_lines))
            
            return ' '.join(text_parts)
        except Exception as e:
            print(f"Error reading SRT file: {e}")
            return ""
    
    @staticmethod
    def detect_from_text(text: str, use_accurate: bool = False) -> Tuple[Optional[str], float]:
        """
        Detect language from text content.
        
        Args:
            text: Text to analyze
            use_accurate: If True, use langid (slower, more accurate). If False, use langdetect (faster).
            
        Returns:
            Tuple of (ISO 639-2 language code, confidence score)
            Returns (None, 0.0) if detection fails
        """
        if not text or len(text) < 20:
            return (None, 0.0)
        
        if use_accurate and LANGID_AVAILABLE:
            try:
                lang_iso1, confidence = langid.classify(text)
                lang_iso2 = LanguageDetector.ISO_639_1_TO_639_2.get(lang_iso1, lang_iso1)
                return (lang_iso2, confidence)
            except Exception as e:
                print(f"langid detection failed: {e}")
                return (None, 0.0)
        
        elif LANGDETECT_AVAILABLE:
            try:
                lang_iso1 = detect(text)
                lang_iso2 = LanguageDetector.ISO_639_1_TO_639_2.get(lang_iso1, lang_iso1)
                confidence = 0.95
                return (lang_iso2, confidence)
            except LangDetectException as e:
                print(f"langdetect detection failed: {e}")
                return (None, 0.0)
        
        else:
            print("No language detection library available. Install langdetect or langid.")
            return (None, 0.0)
    
    @staticmethod
    def detect_from_metadata(video_path: Path, track_index: int) -> Optional[str]:
        """
        Get language from video file metadata using ffprobe.
        
        Args:
            video_path: Path to video file
            track_index: Subtitle track index
            
        Returns:
            ISO 639-2 language code or None
        """
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', f's:{track_index}',
            '-show_entries', 'stream_tags=language',
            '-of', 'json',
            str(video_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            for stream in data.get('streams', []):
                lang = stream.get('tags', {}).get('language')
                if lang and lang != 'und':
                    if len(lang) == 2:
                        return LanguageDetector.ISO_639_1_TO_639_2.get(lang, lang)
                    return lang
            
            return None
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(f"Error reading metadata: {e}")
            return None
    
    @staticmethod
    def detect_subtitle_language(srt_path: Path, video_path: Optional[Path] = None,
                                track_index: Optional[int] = None, use_accurate: bool = False,
                                confidence_threshold: float = 0.7) -> str:
        """
        Detect subtitle language using text analysis with metadata fallback.
        
        Args:
            srt_path: Path to SRT file
            video_path: Optional path to source video for metadata
            track_index: Optional subtitle track index for metadata
            use_accurate: Use langid instead of langdetect
            confidence_threshold: Minimum confidence to accept detection (default 0.7)
            
        Returns:
            ISO 639-2 language code (e.g., 'eng', 'spa') or 'und' if undetermined
        """
        text = LanguageDetector.extract_text_from_srt(srt_path)
        
        if text:
            lang, confidence = LanguageDetector.detect_from_text(text, use_accurate)
            
            if lang and confidence >= confidence_threshold:
                print(f"Detected language: {lang} (confidence: {confidence:.2f})")
                return lang
            elif lang:
                print(f"Low confidence detection: {lang} ({confidence:.2f}), checking metadata...")
        
        if video_path and track_index is not None:
            metadata_lang = LanguageDetector.detect_from_metadata(video_path, track_index)
            if metadata_lang:
                print(f"Using metadata language: {metadata_lang}")
                return metadata_lang
        
        print("Language undetermined, using 'und'")
        return 'und'
    
    @staticmethod
    def tag_subtitle_file(srt_path: Path, lang_code: str) -> Path:
        """
        Rename subtitle file with language tag.
        
        Args:
            srt_path: Path to SRT file
            lang_code: ISO 639-2 language code
            
        Returns:
            Path to renamed file
        """
        stem = srt_path.stem
        
        if stem.endswith('.en'):
            stem = stem[:-3]
        elif '.' in stem and len(stem.split('.')[-1]) in [2, 3]:
            parts = stem.split('.')
            if parts[-1] in ['en', 'es', 'fr', 'de', 'eng', 'spa', 'fra', 'deu', 'und']:
                stem = '.'.join(parts[:-1])
        
        new_path = srt_path.with_name(f"{stem}.{lang_code}.srt")
        
        if new_path != srt_path:
            try:
                srt_path.rename(new_path)
                print(f"Renamed: {srt_path.name} → {new_path.name}")
                return new_path
            except Exception as e:
                print(f"Failed to rename file: {e}")
                return srt_path
        
        return srt_path

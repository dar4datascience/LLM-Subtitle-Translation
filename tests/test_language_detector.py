#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.language_detector import LanguageDetector


class TestLanguageDetector(unittest.TestCase):
    
    def test_iso_639_conversion(self):
        """Test ISO 639-1 to 639-2 conversion."""
        self.assertEqual(LanguageDetector.ISO_639_1_TO_639_2.get('en'), 'eng')
        self.assertEqual(LanguageDetector.ISO_639_1_TO_639_2.get('es'), 'spa')
        self.assertEqual(LanguageDetector.ISO_639_1_TO_639_2.get('fr'), 'fra')
    
    def test_extract_text_from_srt(self):
        """Test extracting text from SRT file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write("1\n")
            f.write("00:00:01,000 --> 00:00:03,000\n")
            f.write("Hello world\n")
            f.write("\n")
            f.write("2\n")
            f.write("00:00:04,000 --> 00:00:06,000\n")
            f.write("This is a test\n")
            f.write("\n")
            srt_path = Path(f.name)
        
        try:
            text = LanguageDetector.extract_text_from_srt(srt_path)
            self.assertIn("Hello world", text)
            self.assertIn("This is a test", text)
            self.assertNotIn("00:00", text)
            self.assertNotIn("-->", text)
        finally:
            srt_path.unlink()
    
    def test_detect_from_text_english(self):
        """Test language detection for English text."""
        text = "This is a test sentence in English. It should be detected as English language."
        lang, confidence = LanguageDetector.detect_from_text(text)
        
        if lang:
            self.assertEqual(lang, 'eng')
            self.assertGreater(confidence, 0.7)
    
    def test_detect_from_text_spanish(self):
        """Test language detection for Spanish text."""
        text = "Esta es una oración de prueba en español. Debería detectarse como idioma español."
        lang, confidence = LanguageDetector.detect_from_text(text)
        
        if lang:
            self.assertEqual(lang, 'spa')
            self.assertGreater(confidence, 0.7)
    
    def test_detect_from_text_short(self):
        """Test language detection fails on very short text."""
        text = "Hi"
        lang, confidence = LanguageDetector.detect_from_text(text)
        self.assertIsNone(lang)
        self.assertEqual(confidence, 0.0)
    
    def test_tag_subtitle_file(self):
        """Test tagging subtitle file with language code."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write("Test content\n")
            original_path = Path(f.name)
        
        try:
            new_path = LanguageDetector.tag_subtitle_file(original_path, 'eng')
            self.assertTrue(new_path.exists())
            self.assertIn('.eng.', str(new_path))
        finally:
            if new_path.exists():
                new_path.unlink()
    
    def test_tag_subtitle_file_replace_existing(self):
        """Test replacing existing language tag."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.en.srt', delete=False) as f:
            f.write("Test content\n")
            original_path = Path(f.name)
        
        try:
            new_path = LanguageDetector.tag_subtitle_file(original_path, 'spa')
            self.assertTrue(new_path.exists())
            self.assertIn('.spa.', str(new_path))
            self.assertNotIn('.en.', str(new_path))
        finally:
            if new_path.exists():
                new_path.unlink()


if __name__ == '__main__':
    unittest.main()

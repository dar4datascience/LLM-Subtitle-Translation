#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.translator import Translator


class TestTranslator(unittest.TestCase):
    
    def test_translator_initialization(self):
        """Test Translator initialization."""
        translator = Translator()
        self.assertEqual(translator.model_name, "facebook/nllb-200-distilled-600M")
        self.assertEqual(translator.src_lang, "eng_Latn")
        self.assertEqual(translator.tgt_lang, "spa_Latn")
        self.assertIsNone(translator.model)
        self.assertIsNone(translator.tokenizer)
    
    def test_translator_custom_langs(self):
        """Test Translator with custom languages."""
        translator = Translator(src_lang="fra_Latn", tgt_lang="eng_Latn")
        self.assertEqual(translator.src_lang, "fra_Latn")
        self.assertEqual(translator.tgt_lang, "eng_Latn")
    
    def test_srt_output_path_generation(self):
        """Test SRT output path generation."""
        translator = Translator()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.en.srt', delete=False) as f:
            f.write("Test\n")
            srt_path = Path(f.name)
        
        try:
            stem = srt_path.stem
            if stem.endswith('.en'):
                stem = stem.rsplit('.', 1)[0]
            
            tgt_code = translator.tgt_lang.split('_')[0][:3]
            expected_output = srt_path.with_name(f"{stem}.{tgt_code}.srt")
            
            self.assertTrue(str(expected_output).endswith('.spa.srt'))
        finally:
            srt_path.unlink()


if __name__ == '__main__':
    unittest.main()

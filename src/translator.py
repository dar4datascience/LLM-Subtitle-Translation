#!/usr/bin/env python3
from pathlib import Path
from typing import Optional, Tuple
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import logging


class Translator:
    """Translate subtitle files using NLLB-200 model."""
    
    DEFAULT_MODEL = "facebook/nllb-200-distilled-600M"
    DEFAULT_SRC_LANG = "eng_Latn"
    DEFAULT_TGT_LANG = "spa_Latn"
    
    def __init__(self, model_name: str = DEFAULT_MODEL, 
                 src_lang: str = DEFAULT_SRC_LANG,
                 tgt_lang: str = DEFAULT_TGT_LANG):
        """
        Initialize translator with NLLB model.
        
        Args:
            model_name: HuggingFace model name
            src_lang: Source language code (NLLB format)
            tgt_lang: Target language code (NLLB format)
        """
        self.model_name = model_name
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.tokenizer = None
        self.model = None
    
    def load_model(self):
        """Load translation model and tokenizer."""
        if self.model is not None:
            return
        
        logging.info(f"Loading translation model: {self.model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, src_lang=self.src_lang)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        logging.info("Translation model loaded successfully")
    
    def translate_text(self, lines: list) -> list:
        """
        Translate list of text lines.
        
        Args:
            lines: List of strings to translate
            
        Returns:
            List of translated strings
        """
        if self.model is None:
            self.load_model()
        
        self.tokenizer.src_lang = self.src_lang
        batch = self.tokenizer(lines, return_tensors="pt", padding=True)
        forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(self.tgt_lang)
        translated_tokens = self.model.generate(**batch, forced_bos_token_id=forced_bos_token_id)
        translated = [self.tokenizer.decode(t, skip_special_tokens=True) for t in translated_tokens]
        return translated
    
    def translate_srt(self, srt_path: Path, output_path: Optional[Path] = None, 
                     batch_size: int = 50) -> Optional[Path]:
        """
        Translate SRT file from source to target language.
        
        Args:
            srt_path: Path to input SRT file
            output_path: Path to output SRT file (auto-generated if None)
            batch_size: Number of subtitle blocks to translate per batch
            
        Returns:
            Path to translated file or None if failed
        """
        if self.model is None:
            self.load_model()
        
        if output_path is None:
            stem = srt_path.stem
            if stem.endswith('.en') or stem.endswith('.eng'):
                stem = stem.rsplit('.', 1)[0]
            
            tgt_code = self.tgt_lang.split('_')[0][:3]
            output_path = srt_path.with_name(f"{stem}.{tgt_code}.srt")
        
        if output_path.exists():
            logging.info(f"⏭️  Skipping (already exists): {output_path}")
            return output_path
        
        logging.info(f"Translating: {srt_path} → {output_path}")
        
        try:
            lines_to_translate = []
            blocks = []
            
            with open(srt_path, "r", encoding="utf-8") as f:
                current_block = []
                for line in f:
                    line = line.rstrip("\n")
                    if line.strip() == "":
                        if current_block:
                            blocks.append(current_block)
                            current_block = []
                    else:
                        current_block.append(line)
                if current_block:
                    blocks.append(current_block)
            
            for block in blocks:
                text_lines = []
                for l in block:
                    if "-->" in l or l.isdigit():
                        continue
                    text_lines.append(l)
                lines_to_translate.append(" ".join(text_lines))
            
            translated_lines = []
            total_batches = (len(lines_to_translate) + batch_size - 1) // batch_size
            logging.info(f"Translating {len(lines_to_translate)} subtitles in {total_batches} batch(es) of {batch_size}")
            
            for i in range(0, len(lines_to_translate), batch_size):
                batch = lines_to_translate[i:i+batch_size]
                batch_num = i // batch_size + 1
                logging.info(f"  Batch {batch_num}/{total_batches}: {len(batch)} subtitles")
                translated_batch = self.translate_text(batch)
                translated_lines.extend(translated_batch)
            
            with open(output_path, "w", encoding="utf-8") as f:
                for block, trans_text in zip(blocks, translated_lines):
                    for l in block:
                        if "-->" in l or l.isdigit():
                            f.write(l + "\n")
                    f.write(trans_text + "\n\n")
            
            logging.info(f"✅ Translated: {output_path}")
            return output_path
        except Exception as e:
            logging.error(f"❌ Failed to translate {srt_path}: {e}")
            return None

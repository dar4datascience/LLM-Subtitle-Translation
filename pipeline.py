#!/usr/bin/env python3
import os
os.environ["TESSDATA_PREFIX"] = os.path.expanduser("~/tessdata_best")

import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime
import sys
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from tqdm import tqdm
from subtitle_extractor import extract_subtitle

# -------------------------------
# Setup Logging
# -------------------------------
def setup_logging(log_file: Path):
    """Setup logging to file and console"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# -------------------------------
# Load Translation Model
# -------------------------------
MODEL_NAME = "facebook/nllb-200-distilled-600M"
SRC_LANG = "eng_Latn"
TGT_LANG = "spa_Latn"

def load_translation_model():
    """Load NLLB model for translation"""
    logging.info(f"Loading translation model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, src_lang=SRC_LANG)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    logging.info("Translation model loaded successfully")
    return tokenizer, model

# -------------------------------
# Step 1: Extract Subtitles
# -------------------------------
def extract_subtitles(mkv_path: Path, track_a=None, track_b=None, track_y=None, interactive=True):
    """
    Extract subtitles from MKV file using auto-detection.
    Supports both text-based (SRT, ASS) and image-based (PGS, VobSub) formats.
    Returns Path to generated SRT file or None if failed.
    
    Args:
        mkv_path: Path to video file
        track_a: Audio track index (for pgsrip)
        track_b: Subtitle track index (auto-select this track)
        track_y: Video track index (for pgsrip)
        interactive: If True, prompt for track selection when multiple tracks exist
    """
    logging.info(f"Extracting subtitles from: {mkv_path}")
    
    try:
        srt_path = extract_subtitle(
            mkv_path,
            subtitle_track_index=track_b,
            track_a=track_a,
            track_y=track_y,
            interactive=interactive
        )
        
        if srt_path:
            logging.info(f"✅ Extracted subtitles: {srt_path}")
            return srt_path
        else:
            logging.error(f"❌ Failed to extract subtitles from {mkv_path}")
            return None
    except Exception as e:
        logging.error(f"❌ Failed to extract subtitles from {mkv_path}: {e}")
        return None

# -------------------------------
# Step 2: Translate Subtitles
# -------------------------------
def translate_text(lines, tokenizer, model):
    """Translate list of text lines using NLLB model"""
    tokenizer.src_lang = SRC_LANG
    batch = tokenizer(lines, return_tensors="pt", padding=True)
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(TGT_LANG)
    translated_tokens = model.generate(**batch, forced_bos_token_id=forced_bos_token_id)
    translated = [tokenizer.decode(t, skip_special_tokens=True) for t in translated_tokens]
    return translated

def translate_srt(srt_path: Path, tokenizer, model, batch_size=50):
    """
    Translate SRT file from English to Spanish.
    Returns Path to translated file or None if failed.
    
    Args:
        batch_size: Number of subtitle blocks to translate per batch (default: 50)
    """
    # Remove .en from stem if present, then add .es.srt
    stem = srt_path.stem
    if stem.endswith('.en'):
        stem = stem[:-3]  # Remove last 3 chars (.en)
    output_path = srt_path.with_name(stem + ".es.srt")
    
    # Skip if already translated
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
        
        # Extract text lines for translation
        for block in blocks:
            text_lines = []
            for l in block:
                if "-->" in l or l.isdigit():
                    continue
                text_lines.append(l)
            lines_to_translate.append(" ".join(text_lines))
        
        # Translate in batches to avoid OOM
        translated_lines = []
        total_batches = (len(lines_to_translate) + batch_size - 1) // batch_size
        logging.info(f"Translating {len(lines_to_translate)} subtitles in {total_batches} batch(es) of {batch_size}")
        
        for i in range(0, len(lines_to_translate), batch_size):
            batch = lines_to_translate[i:i+batch_size]
            batch_num = i // batch_size + 1
            logging.info(f"  Batch {batch_num}/{total_batches}: {len(batch)} subtitles")
            translated_batch = translate_text(batch, tokenizer, model)
            translated_lines.extend(translated_batch)
        
        # Write translated SRT
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

# -------------------------------
# Step 3: Process Pipeline
# -------------------------------
def process_mkv_file(mkv_path: Path, tokenizer, model, track_a=None, track_b=None, track_y=None, batch_size=50, interactive=True):
    """
    Full pipeline: Extract subtitles from MKV and translate to Spanish.
    Returns tuple (success: bool, srt_path, translated_path)
    
    Args:
        batch_size: Number of subtitle blocks to translate per batch
        interactive: If True, prompt for subtitle track selection
    """
    logging.info(f"Processing MKV: {mkv_path}")
    
    # Step 1: Extract
    srt_path = extract_subtitles(mkv_path, track_a, track_b, track_y, interactive=interactive)
    if not srt_path:
        return (False, None, None)
    
    # Step 2: Translate
    translated_path = translate_srt(srt_path, tokenizer, model, batch_size=batch_size)
    if not translated_path:
        return (False, srt_path, None)
    
    # Step 3: Clean up - delete original English SRT
    # Safety check: only delete .srt files, never video files
    if srt_path and srt_path.suffix.lower() == '.srt':
        try:
            srt_path.unlink()
            logging.info(f"Deleted original SRT: {srt_path}")
        except Exception as e:
            logging.warning(f"Could not delete original SRT {srt_path}: {e}")
    else:
        logging.warning(f"Skipped deletion - not an SRT file: {srt_path}")
    
    return (True, None, translated_path)

def process_folder(folder: Path, tokenizer, model, recursive=True, track_a=None, track_b=None, track_y=None, batch_size=50, interactive=True):
    """
    Process all MKV files in folder.
    Returns summary dict with success/failure counts.
    
    Args:
        batch_size: Number of subtitle blocks to translate per batch
        interactive: If True, prompt for subtitle selection on first file only
    """
    if recursive:
        mkv_files = list(folder.rglob("*.mkv"))
    else:
        mkv_files = list(folder.glob("*.mkv"))
    
    if not mkv_files:
        logging.warning("No MKV files found")
        return {"total": 0, "success": 0, "failed": 0}
    
    logging.info(f"Found {len(mkv_files)} MKV file(s)")
    
    results = {"total": len(mkv_files), "success": 0, "failed": 0, "files": []}
    
    # For batch processing: interactive only on first file, then use same track
    first_file = True
    
    for mkv in tqdm(mkv_files, desc="Processing MKV files"):
        # Interactive mode only for first file in batch (unless track_b specified)
        use_interactive = interactive and first_file and track_b is None
        
        success, srt_path, translated_path = process_mkv_file(
            mkv, tokenizer, model, track_a, track_b, track_y, 
            batch_size=batch_size, interactive=use_interactive
        )
        
        first_file = False
        
        if success:
            results["success"] += 1
            results["files"].append({
                "mkv": str(mkv),
                "status": "success",
                "srt": str(srt_path),
                "translated": str(translated_path)
            })
        else:
            results["failed"] += 1
            results["files"].append({
                "mkv": str(mkv),
                "status": "failed",
                "srt": str(srt_path) if srt_path else None,
                "translated": None
            })
    
    return results

# -------------------------------
# Main CLI
# -------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract PGS subtitles from MKV and translate EN→ES"
    )
    parser.add_argument("path", type=str, help="MKV file or folder containing MKV files")
    parser.add_argument("-a", "--audio", type=int, help="Audio track index")
    parser.add_argument("-b", "--subtitle", type=int, help="Subtitle track index")
    parser.add_argument("-y", "--video", type=int, help="Video track index")
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only process MKV files in specified folder, not subdirectories"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log file path (default: pipeline_YYYYMMDD_HHMMSS.log)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which MKV files will be processed without actually processing them"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of subtitle blocks to translate per batch (default: 50, lower = less memory)"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive subtitle track selection (use first track or -b index)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    if args.log_file:
        log_file = Path(args.log_file)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"pipeline_{timestamp}.log"
    
    logger = setup_logging(log_file)
    logging.info("="*60)
    if args.dry_run:
        logging.info("DRY RUN MODE - Preview Only")
    else:
        logging.info("Starting Subtitle Extraction & Translation Pipeline")
    logging.info(f"Log file: {log_file}")
    logging.info("="*60)
    
    # Process input
    input_path = Path(args.path)
    
    # Dry run: just list files
    if args.dry_run:
        if input_path.is_file():
            if input_path.suffix.lower() != ".mkv":
                logging.error(f"{input_path} is not an MKV file")
                sys.exit(1)
            logging.info(f"Would process 1 file:")
            logging.info(f"  - {input_path}")
        elif input_path.is_dir():
            if not args.no_recursive:
                mkv_files = list(input_path.rglob("*.mkv"))
            else:
                mkv_files = list(input_path.glob("*.mkv"))
            
            if not mkv_files:
                logging.warning("No MKV files found")
            else:
                logging.info(f"Would process {len(mkv_files)} file(s):")
                for mkv in sorted(mkv_files):
                    logging.info(f"  - {mkv}")
        else:
            logging.error(f"{input_path} is not a valid file or folder")
            sys.exit(1)
        
        logging.info("="*60)
        logging.info("Dry run complete. Use without --dry-run to process files.")
        logging.info("="*60)
        sys.exit(0)
    
    # Load translation model
    try:
        tokenizer, model = load_translation_model()
    except Exception as e:
        logging.error(f"Failed to load translation model: {e}")
        sys.exit(1)
    
    if input_path.is_file():
        if input_path.suffix.lower() != ".mkv":
            logging.error(f"{input_path} is not an MKV file")
            sys.exit(1)
        
        success, srt_path, translated_path = process_mkv_file(
            input_path, tokenizer, model,
            args.audio, args.subtitle, args.video,
            batch_size=args.batch_size,
            interactive=not args.no_interactive
        )
        
        if success:
            logging.info("="*60)
            logging.info("✅ Pipeline completed successfully!")
            logging.info(f"Output: {translated_path}")
            logging.info("="*60)
            
            # Delete log file on success
            logging.shutdown()
            if log_file.exists():
                log_file.unlink()
        else:
            logging.error("="*60)
            logging.error("❌ Pipeline failed")
            logging.error("="*60)
            sys.exit(1)
    
    elif input_path.is_dir():
        results = process_folder(
            input_path, tokenizer, model,
            recursive=not args.no_recursive,
            track_a=args.audio,
            track_b=args.subtitle,
            track_y=args.video,
            batch_size=args.batch_size,
            interactive=not args.no_interactive
        )
        
        logging.info("="*60)
        logging.info("Pipeline Summary")
        logging.info(f"Total files: {results['total']}")
        logging.info(f"Successful: {results['success']}")
        logging.info(f"Failed: {results['failed']}")
        logging.info("="*60)
        
        # Log detailed results
        for file_result in results["files"]:
            if file_result["status"] == "success":
                logging.info(f"✅ {file_result['mkv']}")
            else:
                logging.error(f"❌ {file_result['mkv']}")
        
        if results["failed"] > 0:
            sys.exit(1)
        else:
            # Delete log file on complete success
            logging.shutdown()
            if log_file.exists():
                log_file.unlink()
    
    else:
        logging.error(f"{input_path} is not a valid file or folder")
        sys.exit(1)

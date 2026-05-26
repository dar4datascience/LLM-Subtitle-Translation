#!/usr/bin/env python3
import os
os.environ["TESSDATA_PREFIX"] = os.path.expanduser("~/tessdata_best")

import argparse
import logging
from pathlib import Path
from datetime import datetime
import sys
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.video_processor import VideoProcessor
from src.translator import Translator

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
# Process Pipeline
# -------------------------------
def process_mkv_file(mkv_path: Path, processor: VideoProcessor, track_a=None, track_b=None, track_y=None, batch_size=50, interactive=True):
    """
    Full pipeline: Extract subtitles from MKV and translate to Spanish.
    Returns tuple (success: bool, srt_path, translated_path)
    
    Args:
        processor: VideoProcessor instance
        batch_size: Number of subtitle blocks to translate per batch
        interactive: If True, prompt for subtitle track selection
    """
    logging.info(f"Processing MKV: {mkv_path}")
    
    success, srt_path, translated_path = processor.process_subtitles(
        mkv_path,
        subtitle_track_index=track_b,
        track_a=track_a,
        track_y=track_y,
        interactive=interactive,
        detect_language=False,
        translate=True,
        batch_size=batch_size,
        cleanup_original=True
    )
    
    return (success, srt_path, translated_path)

def process_folder(folder: Path, processor: VideoProcessor, recursive=True, track_a=None, track_b=None, track_y=None, batch_size=50, interactive=True):
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
            mkv, processor, track_a, track_b, track_y, 
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
        translator = Translator()
        translator.load_model()
        processor = VideoProcessor(translator)
    except Exception as e:
        logging.error(f"Failed to load translation model: {e}")
        sys.exit(1)
    
    if input_path.is_file():
        if input_path.suffix.lower() != ".mkv":
            logging.error(f"{input_path} is not an MKV file")
            sys.exit(1)
        
        success, srt_path, translated_path = process_mkv_file(
            input_path, processor,
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
            input_path, processor,
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

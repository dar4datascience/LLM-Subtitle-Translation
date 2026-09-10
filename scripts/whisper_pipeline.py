#!/usr/bin/env python3
import sys
import argparse
import subprocess
import logging
import threading
import time
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.translator import Translator
from src.audio_manager import AudioManager


def setup_logging():
    """Setup logging to console"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def check_whisper_installed():
    """Check if Whisper CLI is available"""
    try:
        subprocess.run(['whisper', '--help'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def log_progress(process, video_duration: float, check_interval: int = 30):
    """
    Monitor Whisper process and log progress periodically.
    
    Args:
        process: subprocess.Popen object
        video_duration: Video duration in seconds
        check_interval: Seconds between progress logs
    """
    start_time = time.time()
    while process.poll() is None:
        time.sleep(check_interval)
        elapsed = time.time() - start_time
        elapsed_min = int(elapsed / 60)
        
        if video_duration > 0:
            video_min = int(video_duration / 60)
            logger.info(f"🔄 Whisper processing... {elapsed_min} min elapsed (video: {video_min} min)")
        else:
            logger.info(f"🔄 Whisper processing... {elapsed_min} min elapsed")


def generate_subtitles_with_whisper(video_path: Path, model: str = "medium", 
                                   language: str = "en", output_dir: Path = None) -> Path:
    """
    Generate subtitles from video audio using Whisper.
    
    Args:
        video_path: Path to video file
        model: Whisper model size (tiny, base, small, medium, large)
        language: Source language code (en, es, fr, etc.)
        output_dir: Output directory (defaults to video directory)
        
    Returns:
        Path to generated SRT file or None if failed
    """
    if output_dir is None:
        output_dir = video_path.parent
    
    expected_srt = output_dir / f"{video_path.stem}.{language}.srt"
    
    if expected_srt.exists():
        logger.info(f"⏭️  Subtitles already exist: {expected_srt}")
        return expected_srt
    
    duration = get_video_duration(video_path)
    duration_min = int(duration / 60) if duration > 0 else 0
    
    logger.info(f"Generating subtitles with Whisper (model={model}, lang={language})")
    logger.info(f"Video duration: {duration_min} min ({duration:.1f} sec)")
    logger.info(f"Estimated time: {int(duration_min * 0.5)}-{int(duration_min * 2)} min (varies by CPU)")
    
    cmd = [
        'whisper',
        str(video_path),
        '--model', model,
        '--language', language,
        '--output_format', 'srt',
        '--output_dir', str(output_dir),
        '--verbose', 'True'
    ]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        progress_thread = threading.Thread(
            target=log_progress,
            args=(process, duration, 30),
            daemon=True
        )
        progress_thread.start()
        
        for line in process.stdout:
            line = line.strip()
            if line and any(keyword in line.lower() for keyword in ['detecting', 'processing', 'progress', '%']):
                logger.info(f"  {line}")
        
        return_code = process.wait()
        
        if return_code != 0:
            logger.error(f"❌ Whisper failed with exit code {return_code}")
            return None
        
        if expected_srt.exists():
            logger.info(f"✅ Generated: {expected_srt}")
            return expected_srt
        else:
            alt_srt = output_dir / f"{video_path.stem}.srt"
            if alt_srt.exists():
                tagged_srt = output_dir / f"{video_path.stem}.{language}.srt"
                alt_srt.rename(tagged_srt)
                logger.info(f"✅ Generated: {tagged_srt}")
                return tagged_srt
            else:
                logger.error(f"❌ SRT file not found after Whisper processing")
                return None
    except Exception as e:
        logger.error(f"❌ Whisper failed: {e}")
        return None


def process_video(video_path: Path, translator: Translator, whisper_model: str = "medium",
                 source_lang: str = "en", translate: bool = True, 
                 cleanup_original: bool = False) -> tuple:
    """
    Complete pipeline: Generate subtitles with Whisper and translate.
    
    Args:
        video_path: Path to video file
        translator: Translator instance
        whisper_model: Whisper model size
        source_lang: Source language code
        translate: If True, translate to Spanish
        cleanup_original: If True, delete original SRT after translation
        
    Returns:
        Tuple of (success, original_srt_path, translated_srt_path)
    """
    logger.info(f"Processing: {video_path}")
    
    srt_path = generate_subtitles_with_whisper(
        video_path,
        model=whisper_model,
        language=source_lang
    )
    
    if not srt_path:
        return (False, None, None)
    
    if not translate:
        return (True, srt_path, None)
    
    translated_path = translator.translate_srt(srt_path)
    
    if not translated_path:
        logger.error("Failed to translate subtitles")
        return (False, srt_path, None)
    
    if cleanup_original and srt_path.suffix.lower() == '.srt':
        try:
            srt_path.unlink()
            logger.info(f"Deleted original SRT: {srt_path}")
            return (True, None, translated_path)
        except Exception as e:
            logger.warning(f"Could not delete original SRT {srt_path}: {e}")
    
    return (True, srt_path, translated_path)


def process_folder(folder_path: Path, translator: Translator, recursive: bool = True,
                  whisper_model: str = "medium", source_lang: str = "en",
                  translate: bool = True, cleanup_original: bool = False,
                  extensions: list = None) -> dict:
    """
    Process all video files in folder.
    
    Args:
        folder_path: Path to folder
        translator: Translator instance
        recursive: Search subdirectories
        whisper_model: Whisper model size
        source_lang: Source language code
        translate: If True, translate to Spanish
        cleanup_original: If True, delete original SRT
        extensions: List of video extensions (default: mp4, mkv, avi)
        
    Returns:
        Summary dict with success/failure counts
    """
    if extensions is None:
        extensions = ['*.mp4', '*.mkv', '*.avi']
    
    video_files = []
    for ext in extensions:
        if recursive:
            video_files.extend(folder_path.rglob(ext))
        else:
            video_files.extend(folder_path.glob(ext))
    
    if not video_files:
        logger.warning("No video files found")
        return {"total": 0, "success": 0, "failed": 0}
    
    logger.info(f"Found {len(video_files)} video file(s)")
    
    results = {"total": len(video_files), "success": 0, "failed": 0, "files": []}
    
    for video in tqdm(video_files, desc="Processing videos"):
        success, srt_path, translated_path = process_video(
            video, translator, whisper_model, source_lang, translate, cleanup_original
        )
        
        if success:
            results["success"] += 1
            results["files"].append({
                "video": str(video),
                "status": "success",
                "srt": str(srt_path) if srt_path else None,
                "translated": str(translated_path) if translated_path else None
            })
        else:
            results["failed"] += 1
            results["files"].append({
                "video": str(video),
                "status": "failed",
                "srt": None,
                "translated": None
            })
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate subtitles with Whisper and translate to Spanish"
    )
    parser.add_argument("path", type=str, help="Video file or folder containing videos")
    parser.add_argument(
        "-m", "--model",
        choices=["tiny", "base", "small", "medium", "large"],
        default="medium",
        help="Whisper model size (default: medium)"
    )
    parser.add_argument(
        "-l", "--language",
        default="en",
        help="Source language code (default: en)"
    )
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Skip translation (only generate subtitles)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete original SRT after translation"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only process files in specified folder, not subdirectories"
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=["*.mp4", "*.mkv", "*.avi"],
        help="Video file extensions to process (default: mp4 mkv avi)"
    )
    parser.add_argument(
        "--src-lang",
        default="eng_Latn",
        help="NLLB source language code (default: eng_Latn). Use fra_Latn for French, etc."
    )
    parser.add_argument(
        "--tgt-lang",
        default="spa_Latn",
        help="NLLB target language code (default: spa_Latn)."
    )

    args = parser.parse_args()
    
    if not check_whisper_installed():
        logger.error("❌ Whisper CLI not found. Install with: pip install openai-whisper")
        sys.exit(1)
    
    input_path = Path(args.path)
    
    if not input_path.exists():
        logger.error(f"Path does not exist: {input_path}")
        sys.exit(1)
    
    translator = None
    if not args.no_translate:
        logger.info(f"Loading translation model (src={args.src_lang}, tgt={args.tgt_lang})...")
        translator = Translator(src_lang=args.src_lang, tgt_lang=args.tgt_lang)
        translator.load_model()
    
    if input_path.is_file():
        if translator is None:
            translator = Translator(src_lang=args.src_lang, tgt_lang=args.tgt_lang)
            translator.load_model()

        success, srt_path, translated_path = process_video(
            input_path,
            translator,
            whisper_model=args.model,
            source_lang=args.language,
            translate=not args.no_translate,
            cleanup_original=args.cleanup
        )
        
        if success:
            logger.info("✅ Processing completed!")
            sys.exit(0)
        else:
            logger.error("❌ Processing failed")
            sys.exit(1)
    
    elif input_path.is_dir():
        if translator is None:
            translator = Translator(src_lang=args.src_lang, tgt_lang=args.tgt_lang)
            translator.load_model()

        results = process_folder(
            input_path,
            translator,
            recursive=not args.no_recursive,
            whisper_model=args.model,
            source_lang=args.language,
            translate=not args.no_translate,
            cleanup_original=args.cleanup,
            extensions=args.extensions
        )
        
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing Summary:")
        logger.info(f"  Total: {results['total']}")
        logger.info(f"  Success: {results['success']}")
        logger.info(f"  Failed: {results['failed']}")
        logger.info(f"{'='*50}")
        
        sys.exit(0 if results['failed'] == 0 else 1)
    
    else:
        logger.error(f"{input_path} is not a valid file or folder")
        sys.exit(1)

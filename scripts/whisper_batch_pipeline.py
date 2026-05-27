#!/usr/bin/env python3
import sys
import argparse
import logging
import time
from pathlib import Path
from tqdm import tqdm
import whisper
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.translator import Translator


def setup_logging():
    """Setup logging to console"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    import subprocess
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


def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(segments: list, output_path: Path):
    """Write Whisper segments to SRT file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text'].strip()
            
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")


def generate_subtitles_with_whisper(video_path: Path, model_name: str = "medium",
                                   language: str = "en", output_dir: Path = None,
                                   device: str = None, fp16: bool = True,
                                   skip_existing: bool = True) -> Path:
    """
    Generate subtitles using Whisper Python API with batching.
    
    Args:
        video_path: Path to video file
        model_name: Whisper model size (tiny, base, small, medium, large)
        language: Source language code
        output_dir: Output directory
        device: Device to use (cuda/cpu, auto-detect if None)
        fp16: Use FP16 precision (faster on GPU)
        
    Returns:
        Path to generated SRT file or None if failed
    """
    if output_dir is None:
        output_dir = video_path.parent
    
    expected_srt = output_dir / f"{video_path.stem}.{language}.srt"
    
    if expected_srt.exists():
        if skip_existing:
            logger.info(f"⏭️  Subtitles already exist: {expected_srt}")
            return expected_srt
        else:
            logger.info(f"📝 Reprocessing existing subtitles: {expected_srt}")
    
    duration = get_video_duration(video_path)
    duration_min = int(duration / 60) if duration > 0 else 0
    
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    logger.info(f"Generating subtitles with Whisper (model={model_name}, lang={language})")
    logger.info(f"Video duration: {duration_min} min ({duration:.1f} sec)")
    logger.info(f"Device: {device}, FP16: {fp16}")
    
    try:
        start_time = time.time()
        
        logger.info(f"Loading Whisper model '{model_name}'...")
        model = whisper.load_model(model_name, device=device)
        
        load_time = time.time() - start_time
        logger.info(f"Model loaded in {load_time:.1f} sec")
        
        logger.info("Transcribing audio...")
        transcribe_start = time.time()
        
        result = model.transcribe(
            str(video_path),
            language=language,
            fp16=fp16,
            verbose=True,
            task="transcribe"
        )
        
        transcribe_time = time.time() - transcribe_start
        logger.info(f"Transcription completed in {transcribe_time/60:.1f} min")
        
        logger.info(f"Writing SRT file: {expected_srt}")
        write_srt(result['segments'], expected_srt)
        
        total_time = time.time() - start_time
        logger.info(f"✅ Generated: {expected_srt}")
        logger.info(f"Total time: {total_time/60:.1f} min ({duration/transcribe_time:.1f}x realtime)")
        
        return expected_srt
        
    except Exception as e:
        logger.error(f"❌ Whisper failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def process_video(video_path: Path, translator: Translator, whisper_model: str = "medium",
                 source_lang: str = "en", translate: bool = True,
                 cleanup_original: bool = False, device: str = None,
                 fp16: bool = True, skip_existing: bool = True) -> tuple:
    """
    Complete pipeline: Generate subtitles with Whisper and translate.
    
    Args:
        video_path: Path to video file
        translator: Translator instance
        whisper_model: Whisper model size
        source_lang: Source language code
        translate: If True, translate to Spanish
        cleanup_original: If True, delete original SRT after translation
        device: Device to use (cuda/cpu)
        fp16: Use FP16 precision
        
    Returns:
        Tuple of (success, original_srt_path, translated_srt_path)
    """
    logger.info(f"Processing: {video_path}")
    
    srt_path = generate_subtitles_with_whisper(
        video_path,
        model_name=whisper_model,
        language=source_lang,
        device=device,
        fp16=fp16,
        skip_existing=skip_existing
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
                  extensions: list = None, device: str = None, fp16: bool = True,
                  skip_existing: bool = True) -> dict:
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
        extensions: List of video extensions
        device: Device to use
        fp16: Use FP16 precision
        
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
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0}
    
    # Sort videos: files without subtitles first
    def has_subtitle(video_path):
        return (video_path.parent / f"{video_path.stem}.{source_lang}.srt").exists()
    
    video_files.sort(key=lambda v: has_subtitle(v))
    
    logger.info(f"Found {len(video_files)} video file(s)")
    
    results = {"total": len(video_files), "success": 0, "failed": 0, "skipped": 0, "files": []}
    
    for video in tqdm(video_files, desc="Processing videos"):
        expected_srt = video.parent / f"{video.stem}.{source_lang}.srt"
        if skip_existing and expected_srt.exists():
            logger.info(f"⏭️  Skipping (subtitle exists): {video}")
            results["skipped"] += 1
            results["files"].append({
                "video": str(video),
                "status": "skipped",
                "srt": str(expected_srt),
                "translated": None
            })
            continue
        
        success, srt_path, translated_path = process_video(
            video, translator, whisper_model, source_lang, translate,
            cleanup_original, device, fp16, skip_existing
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
        description="Generate subtitles with Whisper (optimized) and translate to Spanish"
    )
    parser.add_argument("path", type=str, help="Video file or folder containing videos")
    parser.add_argument(
        "-m", "--model",
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisper model size (default: base)"
    )
    parser.add_argument(
        "-l", "--language",
        default="en",
        help="Source language code (default: en)"
    )
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu"],
        help="Device to use (auto-detect if not specified)"
    )
    parser.add_argument(
        "--no-fp16",
        action="store_true",
        help="Disable FP16 precision (use FP32)"
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
        "-s", "--skip-existing",
        action="store_true",
        default=True,
        help="Skip videos that already have subtitle files (default: True)"
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Reprocess videos even if subtitles already exist"
    )

    args = parser.parse_args()
    
    input_path = Path(args.path)
    
    if not input_path.exists():
        logger.error(f"Path does not exist: {input_path}")
        sys.exit(1)
    
    translator = None
    if not args.no_translate:
        logger.info("Loading translation model...")
        translator = Translator()
        translator.load_model()
    
    if input_path.is_file():
        if translator is None:
            translator = Translator()
        
        success, srt_path, translated_path = process_video(
            input_path,
            translator,
            whisper_model=args.model,
            source_lang=args.language,
            translate=not args.no_translate,
            cleanup_original=args.cleanup,
            device=args.device,
            fp16=not args.no_fp16,
            skip_existing=args.skip_existing
        )
        
        if success:
            logger.info("✅ Processing completed!")
            sys.exit(0)
        else:
            logger.error("❌ Processing failed")
            sys.exit(1)
    
    elif input_path.is_dir():
        if translator is None:
            translator = Translator()
        
        results = process_folder(
            input_path,
            translator,
            recursive=not args.no_recursive,
            whisper_model=args.model,
            source_lang=args.language,
            translate=not args.no_translate,
            cleanup_original=args.cleanup,
            extensions=args.extensions,
            device=args.device,
            fp16=not args.no_fp16,
            skip_existing=args.skip_existing
        )
        
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing Summary:")
        logger.info(f"  Total: {results['total']}")
        logger.info(f"  Success: {results['success']}")
        logger.info(f"  Skipped: {results['skipped']}")
        logger.info(f"  Failed: {results['failed']}")
        logger.info(f"{'='*50}")
        
        sys.exit(0 if results['failed'] == 0 else 1)
    
    else:
        logger.error(f"{input_path} is not a valid file or folder")
        sys.exit(1)

#!/usr/bin/env python3
import sys
import argparse
import logging
import time
from pathlib import Path
from tqdm import tqdm
from faster_whisper import WhisperModel
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
    """Write faster-whisper segments to SRT file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment.start)
            end = format_timestamp(segment.end)
            text = segment.text.strip()
            
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")


def load_whisper_model(model_name: str = "medium", device: str = None,
                       compute_type: str = "int8") -> WhisperModel:
    """
    Load faster-whisper model into RAM once for reuse across all videos.

    Args:
        model_name: Whisper model size (tiny, base, small, medium, large)
        device: Device to use (cuda/cpu, auto-detect if None)
        compute_type: Quantization type (int8 for fastest CPU, float32 for max accuracy)

    Returns:
        Loaded WhisperModel instance
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # float16 is only meaningful on GPU; fall back to float32 on CPU
    if compute_type == "float16" and device == "cpu":
        logger.warning("float16 compute_type is not supported on CPU, falling back to float32")
        compute_type = "float32"

    logger.info(f"Loading Whisper model '{model_name}' (device={device}, compute_type={compute_type})...")
    start_time = time.time()
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    load_time = time.time() - start_time
    logger.info(f"Whisper model loaded in {load_time:.1f} sec — resident in RAM")
    return model


def generate_subtitles_with_whisper(video_path: Path, model: WhisperModel,
                                   language: str = "en", output_dir: Path = None,
                                   skip_existing: bool = True) -> Path:
    """
    Generate subtitles using faster-whisper (model pre-loaded in RAM).

    Args:
        video_path: Path to video file
        model: Pre-loaded WhisperModel instance
        language: Source language code
        output_dir: Output directory
        skip_existing: Skip if SRT already exists

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

    logger.info(f"Transcribing: {video_path.name}")
    logger.info(f"Video duration: {duration_min} min ({duration:.1f} sec)")

    try:
        transcribe_start = time.time()

        segments, info = model.transcribe(
            str(video_path),
            language=language,
            task="transcribe"
        )

        logger.info(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")

        segments_list = list(segments)
        transcribe_time = time.time() - transcribe_start
        logger.info(f"Transcription completed in {transcribe_time/60:.1f} min")
        if duration > 0 and transcribe_time > 0:
            logger.info(f"Speed: {duration/transcribe_time:.1f}x realtime")

        logger.info(f"Writing SRT file: {expected_srt}")
        write_srt(segments_list, expected_srt)

        logger.info(f"✅ Generated: {expected_srt}")
        return expected_srt

    except Exception as e:
        logger.error(f"❌ Whisper failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def process_video(video_path: Path, translator: Translator, whisper_model: WhisperModel,
                 source_lang: str = "en", translate: bool = True,
                 cleanup_original: bool = False,
                 skip_existing: bool = True) -> tuple:
    """
    Complete pipeline: Generate subtitles with Whisper and translate.

    Args:
        video_path: Path to video file
        translator: Translator instance
        whisper_model: Pre-loaded WhisperModel instance (resident in RAM)
        source_lang: Source language code
        translate: If True, translate to Spanish
        cleanup_original: If True, delete original SRT after translation
        skip_existing: Skip if SRT already exists

    Returns:
        Tuple of (success, original_srt_path, translated_srt_path)
    """
    logger.info(f"Processing: {video_path}")

    srt_path = generate_subtitles_with_whisper(
        video_path,
        model=whisper_model,
        language=source_lang,
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
                  whisper_model: WhisperModel = None, source_lang: str = "en",
                  translate: bool = True, cleanup_original: bool = False,
                  extensions: list = None,
                  skip_existing: bool = True) -> dict:
    """
    Process all video files in folder.

    Args:
        folder_path: Path to folder
        translator: Translator instance
        recursive: Search subdirectories
        whisper_model: Pre-loaded WhisperModel instance (resident in RAM)
        source_lang: Source language code
        translate: If True, translate to Spanish
        cleanup_original: If True, delete original SRT
        extensions: List of video extensions
        skip_existing: Skip videos that already have subtitles

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
            cleanup_original, skip_existing
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
        "--compute-type",
        choices=["int8", "float32", "float16"],
        default="int8",
        help="Quantization type: int8 (fastest CPU), float32 (max accuracy), float16 (GPU only) (default: int8)"
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
    
    # Load Whisper model once into RAM — reused for every video
    whisper_model = load_whisper_model(
        model_name=args.model,
        device=args.device,
        compute_type=args.compute_type
    )

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
            whisper_model=whisper_model,
            source_lang=args.language,
            translate=not args.no_translate,
            cleanup_original=args.cleanup,
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
            whisper_model=whisper_model,
            source_lang=args.language,
            translate=not args.no_translate,
            cleanup_original=args.cleanup,
            extensions=args.extensions,
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

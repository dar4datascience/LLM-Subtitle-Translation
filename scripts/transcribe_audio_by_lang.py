#!/usr/bin/env python3
"""
Bulk transcribe a specific audio track (by language tag) from MKV/MP4 files.

For each video the script:
  1. Finds the audio track whose ffprobe language tag matches --audio-language
     (default: spa,es).
  2. Extracts it to a temporary 16 kHz mono WAV (whisper-friendly).
  3. Transcribes with faster-whisper (model loaded once into RAM).
  4. Writes a Jellyfin-compatible <video>.spa.srt next to the video.
  5. Deletes the temporary WAV (unless --keep-audio).

Videos without a matching audio track are skipped and logged.
"""
import sys
import argparse
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from tqdm import tqdm
from faster_whisper import WhisperModel
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.audio_manager import AudioManager, AudioTrack


def setup_logging():
    """Setup logging to console."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)


logger = setup_logging()


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


def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(segments: list, output_path: Path):
    """Write faster-whisper segments to an SRT file."""
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
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    if compute_type == "float16" and device == "cpu":
        logger.warning("float16 compute_type is not supported on CPU, falling back to float32")
        compute_type = "float32"

    logger.info(f"Loading Whisper model '{model_name}' (device={device}, compute_type={compute_type})...")
    start_time = time.time()
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    load_time = time.time() - start_time
    logger.info(f"Whisper model loaded in {load_time:.1f} sec — resident in RAM")
    return model


def extract_audio_track(video_path: Path, track: AudioTrack,
                        output_wav: Path) -> Optional[Path]:
    """
    Extract a specific audio track to a 16 kHz mono PCM WAV (whisper-friendly).

    Args:
        video_path: Source video
        track: AudioTrack to extract
        output_wav: Destination .wav path

    Returns:
        Path to the WAV file, or None on failure.
    """
    cmd = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-map', f'0:{track.index}',
        '-vn',
        '-ar', '16000',
        '-ac', '1',
        '-c:a', 'pcm_s16le',
        str(output_wav),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return output_wav
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ ffmpeg failed to extract track {track.index} from {video_path.name}: {e}")
        try:
            stderr = e.stderr.decode(errors='replace') if e.stderr else ''
            if stderr:
                logger.error(f"ffmpeg stderr: {stderr[:500]}")
        except Exception:
            pass
        return None


def transcribe_wav(wav_path: Path, model: WhisperModel, language: str = "es",
                   vad_filter: bool = True) -> Optional[list]:
    """
    Transcribe a WAV file with faster-whisper.

    Returns a list of segments, or None on failure.
    """
    try:
        transcribe_start = time.time()
        segments, info = model.transcribe(
            str(wav_path),
            language=language,
            task="transcribe",
            vad_filter=vad_filter,
            vad_parameters=dict(
                threshold=0.6,
                min_silence_duration_ms=500,
                speech_pad_ms=200,
                max_speech_duration_s=30,
            ),
            condition_on_previous_text=False,
            beam_size=5,
            word_timestamps=True,
            hallucination_silence_threshold=2.0,
        )
        logger.info(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
        segments_list = list(segments)
        transcribe_time = time.time() - transcribe_start
        logger.info(f"Transcription completed in {transcribe_time/60:.1f} min")
        return segments_list
    except Exception as e:
        logger.error(f"❌ Whisper failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def process_video(video_path: Path, model: WhisperModel,
                  lang_codes: List[str], source_lang: str = "es",
                  skip_existing: bool = True, vad_filter: bool = True,
                  keep_audio: bool = False,
                  tmp_dir: Optional[Path] = None) -> Tuple[str, Optional[Path]]:
    """
    Process a single video: find matching audio track, extract, transcribe, write SRT.

    Returns:
        (status, srt_path) where status is one of:
          "success", "skipped_existing", "skipped_no_spa", "failed"
    """
    expected_srt = video_path.with_name(f"{video_path.stem}.spa.srt")

    if skip_existing and expected_srt.exists():
        logger.info(f"⏭️  Subtitle already exists: {expected_srt}")
        return ("skipped_existing", expected_srt)

    track = AudioManager.find_track_by_language(video_path, lang_codes)
    if track is None:
        logger.warning(f"⚠️  No audio track matching {lang_codes} in {video_path.name} — skipping")
        return ("skipped_no_spa", None)

    logger.info(f"Found matching track {track.index} ({track.codec}, lang={track.language}) in {video_path.name}")

    duration = get_video_duration(video_path)
    duration_min = int(duration / 60) if duration > 0 else 0
    logger.info(f"Video duration: {duration_min} min ({duration:.1f} sec)")

    # Temp WAV next to the video (or in tmp_dir). PID suffix avoids collisions.
    wav_dir = tmp_dir if tmp_dir is not None else video_path.parent
    wav_path = wav_dir / f"{video_path.stem}.spa.{os.getpid()}.wav"

    extracted = extract_audio_track(video_path, track, wav_path)
    if extracted is None:
        return ("failed", None)

    try:
        segments = transcribe_wav(wav_path, model, language=source_lang, vad_filter=vad_filter)
        if segments is None:
            return ("failed", None)

        logger.info(f"Writing SRT file: {expected_srt}")
        write_srt(segments, expected_srt)
        logger.info(f"✅ Generated: {expected_srt}")
        return ("success", expected_srt)
    finally:
        if not keep_audio:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Could not delete temp WAV {wav_path}: {e}")
        else:
            logger.info(f"Kept extracted audio: {wav_path}")


def process_folder(folder_path: Path, model: WhisperModel,
                   recursive: bool = True, lang_codes: List[str] = None,
                   source_lang: str = "es", extensions: List[str] = None,
                   skip_existing: bool = True, vad_filter: bool = True,
                   keep_audio: bool = False,
                   tmp_dir: Optional[Path] = None) -> dict:
    """
    Process all matching video files in a folder.

    Returns a summary dict.
    """
    if lang_codes is None:
        lang_codes = ["spa", "es"]
    if extensions is None:
        extensions = ['*.mkv']

    video_files = []
    for ext in extensions:
        if recursive:
            video_files.extend(folder_path.rglob(ext))
        else:
            video_files.extend(folder_path.glob(ext))

    if not video_files:
        logger.warning("No video files found")
        return {"total": 0, "success": 0, "failed": 0,
                "skipped_no_spa": 0, "skipped_existing": 0, "files": []}

    # Sort: files without an existing SRT first (so work happens before skips in logs)
    video_files.sort(key=lambda v: (v.parent / f"{v.stem}.spa.srt").exists())

    logger.info(f"Found {len(video_files)} video file(s)")

    results = {
        "total": len(video_files), "success": 0, "failed": 0,
        "skipped_no_spa": 0, "skipped_existing": 0, "files": []
    }

    for video in tqdm(video_files, desc="Processing videos"):
        status, srt_path = process_video(
            video, model,
            lang_codes=lang_codes,
            source_lang=source_lang,
            skip_existing=skip_existing,
            vad_filter=vad_filter,
            keep_audio=keep_audio,
            tmp_dir=tmp_dir,
        )
        results[status] = results.get(status, 0) + 1
        results["files"].append({
            "video": str(video),
            "status": status,
            "srt": str(srt_path) if srt_path else None,
        })

    return results


def parse_lang_codes(value: str) -> List[str]:
    """Parse a comma-separated list of language codes."""
    return [c.strip() for c in value.split(',') if c.strip()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Bulk transcribe a specific audio track (by language tag) from MKV/MP4 files. "
            "Finds the Spanish (or specified) audio track, extracts it, transcribes with "
            "faster-whisper, and writes a Jellyfin-compatible <video>.spa.srt."
        )
    )
    parser.add_argument("path", type=str, help="Video file or folder containing videos")
    parser.add_argument(
        "-m", "--model",
        choices=["tiny", "base", "small", "medium", "large"],
        default="medium",
        help="Whisper model size (default: medium — better accuracy for Spanish)"
    )
    parser.add_argument(
        "-l", "--language",
        default="es",
        help="Source language code passed to Whisper (default: es)"
    )
    parser.add_argument(
        "--audio-language",
        default="spa,es",
        help="Comma-separated ffprobe language tags to match against audio tracks "
             "(default: spa,es). The first matching track is transcribed."
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
        "--no-recursive",
        action="store_true",
        help="Only process files in specified folder, not subdirectories"
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=["*.mkv"],
        help="Video file extensions to process (default: *.mkv)"
    )
    parser.add_argument(
        "-s", "--skip-existing",
        action="store_true",
        default=True,
        help="Skip videos that already have a .spa.srt file (default: True)"
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Reprocess videos even if a .spa.srt already exists"
    )
    parser.add_argument(
        "--no-vad",
        dest="vad_filter",
        action="store_false",
        default=True,
        help="Disable VAD filter (not recommended — may cause hallucination on long audio)"
    )
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Keep the extracted WAV file after transcription (default: delete)"
    )
    parser.add_argument(
        "--tmp-dir",
        type=str,
        default=None,
        help="Directory for temporary WAV files (default: alongside each video)"
    )

    args = parser.parse_args()

    input_path = Path(args.path)
    if not input_path.exists():
        logger.error(f"Path does not exist: {input_path}")
        sys.exit(1)

    lang_codes = parse_lang_codes(args.audio_language)
    tmp_dir = Path(args.tmp_dir) if args.tmp_dir else None
    if tmp_dir is not None:
        tmp_dir.mkdir(parents=True, exist_ok=True)

    whisper_model = load_whisper_model(
        model_name=args.model,
        device=args.device,
        compute_type=args.compute_type
    )

    if input_path.is_file():
        status, srt_path = process_video(
            input_path,
            whisper_model,
            lang_codes=lang_codes,
            source_lang=args.language,
            skip_existing=args.skip_existing,
            vad_filter=args.vad_filter,
            keep_audio=args.keep_audio,
            tmp_dir=tmp_dir,
        )
        if status == "success":
            logger.info("✅ Processing completed!")
            sys.exit(0)
        elif status.startswith("skipped"):
            logger.info(f"⏭️  Skipped ({status})")
            sys.exit(0)
        else:
            logger.error("❌ Processing failed")
            sys.exit(1)

    elif input_path.is_dir():
        results = process_folder(
            input_path,
            whisper_model,
            recursive=not args.no_recursive,
            lang_codes=lang_codes,
            source_lang=args.language,
            extensions=args.extensions,
            skip_existing=args.skip_existing,
            vad_filter=args.vad_filter,
            keep_audio=args.keep_audio,
            tmp_dir=tmp_dir,
        )

        logger.info(f"\n{'='*50}")
        logger.info(f"Processing Summary:")
        logger.info(f"  Total:            {results['total']}")
        logger.info(f"  Success:          {results['success']}")
        logger.info(f"  Skipped (no spa): {results['skipped_no_spa']}")
        logger.info(f"  Skipped (exist):  {results['skipped_existing']}")
        logger.info(f"  Failed:           {results['failed']}")
        logger.info(f"{'='*50}")

        sys.exit(0 if results['failed'] == 0 else 1)

    else:
        logger.error(f"{input_path} is not a valid file or folder")
        sys.exit(1)

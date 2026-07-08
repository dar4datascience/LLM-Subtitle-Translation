#!/usr/bin/env python3
"""YouTube → Transcription → Q&A Pipeline.

Downloads a single YouTube video, transcribes it with faster-whisper,
and generates a markdown file combining the transcription with template
questions for manual IDE AI review.

Usage:
    python scripts/youtube_qa_pipeline.py <youtube_url> [options]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from pytubefix import YouTube
    from pytubefix.exceptions import BotDetection, MaxRetriesExceeded
except ImportError:
    print("Error: pytubefix is not installed. Run: pip install pytubefix")
    sys.exit(1)

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Error: faster-whisper is not installed. Run: pip install faster-whisper")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    """Remove characters that are problematic for filesystems."""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()


def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    td = timedelta(seconds=int(seconds))
    total = int(td.total_seconds())
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ---------------------------------------------------------------------------
# Stage 1 — Download
# ---------------------------------------------------------------------------

def download_video(url: str, output_dir: Path, max_retries: int = 3) -> Path | None:
    """Download a single YouTube video and merge audio+video with ffmpeg.

    Returns the path to the merged .mp4 file, or None on failure.
    Skips download if the merged file already exists.
    """
    print(f"\n{'='*60}")
    print("Stage 1: Downloading video")
    print(f"{'='*60}")
    print(f"URL: {url}")

    yt = YouTube(url, use_oauth=True, allow_oauth_cache=True)

    title = sanitize_filename(yt.title)
    # yt.length is in seconds
    duration_str = format_duration(yt.length)

    merged_path = output_dir / f"{title}.mp4"
    if merged_path.exists():
        print(f"Video already exists: {merged_path}")
        return merged_path

    output_dir.mkdir(parents=True, exist_ok=True)

    # Retry logic for HTTP 429
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Fetching streams (attempt {attempt}/{max_retries})...")

            # Use WEB client for better compatibility
            streams = yt.streams
            video_stream = streams.filter(
                adaptive=True, file_extension="mp4", type="video"
            ).order_by("resolution").last()

            audio_stream = streams.filter(
                adaptive=True, file_extension="mp4", type="audio"
            ).order_by("abr").last()

            if not video_stream or not audio_stream:
                print("Error: Could not find suitable adaptive streams.")
                return None

            print(f"Video: {video_stream.resolution} | Audio: {audio_stream.abr}")

            # Download to temporary files
            tmp_video = output_dir / f"{title}_video_tmp.mp4"
            tmp_audio = output_dir / f"{title}_audio_tmp.mp4"

            print("Downloading video stream...")
            video_stream.download(output_path=str(output_dir), filename=tmp_video.name)
            print("Downloading audio stream...")
            audio_stream.download(output_path=str(output_dir), filename=tmp_audio.name)

            # Merge with ffmpeg
            print("Merging video + audio with ffmpeg...")
            cmd = [
                "ffmpeg", "-y",
                "-i", str(tmp_video),
                "-i", str(tmp_audio),
                "-c", "copy",
                "-map", "0:v:0",
                "-map", "1:a:0",
                str(merged_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"ffmpeg error:\n{result.stderr}")
                return None

            # Clean up temp files
            tmp_video.unlink(missing_ok=True)
            tmp_audio.unlink(missing_ok=True)

            print(f"Downloaded: {merged_path}")
            print(f"Duration: {duration_str}")
            return merged_path

        except BotDetection:
            wait = 2 ** attempt
            print(f"Bot detection (HTTP 429) — waiting {wait}s before retry...")
            time.sleep(wait)
        except Exception as e:
            print(f"Download error: {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                return None

    print("Failed to download after max retries.")
    return None


# ---------------------------------------------------------------------------
# Stage 2 — Transcribe
# ---------------------------------------------------------------------------

def transcribe_video(
    video_path: Path,
    model_size: str = "medium",
    language: str = "en",
    device: str | None = None,
    use_fp16: bool = True,
) -> tuple[Path, str] | None:
    """Transcribe a video file using faster-whisper.

    Returns (srt_path, plain_text) or None on failure.
    Skips transcription if the SRT file already exists.
    """
    print(f"\n{'='*60}")
    print("Stage 2: Transcribing with faster-whisper")
    print(f"{'='*60}")

    srt_path = video_path.with_suffix(".srt")
    if srt_path.exists():
        print(f"SRT already exists: {srt_path}")
        text = _extract_text_from_srt(srt_path)
        return srt_path, text

    # Auto-detect device
    if device is None:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    compute_type = "float16" if (device == "cuda" and use_fp16) else "int8"
    print(f"Device: {device} | Compute type: {compute_type} | Model: {model_size}")

    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print("Transcribing...")
    segments, info = model.transcribe(
        str(video_path),
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    print(f"Detected language: {info.language} (prob: {info.language_probability:.2f})")

    # Get video duration for progress estimation
    try:
        ffprobe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(video_path),
        ]
        ffprobe_result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
        video_duration = float(json.loads(ffprobe_result.stdout)["format"]["duration"])
    except Exception:
        video_duration = 0.0

    # Write SRT and collect plain text
    srt_lines = []
    text_parts = []
    segment_count = 0
    last_progress_time = time.time()

    print(f"Video duration: {format_duration(video_duration)}" if video_duration else "Video duration: unknown")
    print("Transcribing segments (progress shown every 10 segments or 30s)...\n")

    for i, segment in enumerate(segments, start=1):
        start_ts = format_srt_timestamp(segment.start)
        end_ts = format_srt_timestamp(segment.end)
        srt_lines.append(f"{i}")
        srt_lines.append(f"{start_ts} --> {end_ts}")
        srt_lines.append(segment.text.strip())
        srt_lines.append("")  # blank line between entries
        text_parts.append(segment.text.strip())
        segment_count = i

        # Print progress every 10 segments or every 30 seconds
        now = time.time()
        if i % 10 == 0 or (now - last_progress_time) > 30:
            if video_duration > 0:
                pct = (segment.end / video_duration) * 100
                print(f"  [{format_duration(segment.end)} / {format_duration(video_duration)}] {pct:.1f}% — {i} segments transcribed")
            else:
                print(f"  {i} segments transcribed (last end: {format_duration(segment.end)})")
            last_progress_time = now

    print(f"\nTranscription complete: {segment_count} segments total")

    srt_content = "\n".join(srt_lines)
    srt_path.write_text(srt_content, encoding="utf-8")
    print(f"SRT written: {srt_path}")

    plain_text = " ".join(text_parts)
    return srt_path, plain_text


def _extract_text_from_srt(srt_path: Path) -> str:
    """Extract plain text from an existing SRT file (strips timestampss/indices)."""
    lines = srt_path.read_text(encoding="utf-8").splitlines()
    text_parts = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if "-->" in line:
            continue
        text_parts.append(line)
    return " ".join(text_parts)


# ---------------------------------------------------------------------------
# Stage 3 — Generate Q&A Markdown
# ---------------------------------------------------------------------------

def generate_qa_markdown(
    video_path: Path,
    video_url: str,
    video_title: str,
    duration_seconds: float,
    transcription_text: str,
    template_path: Path,
    output_dir: Path,
) -> Path | None:
    """Generate a markdown file combining transcription with template questions.

    Returns the path to the generated markdown file, or None on failure.
    """
    print(f"\n{'='*60}")
    print("Stage 3: Generating Q&A markdown")
    print(f"{'='*60}")

    if not template_path.exists():
        print(f"Error: Template file not found: {template_path}")
        return None

    template_content = template_path.read_text(encoding="utf-8")

    # Build the questions section from the template
    # The template contains "## Questions" header and "### Question N: ..." entries
    # We copy them verbatim and add answer placeholders
    questions_section = _build_questions_section(template_content)

    duration_str = format_duration(duration_seconds)
    date_str = datetime.now().strftime("%Y-%m-%d")

    markdown = f"""# Q&A: {video_title}

**Source:** {video_url}
**Duration:** {duration_str}
**Transcribed:** {date_str}

## Transcription

{transcription_text}

---

{questions_section}
"""

    safe_title = sanitize_filename(video_title)
    output_path = output_dir / f"{safe_title}_qa.md"
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Q&A markdown written: {output_path}")
    return output_path


def _build_questions_section(template_content: str) -> str:
    """Parse the template and build a questions section with answer placeholders."""
    lines = template_content.splitlines()
    result_lines = []
    in_questions = False

    for line in lines:
        stripped = line.strip()

        # Detect the "## Questions" header
        if stripped.startswith("## Questions"):
            in_questions = True
            result_lines.append(line)
            continue

        if not in_questions:
            continue

        # If we hit another ## header, stop
        if stripped.startswith("## ") and not stripped.startswith("## Questions"):
            break

        # When we see a "### Question" line, add it and an answer placeholder
        if stripped.startswith("### Question"):
            result_lines.append("")
            result_lines.append(line)
            result_lines.append("")
            result_lines.append("**Answer:**")
            result_lines.append("")
            result_lines.append("_(to be filled)_")
        else:
            result_lines.append(line)

    return "\n".join(result_lines)


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="YouTube → Transcription → Q&A Pipeline"
    )
    parser.add_argument("url", type=str, help="YouTube video URL")
    parser.add_argument(
        "-o", "--output-dir",
        type=str, default="downloads",
        help="Directory for downloads and outputs (default: downloads/)"
    )
    parser.add_argument(
        "-t", "--template",
        type=str, default="templates/qa_template.md",
        help="Path to Q&A template markdown (default: templates/qa_template.md)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str, default="medium",
        choices=["tiny", "base", "small", "medium", "large-v3", "large-v2", "large"],
        help="faster-whisper model size (default: medium)"
    )
    parser.add_argument(
        "-l", "--language",
        type=str, default="es",
        help="Source language code (default: es)"
    )
    parser.add_argument(
        "--device",
        type=str, choices=["cuda", "cpu"],
        help="Force cuda/cpu (auto-detect if not specified)"
    )
    parser.add_argument(
        "--no-fp16",
        action="store_true",
        help="Disable FP16 precision"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download step (use existing video file)"
    )
    parser.add_argument(
        "--skip-transcribe",
        action="store_true",
        help="Skip transcription step (use existing SRT file)"
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    template_path = Path(args.template).resolve()

    # Resolve project root (parent of scripts/ dir)
    project_root = Path(__file__).parent.parent.resolve()

    if not template_path.is_absolute():
        template_path = project_root / template_path
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Stage 1: Download ---
    video_path = None
    video_url = args.url
    video_title = ""
    duration_seconds = 0.0

    if args.skip_download:
        print("Skipping download — looking for existing video file...")
        # Try to find any .mp4 in output dir
        mp4_files = sorted(output_dir.glob("*.mp4"))
        if mp4_files:
            video_path = mp4_files[-1]
            video_title = video_path.stem
            print(f"Found: {video_path}")
        else:
            print(f"Error: No .mp4 files found in {output_dir}")
            sys.exit(1)
    else:
        result = download_video(video_url, output_dir)
        if not result:
            print("Error: Download failed.")
            sys.exit(1)
        video_path = result
        # Get metadata from YouTube
        try:
            yt = YouTube(video_url, use_oauth=True, allow_oauth_cache=True)
            video_title = yt.title
            duration_seconds = float(yt.length)
        except Exception:
            video_title = video_path.stem
            duration_seconds = 0.0

    # --- Stage 2: Transcribe ---
    transcription_text = ""

    if args.skip_transcribe:
        print("Skipping transcription — looking for existing SRT file...")
        srt_path = video_path.with_suffix(".srt")
        if srt_path.exists():
            transcription_text = _extract_text_from_srt(srt_path)
            print(f"Found: {srt_path}")
        else:
            print(f"Error: No SRT file found at {srt_path}")
            sys.exit(1)
    else:
        result = transcribe_video(
            video_path,
            model_size=args.model,
            language=args.language,
            device=args.device,
            use_fp16=not args.no_fp16,
        )
        if not result:
            print("Error: Transcription failed.")
            sys.exit(1)
        _, transcription_text = result

    # --- Stage 3: Generate Q&A Markdown ---
    qa_path = generate_qa_markdown(
        video_path=video_path,
        video_url=video_url,
        video_title=video_title,
        duration_seconds=duration_seconds,
        transcription_text=transcription_text,
        template_path=template_path,
        output_dir=output_dir,
    )

    if not qa_path:
        print("Error: Q&A markdown generation failed.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("Pipeline complete!")
    print(f"{'='*60}")
    print(f"Video:   {video_path}")
    print(f"SRT:     {video_path.with_suffix('.srt')}")
    print(f"Q&A MD:  {qa_path}")


if __name__ == "__main__":
    main()

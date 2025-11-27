#!/usr/bin/env python3
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import timedelta
import pytesseract
from PIL import Image

def run(cmd):
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

def extract_vobsub(mkv_path, out_dir):
    """
    Extracts .sub/.idx VobSub streams from an MKV file.
    Output: vobsub.idx + vobsub.sub
    """
    idx_path = out_dir / "vobsub.idx"
    sub_path = out_dir / "vobsub.sub"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(mkv_path),
        "-map", "0:s:0",
        "-c:s", "copy",
        str(idx_path)
    ]
    run(cmd)

    # The .sub file appears automatically next to .idx in ffmpeg
    if not sub_path.exists():
        raise RuntimeError("VobSub .sub file not created!")

    return idx_path, sub_path


def vobsub_to_png(idx_file, out_dir):
    """
    Converts VobSub (.sub/.idx) images into PNG frames using ffmpeg.
    """
    out_pattern = str(out_dir / "sub_%06d.png")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(idx_file),
        out_pattern
    ]
    run(cmd)


def detect_frame_timestamps(idx_file):
    """
    Parse the .idx and return (image_index, start_ms, end_ms)
    """
    timestamps = []
    with open(idx_file, "r", encoding="latin-1") as f:
        for line in f:
            if line.startswith("timestamp:"):
                parts = line.strip().split(",")
                ts = parts[0].split()[1]  # hh:mm:ss:ms
                hh, mm, ss, ms = ts.split(":")
                start = (int(hh) * 3600 + int(mm) * 60 + int(ss)) * 1000 + int(ms)

                # crude: assume each frame lasts until the next frame
                timestamps.append(start)

    # Create end timestamps
    result = []
    for i, start in enumerate(timestamps):
        if i < len(timestamps) - 1:
            end = timestamps[i+1] - 1
        else:
            end = start + 2000  # assume 2s for last
        result.append((i+1, start, end))

    return result


def ms_to_srt_time(ms):
    td = timedelta(milliseconds=ms)
    return str(td)[:-3].replace(".", ",")


def ocr_pngs_to_srt(frames_dir, timestamps, out_srt):
    """
    OCR png files and write SRT.
    """
    with open(out_srt, "w", encoding="utf-8") as srt:
        for idx, start, end in timestamps:
            frame_path = frames_dir / f"sub_{idx:06d}.png"
            if not frame_path.exists():
                continue

            text = pytesseract.image_to_string(Image.open(frame_path)).strip()

            if not text:
                continue

            srt.write(f"{idx}\n")
            srt.write(f"{ms_to_srt_time(start)} --> {ms_to_srt_time(end)}\n")
            srt.write(text + "\n\n")


def convert_mkv_vobsub_to_srt(mkv_path):
    mkv_path = Path(mkv_path)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        vobsub_dir = tmp / "vobsub"
        frames_dir = tmp / "frames"
        vobsub_dir.mkdir()
        frames_dir.mkdir()

        print("STEP 1 — Extracting VobSub (.sub/.idx)")
        idx, sub = extract_vobsub(mkv_path, vobsub_dir)

        print("STEP 2 — Converting VobSub → PNG")
        vobsub_to_png(idx, frames_dir)

        print("STEP 3 — Reading frame timestamps")
        timestamps = detect_frame_timestamps(idx)

        print("STEP 4 — Running OCR and producing SRT")
        out_srt = mkv_path.with_suffix(".srt")
        ocr_pngs_to_srt(frames_dir, timestamps, out_srt)

        print(f"\nDONE! Generated SRT at: {out_srt}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python llm_subtitle_translate.py <input.mkv>")
        sys.exit(1)

    convert_mkv_vobsub_to_srt(sys.argv[1])

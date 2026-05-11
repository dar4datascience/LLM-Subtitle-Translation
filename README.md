# LLM Subtitle Translation

Extract PGS subtitles from Blu-ray MKV files and translate EN→ES using NLLB-200.

## Setup

```bash
# Activate venv
source venv/bin/activate

# Install Python deps
pip install -r requirements.txt

# Install Tesseract OCR (system package)
# Ubuntu/Debian:
sudo apt install tesseract-ocr

# Download tessdata_best for better OCR
mkdir -p ~/tessdata_best
curl -L https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata -o ~/tessdata_best/eng.traineddata
```

## Usage

### 1. Extract Subtitles from MKV

```bash
python batch_pgstrip.py /path/to/folder/with/mkv/files
```

### 2. Translate SRT Files

```bash
python translate_srt_folder.py /path/to/folder/with/srt/files
```

Translates all `.srt` files to Spanish, outputs as `.es.srt`.

## Model

Uses **facebook/nllb-200-distilled-600M** (600MB)
- Better quality than MarianMT
- CPU-friendly for Ryzen 7 5825U
- Supports 200 languages

## Hardware Requirements

- **CPU**: 8+ cores recommended
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: ~2GB for model + deps

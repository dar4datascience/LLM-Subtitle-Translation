# LLM Subtitle Translation

Extract subtitles from video files and translate EN→ES using NLLB-200.

**Supports multiple subtitle formats:**
- **Text-based** (fast, direct copy): SRT, ASS, SSA, WebVTT
- **Image-based** (OCR required): PGS (Blu-ray), VobSub (DVD)

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

### Complete Pipeline (Recommended)

Use `pipeline.py` to extract and translate in one step:

```bash
# Single file
python pipeline.py /path/to/file.mkv

# Folder (recursive by default)
python pipeline.py /path/to/folder

# With track selection
python pipeline.py /path/to/file.mkv -a 0 -b 2 -y 0

# Only current folder, no subdirectories
python pipeline.py /path/to/folder --no-recursive

# Custom log file
python pipeline.py /path/to/folder --log-file my_process.log

# Preview files without processing (dry run)
python pipeline.py /path/to/folder --dry-run
```

**Features:**
- **Auto-detects** subtitle format (text vs image-based)
- **Interactive selection** when multiple subtitle tracks available
- Extracts subtitles from MKV → SRT (uses ffmpeg for text, pgsrip+OCR for images)
- Translates English → Spanish automatically
- **Auto-cleanup**: Deletes intermediate English SRT files, keeps only Spanish translations
- Logs all operations to timestamped log file in `logs/` directory
- Automatically deletes log file on successful completion
- Keeps log files only when errors occur (for debugging)
- Tracks success/failure for each file
- Progress bars for batch processing

**Options:**
- `-a, --audio`: Audio track index (for pgsrip)
- `-b, --subtitle`: Subtitle track index (auto-select this track)
- `-y, --video`: Video track index (for pgsrip)
- `--no-recursive`: Only process current folder
- `--no-interactive`: Disable interactive track selection (use first track or -b index)
- `--log-file`: Custom log file path (default: `logs/pipeline_YYYYMMDD_HHMMSS.log`)
- `--dry-run`: Preview which MKV files will be processed without actually processing them
- `--batch-size`: Subtitle blocks per batch (default: 50, lower = less memory)

---

### Individual Steps (Advanced)

#### 1. Extract Subtitles from MKV

```bash
# Single file (interactive track selection)
python batch_extract.py /path/to/file.mkv

# Folder (recursive by default)
python batch_extract.py /path/to/folder/with/mkv/files

# With track selection (auto-select subtitle track 2)
python batch_extract.py /path/to/file.mkv -s 2

# Non-interactive (use first track)
python batch_extract.py /path/to/folder --no-interactive

# Only current folder, no subdirectories
python batch_extract.py /path/to/folder --no-recursive
```

**Options:**
- `-a, --audio`: Audio track index (for pgsrip)
- `-s, --subtitle`: Subtitle track index (auto-select)
- `-y, --video`: Video track index (for pgsrip)
- `--no-recursive`: Only process current folder, skip subdirectories
- `--no-interactive`: Disable interactive track selection

#### 2. Translate SRT Files

```bash
# Single file
python translate_srt_folder.py /path/to/file.srt

# Folder (recursive by default)
python translate_srt_folder.py /path/to/folder/with/srt/files

# Only current folder, no subdirectories
python translate_srt_folder.py /path/to/folder --no-recursive
```

Translates English `.srt` files to Spanish, outputs as `.es.srt`.

**Options:**
- `--no-recursive`: Only process current folder, skip subdirectories

## Model

Uses **facebook/nllb-200-distilled-600M** (600MB)
- Better quality than MarianMT
- CPU-friendly for Ryzen 7 5825U
- Supports 200 languages

## Hardware Requirements

- **CPU**: 8+ cores recommended
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: ~2GB for model + deps

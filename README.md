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
- Extracts PGS subtitles from MKV → SRT
- Translates English → Spanish automatically
- **Auto-cleanup**: Deletes intermediate English SRT files, keeps only Spanish translations
- Logs all operations to timestamped log file in `logs/` directory
- Automatically deletes log file on successful completion
- Keeps log files only when errors occur (for debugging)
- Tracks success/failure for each file
- Progress bars for batch processing

**Options:**
- `-a, --audio`: Audio track index
- `-b, --subtitle`: Subtitle track index  
- `-y, --video`: Video track index
- `--no-recursive`: Only process current folder
- `--log-file`: Custom log file path (default: `logs/pipeline_YYYYMMDD_HHMMSS.log`)
- `--dry-run`: Preview which MKV files will be processed without actually processing them

---

### Individual Steps (Advanced)

#### 1. Extract Subtitles from MKV

```bash
# Single file
python batch_pgstrip.py /path/to/file.mkv

# Folder (recursive by default)
python batch_pgstrip.py /path/to/folder/with/mkv/files

# With track selection
python batch_pgstrip.py /path/to/file.mkv -a 0 -b 2 -y 0

# Only current folder, no subdirectories
python batch_pgstrip.py /path/to/folder --no-recursive

# Full options
python batch_pgstrip.py /path/to/folder -a 0 -b 2 -y 0 --no-recursive
```

**Options:**
- `-a, --audio`: Audio track index
- `-b, --subtitle`: Subtitle track index  
- `-y, --video`: Video track index
- `--no-recursive`: Only process current folder, skip subdirectories

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

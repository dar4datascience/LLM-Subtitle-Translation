# LLM Subtitle Translation

Video processing toolkit for subtitle extraction/translation and audio track management. Extract subtitles (text/image-based) with automatic language detection, translate using NLLB-200, and manage audio tracks for Jellyfin/media servers.

## Features

- **Subtitle Extraction**: Text-based (SRT, ASS, WebVTT) and image-based (PGS, VobSub) with OCR
- **Language Detection**: Auto-detect subtitle language using langdetect/langid
- **Translation**: English → Spanish using NLLB-200 (600M model)
- **Audio Management**: Extract, merge, and convert audio tracks
- **Batch Processing**: Process entire folders with progress tracking
- **Jellyfin Optimized**: Audio format recommendations for streaming servers

## Architecture

### Repository Structure

```
LLM-Subtitle-Translation/
├── src/                          # Core classes
│   ├── audio_manager.py          # Audio extraction/merging
│   ├── language_detector.py      # Subtitle language detection
│   ├── subtitle_extractor.py     # Subtitle extraction (text/image)
│   ├── translator.py             # NLLB-200 translation
│   └── video_processor.py        # High-level coordinator
├── scripts/                      # CLI entry points
│   ├── extract_audio.py          # Extract audio tracks
│   ├── merge_audio.py            # Merge audio into video
│   ├── extract_subtitles.py      # Extract + detect language
│   ├── batch_extract.py          # Batch subtitle extraction
│   ├── translate_srt_folder.py   # Batch translation
│   ├── transcribe_audio_by_lang.py  # Transcribe a specific audio track by language
│   └── pipeline.py               # Complete pipeline
├── requirements.txt
├── README.md
└── venv/
```

### Pipeline Diagrams

#### Subtitle Extraction & Translation Pipeline

```
┌─────────────┐
│  Video File │
│   (.mkv)    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│  Detect Subtitle Tracks         │
│  (ffprobe)                      │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Select Track (interactive)     │
└──────┬──────────────────────────┘
       │
       ├─── Text-based? ──────────┐
       │    (SRT/ASS/WebVTT)      │
       │                          ▼
       │                   ┌──────────────┐
       │                   │   ffmpeg     │
       │                   │   extract    │
       │                   └──────┬───────┘
       │                          │
       ├─── Image-based? ─────────┤
       │    (PGS/VobSub)          │
       │                          ▼
       │                   ┌──────────────┐
       │                   │   pgsrip     │
       │                   │   + OCR      │
       │                   └──────┬───────┘
       │                          │
       ▼                          ▼
┌─────────────────────────────────┐
│  Raw Subtitle (.srt)            │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Language Detection             │
│  (langdetect/langid)            │
│  - Analyze text content         │
│  - Check confidence (>70%)      │
│  - Tag with ISO 639-2 code      │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Tagged Subtitle                │
│  (video.eng.srt)                │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Translation (NLLB-200)         │
│  - Batch processing (50 blocks) │
│  - EN → ES                      │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Translated Subtitle            │
│  (video.es.srt)                 │
└─────────────────────────────────┘
```

#### Audio Extraction Pipeline

```
┌─────────────┐
│  Video File │
│   (.mkv)    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│  List Audio Tracks              │
│  (ffprobe)                      │
│  - Track index                  │
│  - Codec (AAC/MP3/FLAC/etc)     │
│  - Language                     │
│  - Bitrate/Channels             │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Select Track (interactive)     │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Extract Audio (ffmpeg)         │
│  - Copy codec (no re-encode)    │
│  - OR convert to AAC/MP3        │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Audio File                     │
│  (video_audio_track1.aac)       │
└─────────────────────────────────┘
```

#### Audio Merging Pipeline

```
┌─────────────┐      ┌─────────────┐
│  Video File │      │ Audio File  │
│   (.mkv)    │      │   (.aac)    │
└──────┬──────┘      └──────┬──────┘
       │                    │
       └────────┬───────────┘
                │
                ▼
┌─────────────────────────────────┐
│  Merge Strategy?                │
├─────────────────────────────────┤
│  1. Add (keep all tracks)       │
│  2. Replace (remove original)   │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Merge Audio (ffmpeg)           │
│  - Map video stream             │
│  - Map audio streams            │
│  - Copy codecs (no re-encode)   │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Output Video                   │
│  (video_merged.mkv)             │
│  - Multiple audio tracks        │
│  - Selectable in player         │
└─────────────────────────────────┘
```

## Quick Start

### Installation

```bash
# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install system dependencies
# Ubuntu/Debian:
sudo apt install tesseract-ocr ffmpeg

# Download Tesseract best models (for OCR)
mkdir -p ~/tessdata_best
curl -L https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata -o ~/tessdata_best/eng.traineddata
```

### Basic Usage

```bash
# Complete pipeline (extract + translate)
python scripts/pipeline.py /path/to/video.mkv

# Extract audio from video
python scripts/extract_audio.py /path/to/video.mkv

# Merge audio into video
python scripts/merge_audio.py video.mkv audio.aac -o output.mkv

# Extract subtitles with language detection
python scripts/extract_subtitles.py /path/to/video.mkv
```

## Usage Guide

### Complete Subtitle Pipeline

Use `pipeline.py` for full extraction and translation:

```bash
# Single file
python scripts/pipeline.py /path/to/file.mkv

# Folder (recursive by default)
python scripts/pipeline.py /path/to/folder

# With track selection
python scripts/pipeline.py /path/to/file.mkv -b 2

# Preview files (dry run)
python scripts/pipeline.py /path/to/folder --dry-run
```

**Options:**
- `-a, --audio`: Audio track index (for pgsrip)
- `-b, --subtitle`: Subtitle track index (auto-select)
- `-y, --video`: Video track index (for pgsrip)
- `--no-recursive`: Only process current folder
- `--no-interactive`: Disable interactive track selection
- `--batch-size`: Subtitle blocks per batch (default: 50)
- `--dry-run`: Preview files without processing

### Audio Extraction

Extract audio tracks from video files:

```bash
# Extract with interactive track selection
python scripts/extract_audio.py video.mkv

# Extract specific track
python scripts/extract_audio.py video.mkv -t 1

# Convert to specific format
python scripts/extract_audio.py video.mkv -f aac

# Batch extract from folder
python scripts/extract_audio.py /path/to/videos/ -f aac
```

**Options:**
- `-t, --track`: Audio track index to extract
- `-o, --output`: Output audio file path
- `-f, --format`: Convert to format (aac, mp3, flac, opus)
- `--no-recursive`: Only process current folder
- `--no-interactive`: Use first track or -t index

### Audio Merging

Merge audio tracks into video files:

```bash
# Add audio track (keep existing)
python scripts/merge_audio.py video.mkv audio.aac -o output.mkv

# Replace existing audio
python scripts/merge_audio.py video.mkv audio.aac -o output.mkv --replace

# Set audio language
python scripts/merge_audio.py video.mkv audio.aac -l spa

# List available audio tracks
python scripts/merge_audio.py video.mkv --select-audio
```

**Options:**
- `-o, --output`: Output video file path
- `--replace`: Replace existing audio tracks
- `-l, --language`: Language code for audio track (default: und)
- `--select-audio`: List tracks without merging

### Subtitle Extraction with Language Detection

Extract subtitles and automatically detect language:

```bash
# Extract with language detection
python scripts/extract_subtitles.py video.mkv
# Output: video.eng.srt (auto-detected)

# Use accurate detection (slower)
python scripts/extract_subtitles.py video.mkv --accurate

# Skip language detection
python scripts/extract_subtitles.py video.mkv --no-detect

# Batch process folder
python scripts/extract_subtitles.py /path/to/videos/
```

**Options:**
- `-s, --subtitle`: Subtitle track index
- `--no-detect`: Skip language detection
- `--accurate`: Use langid (slower, more accurate)
- `--no-recursive`: Only process current folder
- `--no-interactive`: Use first track or -s index

### Individual Tools

#### Extract Subtitles (Legacy)

```bash
python scripts/batch_extract.py /path/to/file.mkv
python scripts/batch_extract.py /path/to/folder -s 2
```

#### Translate SRT Files

```bash
python scripts/translate_srt_folder.py /path/to/file.srt
python scripts/translate_srt_folder.py /path/to/folder
```

### Transcribe Audio Track by Language

Bulk transcribe a specific audio track (selected by language tag) from MKV/MP4
files. For each video the script finds the matching audio track via ffprobe,
extracts it to a temporary 16 kHz mono WAV, transcribes with faster-whisper,
and writes a Jellyfin-compatible `<video>.spa.srt` next to the video. The
temporary WAV is deleted after transcription (unless `--keep-audio`). Videos
without a matching audio track are skipped and logged.

```bash
# Single file (transcribe the Spanish audio track)
python scripts/transcribe_audio_by_lang.py /path/to/video.mkv

# Bulk process a folder (recursive by default)
python scripts/transcribe_audio_by_lang.py /path/to/videos/

# Use a larger model for better accuracy
python scripts/transcribe_audio_by_lang.py /path/to/videos/ -m large

# Match a different set of language tags
python scripts/transcribe_audio_by_lang.py /path/to/videos/ --audio-language spa,es,sp

# Keep the extracted WAV files for re-transcription
python scripts/transcribe_audio_by_lang.py /path/to/videos/ --keep-audio

# Reprocess videos even if a .spa.srt already exists
python scripts/transcribe_audio_by_lang.py /path/to/videos/ --no-skip-existing
```

**Options:**
- `-m, --model`: Whisper model size (default: `medium` — better accuracy for Spanish)
- `-l, --language`: Source language code passed to Whisper (default: `es`)
- `--audio-language`: Comma-separated ffprobe language tags to match (default: `spa,es`)
- `--device`: `cuda` or `cpu` (auto-detect if not specified)
- `--compute-type`: `int8` (fastest CPU), `float32` (max accuracy), `float16` (GPU only)
- `--no-recursive`: Only process the specified folder, not subdirectories
- `--extensions`: Video extensions to process (default: `*.mkv`)
- `-s, --skip-existing`: Skip videos that already have a `.spa.srt` (default: True)
- `--no-skip-existing`: Reprocess videos even if subtitles exist
- `--no-vad`: Disable VAD filter (not recommended for long audio)
- `--keep-audio`: Keep the extracted WAV after transcription (default: delete)
- `--tmp-dir`: Directory for temporary WAV files (default: alongside each video)

## Technical Details

### Language Detection

#### Algorithms

**langdetect** (Default)
- Based on Nakatani Shuyo's implementation
- Uses character n-grams (1-3 chars)
- Supports 55 languages
- Fast: ~1ms per detection
- Accuracy: 95% on paragraphs, 80% on sentences
- Non-deterministic (uses randomization for speed)
- GitHub: https://github.com/Mimino666/langdetect

**langid** (Optional, via --accurate flag)
- Based on Lui & Baldwin (2012) research
- Uses byte n-grams with Naive Bayes classifier
- Supports 97 languages
- Slower: ~5-10ms per detection
- Accuracy: 97% on paragraphs, 85% on sentences
- Deterministic results
- GitHub: https://github.com/saffsd/langid.py

#### Implementation Strategy

1. Extract text from first 10 subtitle blocks (min 100 chars)
2. Run detection algorithm
3. Check confidence score
4. If confidence < 70%:
   - Fall back to video metadata (ffprobe)
   - If no metadata, use 'und' (undetermined)
5. Tag output file with ISO 639-2 code

#### Language Detection Flow

```
┌─────────────────────────────────┐
│  Subtitle File (.srt)           │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Extract Text Samples           │
│  - Skip timestamps/numbers      │
│  - Combine first 10 blocks      │
│  - Min 100 chars for accuracy   │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Language Detection             │
│  (langdetect or langid)         │
└──────┬──────────────────────────┘
       │
       ├─── Confidence > 70%? ─────┐
       │                           │
       │ YES                       │ NO
       ▼                           ▼
┌──────────────┐          ┌─────────────────┐
│ Use Detected │          │ Check Metadata  │
│ Language     │          │ (ffprobe)       │
└──────┬───────┘          └────────┬────────┘
       │                           │
       │                           ├─── Has lang tag? ───┐
       │                           │                     │
       │                           │ YES                 │ NO
       │                           ▼                     ▼
       │                  ┌─────────────┐      ┌──────────────┐
       │                  │ Use Metadata│      │ Use 'und'    │
       │                  └──────┬──────┘      │ (undetermined)│
       │                         │             └──────┬───────┘
       │                         │                    │
       └─────────────────────────┴────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Tag Subtitle File       │
                    │ (video.{lang}.srt)      │
                    └─────────────────────────┘
```

#### Supported Language Codes

Common codes: `eng` (English), `spa` (Spanish), `fra` (French), `deu` (German), `ita` (Italian), `por` (Portuguese), `rus` (Russian), `jpn` (Japanese), `kor` (Korean), `zho` (Chinese), `ara` (Arabic)

Full list: https://en.wikipedia.org/wiki/List_of_ISO_639-2_codes

### Audio Formats

#### Format Comparison for Jellyfin Playback

| Format | Pros | Cons | Use Case | Codec |
|--------|------|------|----------|-------|
| **AAC** | Best compatibility, good quality/size, native in MP4/MKV | Lossy compression | **Recommended** for streaming servers | `aac`, `libfdk_aac` |
| **MP3** | Universal compatibility, smaller files | Lower quality than AAC | Maximum device compatibility | `libmp3lame` |
| **FLAC** | Lossless (perfect quality), open source | Large files (2-3x AAC) | Archival, audiophile collections | `flac` |
| **Opus** | Best quality/size ratio, modern | Limited hardware support | Low bitrate streaming, VoIP | `libopus` |

#### Strategy for This Project

- **Extract:** Copy original audio codec (no re-encoding, preserves quality)
- **Merge:** Keep original format when possible
- **Convert only if needed:** AAC fallback for compatibility
- **User choice:** CLI flag for format preference

### Translation Model

**facebook/nllb-200-distilled-600M**
- 600MB model size
- Better quality than MarianMT
- CPU-friendly for Ryzen 7 5825U
- Supports 200 languages
- Batch processing to avoid OOM

## Hardware Requirements

- **CPU**: 8+ cores recommended
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: ~2GB for model + dependencies
- **GPU**: Optional (CPU-only works fine)

## API Reference

### Core Classes

#### `AudioManager`
- `list_audio_tracks(video_path)` - List all audio tracks
- `extract_audio(video_path, output_path, track_index, convert_to)` - Extract audio
- `merge_audio(video_path, audio_path, output_path, replace, audio_language)` - Merge audio
- `select_audio_track(tracks, auto_select)` - Interactive selection
- `find_track_by_language(video_path, lang_codes)` - Find first audio track matching a language tag

#### `LanguageDetector`
- `detect_subtitle_language(srt_path, video_path, track_index, use_accurate)` - Detect language
- `detect_from_text(text, use_accurate)` - Detect from text content
- `detect_from_metadata(video_path, track_index)` - Get from metadata
- `tag_subtitle_file(srt_path, lang_code)` - Rename with language tag

#### `SubtitleExtractor`
- `detect_tracks(video_path)` - Detect subtitle tracks
- `extract(video_path, subtitle_track_index, interactive)` - Extract subtitle
- `extract_text_based(video_path, track)` - Extract text subtitle
- `extract_image_based(video_path, track)` - Extract image subtitle with OCR

#### `Translator`
- `load_model()` - Load NLLB-200 model
- `translate_text(lines)` - Translate text lines
- `translate_srt(srt_path, output_path, batch_size)` - Translate SRT file

#### `VideoProcessor`
- `process_subtitles(video_path, ...)` - Complete subtitle pipeline
- `extract_audio_track(video_path, ...)` - Extract audio
- `merge_audio_track(video_path, audio_path, ...)` - Merge audio

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or PR.

## Acknowledgments

- **NLLB-200**: Meta AI's No Language Left Behind translation model
- **pgsrip**: PGS subtitle extraction with OCR
- **Tesseract**: OCR engine
- **langdetect**: Language detection library
- **FFmpeg**: Video/audio processing

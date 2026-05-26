# Pipeline Status

## Issue Found & Fixed

### **Root Cause**
The subtitle extraction was failing because `subtitle_extractor.py` was using invalid command-line flags for pgsrip:
- Used `-b` flag (doesn't exist in pgsrip)
- Used `-a` and `-y` flags incorrectly

### **Fix Applied**
- Removed invalid flags from `@/home/chonkydev/Documents/Github_Repos/Catalogo-Peliculas-Biblioteca-Vasconcelos/LLM-Subtitle-Translation/subtitle_extractor.py:154`
- Added `-v` (verbose) flag to see progress
- Removed `capture_output=True` to show real-time progress

## Current Status

**Running:** `pipeline.py` on "Crimes of the Future (2022).mkv"

**Progress:**
1. ✅ Translation model loaded
2. ✅ Subtitle track detected (hdmv_pgs_subtitle - image-based)
3. 🔄 pgsrip OCR extraction in progress ("Ripping subtitles")

**Expected Time:** 15-30+ minutes for full-length movie OCR

## What's Happening

pgsrip is performing OCR (Optical Character Recognition) on image-based PGS subtitles. This process:
- Extracts each subtitle frame as an image
- Runs OCR on each image to convert to text
- Generates an SRT file with timestamps

## Output Location

When complete, subtitle file will be created at:
```
/mnt/gojira/LeDuke/Crimes of the Future (2022)/Crimes of the Future (2022).en.srt
```

## Monitoring

Check progress with:
```bash
# Watch for output file
ls -lh "/mnt/gojira/LeDuke/Crimes of the Future (2022)/"*.srt

# Check process
ps aux | grep pgsrip

# View log
tail -f pipeline_run.log
```

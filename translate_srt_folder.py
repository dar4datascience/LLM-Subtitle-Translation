#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from tqdm import tqdm

# -------------------------------
# Step 0 — Load NLLB model
# -------------------------------
MODEL_NAME = "facebook/nllb-200-distilled-600M"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, src_lang="eng_Latn")
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

# NLLB language codes
SRC_LANG = "eng_Latn"  # English
TGT_LANG = "spa_Latn"  # Spanish

# -------------------------------
# Step 1 — Helper: Translate text
# -------------------------------
def translate_text(lines):
    """
    lines: list of strings
    returns: list of translated strings
    """
    tokenizer.src_lang = SRC_LANG
    batch = tokenizer(lines, return_tensors="pt", padding=True)
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(TGT_LANG)
    translated_tokens = model.generate(**batch, forced_bos_token_id=forced_bos_token_id)
    translated = [tokenizer.decode(t, skip_special_tokens=True) for t in translated_tokens]
    return translated

# -------------------------------
# Step 2 — Translate SRT file
# -------------------------------
def translate_srt_file(srt_path: Path):
    """
    Reads an SRT file, translates each subtitle text line,
    and writes a new file with '.es.srt' suffix.
    """
    # Remove .en from stem if present, then add .es.srt
    stem = srt_path.stem
    if stem.endswith('.en'):
        stem = stem[:-3]  # Remove last 3 chars (.en)
    output_path = srt_path.with_name(stem + ".es.srt")
    print(f"Translating {srt_path} → {output_path}")

    lines_to_translate = []
    blocks = []

    with open(srt_path, "r", encoding="utf-8") as f:
        current_block = []
        for line in f:
            line = line.rstrip("\n")
            if line.strip() == "":
                if current_block:
                    blocks.append(current_block)
                    current_block = []
            else:
                current_block.append(line)
        if current_block:
            blocks.append(current_block)

    # Extract only text lines for translation (ignore numbers & timestamps)
    for block in blocks:
        text_lines = []
        for l in block:
            if "-->" in l or l.isdigit():
                continue
            text_lines.append(l)
        lines_to_translate.append(" ".join(text_lines))

    # Translate all at once
    translated_lines = translate_text(lines_to_translate)

    # Reconstruct blocks with translated text
    with open(output_path, "w", encoding="utf-8") as f:
        for block, trans_text in zip(blocks, translated_lines):
            for l in block:
                if "-->" in l or l.isdigit():
                    f.write(l + "\n")
            # Write translated text
            f.write(trans_text + "\n\n")

# -------------------------------
# Step 3 — Process folder
# -------------------------------
def translate_srt_folder(folder_path: Path, recursive=True):
    """
    Process all SRT files in a folder.
    
    Args:
        folder_path: Path to folder
        recursive: If True, search subdirectories. If False, only current folder.
    """
    if recursive:
        srt_files = list(folder_path.rglob("*.srt"))
    else:
        srt_files = list(folder_path.glob("*.srt"))
    
    if not srt_files:
        print("No SRT files found in folder.")
        return

    print(f"Found {len(srt_files)} SRT files to translate.")

    for srt_file in tqdm(srt_files, desc="Translating"):
        translate_srt_file(srt_file)

# -------------------------------
# CLI
# -------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Translate SRT subtitle files from English to Spanish using NLLB-200"
    )
    parser.add_argument("path", type=str, help="SRT file or folder containing SRT files")
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only process SRT files in the specified folder, not subdirectories"
    )
    
    args = parser.parse_args()

    input_path = Path(args.path)
    
    if input_path.is_file():
        if input_path.suffix.lower() != ".srt":
            print(f"{input_path} is not an SRT file.")
            sys.exit(1)
        print(f"Translating single file: {input_path}")
        translate_srt_file(input_path)
        print("\n✅ Translation completed!")
    elif input_path.is_dir():
        translate_srt_folder(input_path, recursive=not args.no_recursive)
        print("\n✅ Translation completed!")
    else:
        print(f"{input_path} is not a valid file or folder.")
        sys.exit(1)

#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.translator import Translator

# -------------------------------
# Translate SRT file
# -------------------------------
def translate_srt_file(srt_path: Path, translator: Translator):
    """
    Translate SRT file using Translator class.
    """
    result = translator.translate_srt(srt_path)
    if result:
        print(f"✅ Translated: {result}")
    else:
        print(f"❌ Failed: {srt_path}")

# -------------------------------
# Process folder
# -------------------------------
def translate_srt_folder(folder_path: Path, translator: Translator, recursive=True):
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
        translate_srt_file(srt_file, translator)

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
    
    print("Loading translation model...")
    translator = Translator()
    translator.load_model()
    
    if input_path.is_file():
        if input_path.suffix.lower() != ".srt":
            print(f"{input_path} is not an SRT file.")
            sys.exit(1)
        print(f"Translating single file: {input_path}")
        translate_srt_file(input_path, translator)
        print("\n✅ Translation completed!")
    elif input_path.is_dir():
        translate_srt_folder(input_path, translator, recursive=not args.no_recursive)
        print("\n✅ Translation completed!")
    else:
        print(f"{input_path} is not a valid file or folder.")
        sys.exit(1)

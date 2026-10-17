"""
generate_alpha_masks.py

Scans the folder this script is run from for .png files and generates
a grayscale alpha mask for each one, based on that image's alpha channel.

Output naming: <original_name>_mask.png
- White = fully opaque
- Black = fully transparent
- Grey = partial transparency

Useful for building Translucent/Alpha Test materials in the CS2 Source 2
Material Editor, where the mask is often wired in as a separate greyscale
texture rather than relying on the color texture's embedded alpha channel.

Usage:
    1. Place this script in the same folder as your PNG textures.
    2. Run:  python generate_alpha_masks.py
    3. Masks will be written alongside the originals.

Images with no alpha channel (e.g. plain RGB/opaque textures) are skipped
and reported, since there's no transparency data to extract.
"""

from pathlib import Path
from PIL import Image

def generate_alpha_mask(png_path: Path) -> str:
    """
    Generates a single alpha mask for one PNG file.
    Returns a short status string describing what happened.
    """
    try:
        img = Image.open(png_path)
    except Exception as e:
        return f"skipped (couldn't open: {e})"

    if img.mode not in ("RGBA", "LA", "PA"):
        return "skipped (no alpha channel)"

    # Normalize to RGBA so we can reliably pull the alpha band
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    alpha_channel = img.split()[-1]  # the 'A' band, as an 'L' (grayscale) image

    out_path = png_path.with_name(f"{png_path.stem}_mask.png")
    alpha_channel.save(out_path)

    return f"mask written -> {out_path.name}"


def main():
    folder = Path(__file__).resolve().parent
    png_files = sorted(folder.glob("*.png"))

    # Don't re-process masks we already generated on a previous run
    png_files = [p for p in png_files if not p.stem.endswith("_mask")]

    if not png_files:
        print("No .png files found in this folder.")
        return

    print(f"Found {len(png_files)} PNG file(s) in {folder}\n")

    for png_path in png_files:
        result = generate_alpha_mask(png_path)
        print(f"{png_path.name}: {result}")


if __name__ == "__main__":
    main()
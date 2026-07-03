#!/usr/bin/env python3
"""Crop a sheet of card backs into individual rectangles.

Usage:
    python3 crop_sheet.py <input.png> <output_dir>
"""
import sys
from pathlib import Path

from PIL import Image

CARD_W = 744
CARD_H = 484


def main() -> None:
    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as img:
        sheet_w, sheet_h = img.size
        print(f"Sheet size: {sheet_w}x{sheet_h}")

        cols = sheet_w // CARD_W
        rows = sheet_h // CARD_H
        print(f"Cropping {cols}x{rows} = {cols * rows} cards at {CARD_W}x{CARD_H}")

        for row in range(rows):
            for col in range(cols):
                left = col * CARD_W
                top = row * CARD_H
                right = left + CARD_W
                bottom = top + CARD_H
                card = img.crop((left, top, right, bottom))
                name = f"card_r{row:02d}_c{col:02d}.png"
                card.save(output_dir / name)

    print(f"Saved cards to {output_dir}")


if __name__ == "__main__":
    main()

"""Vision-path probe: can the configured vision model actually read a drawing?

Generates a synthetic P&ID-style image with a KNOWN set of tags (drawn with
PIL — vessel, pump pair, relief valve, exchanger, instrument bubble, line
number), runs it through the real `read_drawing` path, and scores recall.

This validates the drawing-digitisation path end to end with a live model.
It is a *clean* synthetic drawing — a real scanned P&ID (noise, rotation,
dense linework) is a harder problem and remains untested. Costs 1 API call.

Run:  python eval/vision_probe.py            (needs GEMINI_API_KEY or Ollama)
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

GROUND_TRUTH = {
    "V-204", "PSV-110B", "P-101A", "P-101B", "E-217", "FT-350", '6"-CR-1501-A1',
}


def make_drawing(path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1400, 900), "white")
    d = ImageDraw.Draw(img)
    try:
        big = ImageFont.truetype("arial.ttf", 26)
        small = ImageFont.truetype("arial.ttf", 20)
    except OSError:
        big = small = ImageFont.load_default()

    d.rectangle([20, 20, 1380, 80], outline="black", width=2)
    d.text((40, 38), "CRUDE UNIT — P&ID DWG-1042  REV C", font=big, fill="black")
    # vessel V-204
    d.ellipse([120, 200, 260, 260], outline="black", width=3)
    d.rectangle([120, 230, 260, 520], outline="black", width=3)
    d.ellipse([120, 490, 260, 550], outline="black", width=3)
    d.text((150, 350), "V-204", font=big, fill="black")
    # pumps
    for cx, tag in ((520, "P-101A"), (780, "P-101B")):
        d.ellipse([cx - 55, 620, cx + 55, 730], outline="black", width=3)
        d.ellipse([cx - 4, 671, cx + 4, 679], fill="black")
        d.text((cx - 45, 745), tag, font=big, fill="black")
    # relief valve
    d.polygon([(190, 130), (170, 170), (210, 170)], outline="black", width=3)
    d.line([190, 170, 190, 200], fill="black", width=3)
    d.text((225, 135), "PSV-110B", font=big, fill="black")
    # exchanger
    d.ellipse([950, 260, 1090, 400], outline="black", width=3)
    d.line([950, 330, 1090, 330], fill="black", width=3)
    d.text((980, 415), "E-217", font=big, fill="black")
    # instrument bubble
    d.ellipse([700, 300, 780, 380], outline="black", width=2)
    d.text((715, 325), "FT-350", font=small, fill="black")
    # piping + line number
    d.line([260, 380, 950, 380], fill="black", width=3)
    d.line([190, 550, 190, 675], fill="black", width=3)
    d.line([190, 675, 465, 675], fill="black", width=3)
    d.text((420, 350), '6"-CR-1501-A1', font=small, fill="black")
    img.save(path)


def main() -> int:
    from brain.ingest.readers.drawing import read_drawing

    with tempfile.TemporaryDirectory() as td:
        img = Path(td) / "pid_probe.png"
        make_drawing(img)
        text = read_drawing(img, "pid-probe").text

    print("--- model read ---")
    print(text)
    read_values = set()
    for line in text.splitlines():
        m = re.match(r"\s*(?:EQUIPMENT_TAG|LINE_NUMBER|INSTRUMENT_TAG)\s*:\s*(.+)", line)
        if m:
            read_values.add(m.group(1).strip())

    found = GROUND_TRUTH & read_values
    missed = GROUND_TRUTH - read_values
    extra = read_values - GROUND_TRUTH
    print(f"\nrecall: {len(found)}/{len(GROUND_TRUTH)}"
          + (f"   missed: {sorted(missed)}" if missed else "")
          + (f"   extra (check for hallucination): {sorted(extra)}" if extra else ""))
    return 0 if not missed else 1


if __name__ == "__main__":
    raise SystemExit(main())

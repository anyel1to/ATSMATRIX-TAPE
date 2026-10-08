#!/usr/bin/env python3
"""Compose ATSMATRIX TAPE frames: C++ raster plus the Rust signal."""

import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DOCS = ROOT / "docs"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def read_ppm(path: Path) -> Image.Image:
    data = path.read_bytes()
    header, _, rest = data.partition(b"\n")
    assert header == b"P6"
    line, _, rest = rest.partition(b"\n")
    while line.startswith(b"#"):
        line, _, rest = rest.partition(b"\n")
    w, h = map(int, line.split())
    _, _, rest = rest.partition(b"\n")
    return Image.frombytes("RGB", (w, h), rest[: w * h * 3])


def load_signals():
    with (BUILD / "signals.csv").open() as handle:
        return list(csv.DictReader(handle))


def load_tape():
    with (BUILD / "tape.csv").open() as handle:
        return list(csv.DictReader(handle))


def paint(base: Image.Image, sig: dict, tape_row: dict, equity: list[float], prints: list[dict]) -> Image.Image:
    im = base.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    title = ImageFont.truetype(FONTB, 22)
    body = ImageFont.truetype(FONT, 15)
    mono = ImageFont.truetype(MONO, 14)
    small = ImageFont.truetype(FONT, 13)

    draw.rectangle((0, 0, im.width, 44), fill=(12, 16, 22, 230))
    draw.text((28, 10), "ATSMATRIX  TAPE", font=title, fill=(236, 240, 246, 255))
    last = float(tape_row["last"])
    side = int(float(tape_row["side"]))
    last_col = (125, 214, 176, 255) if side >= 0 else (255, 138, 150, 255)
    draw.text((280, 14), f"{last:0.2f}", font=title, fill=last_col)
    draw.text((860, 14), f"tick {int(sig['i']):03d}", font=mono, fill=(168, 178, 192, 255))

    draw.text((980, 52), "BOOK", font=small, fill=(140, 150, 164, 255))
    ask = float(tape_row["ask"])
    bid = float(tape_row["bid"])
    for k in range(5):
        draw.text((1148, 66 + (4 - k) * 22), f"{ask + 0.01 * k:0.2f}", font=small, fill=(186, 194, 206, 255))
        draw.text((1148, 164 + k * 22), f"{bid - 0.01 * k:0.2f}", font=small, fill=(186, 194, 206, 255))
    draw.text((980, 338), "PRINTS", font=small, fill=(140, 150, 164, 255))
    for n, printed in enumerate(prints):
        side_n = int(float(printed["side"]))
        ink = (125, 214, 176, 255) if side_n > 0 else (255, 150, 160, 255)
        word = "buy" if side_n > 0 else "sell"
        draw.text((1140, 356 + n * 22), f"{word} {float(printed['qty']):0.0f}", font=small, fill=ink)

    panel = (28, 598, im.width - 28, 662)
    draw.rounded_rectangle(panel, radius=12, fill=(18, 22, 30, 235))
    regime = sig["regime"].upper()
    bias = int(float(sig["bias"]))
    conf = float(sig["confidence"])
    bias_word = "BID" if bias > 0 else "ASK" if bias < 0 else "FLAT"
    draw.text((44, 612), regime, font=title, fill=(236, 240, 246, 255))
    draw.text((168, 616), bias_word, font=body, fill=last_col)
    draw.text((250, 616), f"{conf * 100:0.0f}%", font=mono, fill=(198, 206, 216, 255))
    bar_x = 320
    draw.rounded_rectangle((bar_x, 622, bar_x + 180, 638), radius=4, fill=(36, 42, 54, 255))
    fill_w = int(180 * conf)
    bar_col = (90, 168, 255, 255) if bias >= 0 else (255, 120, 136, 255)
    if fill_w > 4:
        draw.rounded_rectangle((bar_x, 622, bar_x + fill_w, 638), radius=4, fill=bar_col)

    if equity:
        lo, hi = min(equity), max(equity)
        span = max(1e-6, hi - lo)
        pts = []
        for n, value in enumerate(equity):
            x = 560 + int(n / max(1, len(equity) - 1) * 580)
            y = 650 - int((value - lo) / span * 40)
            pts.append((x, y))
        if len(pts) > 1:
            draw.line(pts, fill=(214, 196, 140, 255), width=2)
        draw.text((560, 606), "PAPER", font=small, fill=(140, 150, 164, 255))

    return Image.alpha_composite(im, overlay).convert("RGB")


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    signals = {int(row["i"]): row for row in load_signals()}
    tape = {int(row["i"]): row for row in load_tape()}
    frames = sorted(BUILD.glob("frame_*.ppm"))
    composed = []
    equity_all = [float(signals[i]["pnl"]) for i in sorted(signals)]
    for path in frames:
        if path.name == "frame_last.ppm":
            tick = max(signals)
        else:
            tick = int(path.stem.split("_")[1])
        sig = signals.get(tick) or signals[min(signals, key=lambda i: abs(i - tick))]
        row = tape.get(tick) or tape[min(tape, key=lambda i: abs(i - tick))]
        upto = int(sig["i"])
        equity = equity_all[: upto + 1]
        prints = []
        for older in range(tick, -1, -1):
            older_row = tape.get(older)
            if older_row and int(float(older_row["side"])) != 0:
                prints.append(older_row)
            if len(prints) == 8:
                break
        image = paint(read_ppm(path), sig, row, equity, prints)
        composed.append((upto, image, sig["regime"]))
        image.save(BUILD / f"{path.stem}.png", optimize=True)

    picks = {}
    for tick, image, regime in composed:
        picks.setdefault(regime, (tick, image))
        if regime == "trend" and float(signals[tick]["score"]) > float(signals[picks["trend"][0]]["score"]):
            picks["trend"] = (tick, image)
    names = {"trend": "desk-trend.png", "revert": "desk-revert.png", "chop": "desk-chop.png"}
    for regime, filename in names.items():
        if regime in picks:
            picks[regime][1].save(DOCS / filename, optimize=True)
    if composed:
        composed[-1][1].save(DOCS / "desk-last.png", optimize=True)

    gif_frames = [image.resize((960, 544), Image.Resampling.LANCZOS) for _, image, _ in composed]
    if gif_frames:
        gif_frames[0].save(
            DOCS / "tape.gif",
            save_all=True,
            append_images=gif_frames[1:],
            duration=90,
            loop=0,
            optimize=True,
        )
    print(f"frames {len(composed)} docs {DOCS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

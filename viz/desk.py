#!/usr/bin/env python3
"""Compose ATSMATRIX TAPE frames: C++ raster, Rust signal, agent radar."""

import csv
import math
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


def paint(base: Image.Image, sig: dict, tape_row: dict, equity: list[float], prints: list[dict], scale: tuple[float, float]) -> Image.Image:
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
    lo, hi = scale
    tiny = ImageFont.truetype(MONO, 12)

    def price_y(price: float) -> int:
        return 500 - int((price - lo) / (hi - lo) * 400)

    for price in (hi, (hi + lo) / 2, lo):
        draw.text((8, price_y(price) - 8), f"{price:0.2f}", font=tiny, fill=(140, 150, 164, 255))
    draw.text((78, 556), "VOL", font=tiny, fill=(140, 150, 164, 255))

    draw.text((980, 52), "BOOK", font=small, fill=(140, 150, 164, 255))
    ask = float(tape_row["ask"])
    bid = float(tape_row["bid"])
    for k in range(5):
        draw.text((1148, 66 + (4 - k) * 22), f"{ask + 0.01 * k:0.2f}", font=small, fill=(186, 194, 206, 255))
        draw.text((1148, 164 + k * 22), f"{bid - 0.01 * k:0.2f}", font=small, fill=(186, 194, 206, 255))
    draw.text((980, 286), "RADAR", font=small, fill=(140, 150, 164, 255))
    draw_radar(draw, sig, tape_row)
    draw.text((980, 444), "PRINTS", font=small, fill=(140, 150, 164, 255))
    for n, printed in enumerate(prints[:4]):
        side_n = int(float(printed["side"]))
        ink = (125, 214, 176, 255) if side_n > 0 else (255, 150, 160, 255)
        word = "buy" if side_n > 0 else "sell"
        draw.text((1140, 464 + n * 22), f"{word} {float(printed['qty']):0.0f}", font=small, fill=ink)

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


def draw_radar(draw: ImageDraw.ImageDraw, sig: dict, tape_row: dict) -> None:
    cx, cy, radius = 1090, 360, 68
    ring = (90, 110, 140, 170)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=ring)
    draw.ellipse((cx - radius // 2, cy - radius // 2, cx + radius // 2, cy + radius // 2), outline=ring)
    draw.line((cx - radius, cy, cx + radius, cy), fill=ring)
    draw.line((cx, cy - radius, cx, cy + radius), fill=ring)
    angle = (int(sig["i"]) % 48) / 48 * math.tau
    draw.line(
        (cx, cy, cx + math.cos(angle) * radius, cy + math.sin(angle) * radius),
        fill=(90, 168, 255, 230),
        width=2,
    )
    scores = [
        float(sig["imbalance"]),
        max(-1.0, min(1.0, float(sig["mom"]) * 90)),
        max(-1.0, min(1.0, -float(sig["mom"]) * 90)),
        float(sig["confidence"]) - 0.5,
        int(float(tape_row["side"])) * 0.45,
    ]
    for index, score in enumerate(scores):
        theta = -math.pi / 2 + index * (math.tau / 5)
        dist = min(radius - 10, 18 + abs(score) * 46)
        x = cx + math.cos(theta) * dist
        y = cy + math.sin(theta) * dist
        color = (125, 214, 176, 255) if score >= 0 else (255, 138, 150, 255)
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color)


def banner() -> None:
    image = Image.new("RGB", (1600, 440), (12, 16, 22))
    draw = ImageDraw.Draw(image)
    small = ImageFont.truetype(FONT, 22)
    big = ImageFont.truetype(FONTB, 92)
    body = ImageFont.truetype(FONT, 26)
    draw.text((88, 118), "ATSMATRIX", font=small, fill=(140, 150, 164))
    draw.text((84, 156), "TAPE", font=big, fill=(236, 240, 246))
    draw.text((88, 278), "Paper agents. Simulated book. No brokerage.", font=body, fill=(186, 194, 206))
    draw.text((88, 324), "instagram.com/atsmatrix", font=body, fill=(90, 168, 255))
    cx, cy, radius = 1280, 220, 120
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(80, 100, 130))
    draw.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), outline=(80, 100, 130))
    draw.line((cx - radius, cy, cx + radius, cy), fill=(80, 100, 130))
    draw.line((cx, cy - radius, cx, cy + radius), fill=(80, 100, 130))
    draw.line((cx, cy, cx + 90, cy - 70), fill=(90, 168, 255), width=3)
    for index, color in enumerate(((125, 214, 176), (125, 214, 176), (255, 138, 150), (125, 214, 176), (255, 138, 150))):
        theta = -math.pi / 2 + index * (math.tau / 5)
        dist = 40 + (index % 3) * 28
        x = cx + math.cos(theta) * dist
        y = cy + math.sin(theta) * dist
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=color)
    image.save(DOCS / "banner.png", optimize=True)


def card(headline: str, sub: str) -> Image.Image:
    image = Image.new("RGB", (1200, 680), (12, 16, 22))
    draw = ImageDraw.Draw(image)
    small = ImageFont.truetype(FONT, 16)
    big = ImageFont.truetype(FONTB, 64)
    body = ImageFont.truetype(FONT, 22)
    draw.text((72, 230), "ATSMATRIX", font=small, fill=(140, 150, 164, 255))
    draw.text((72, 268), headline, font=big, fill=(236, 240, 246, 255))
    draw.text((72, 360), sub, font=body, fill=(186, 194, 206, 255))
    return image


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
        mids = [float(tape[i]["mid"]) for i in range(upto + 1) if i in tape]
        lo, hi = min(mids), max(mids)
        pad = max(0.15, (hi - lo) * 0.18)
        image = paint(read_ppm(path), sig, row, equity, prints, (lo - pad, hi + pad))
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

    seq = BUILD / "seq"
    seq.mkdir(exist_ok=True)
    for old in seq.glob("*.png"):
        old.unlink()
    index = 1
    intro = card("TAPE", "Simulated book. Paper signal.")
    for _ in range(48):
        intro.save(seq / f"{index:04d}.png")
        index += 1
    for _, image, _ in composed:
        image.save(seq / f"{index:04d}.png")
        index += 1
    outro = card("MIT", "github.com/anyel1to/ATSMATRIX-TAPE")
    for _ in range(48):
        outro.save(seq / f"{index:04d}.png")
        index += 1

    gif_frames = [image.resize((960, 544), Image.Resampling.LANCZOS) for _, image, _ in composed[::4]]
    if gif_frames:
        gif_frames[0].save(
            DOCS / "tape.gif",
            save_all=True,
            append_images=gif_frames[1:],
            duration=90,
            loop=0,
            optimize=True,
        )
    banner()
    print(f"frames {len(composed)} docs {DOCS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

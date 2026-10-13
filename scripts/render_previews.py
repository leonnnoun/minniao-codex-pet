"""Render labeled motion previews from the final v2 sprite atlas."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

try:
    import imageio_ffmpeg
except ImportError:  # GIF previews remain useful when the optional video encoder is unavailable.
    imageio_ffmpeg = None

ROOT = Path(__file__).resolve().parents[1]
ATLAS_PATH = ROOT / "assets" / "spritesheet.png"
OUTPUT = ROOT / "previews"
CELL_W, CELL_H = 192, 208
COLUMNS = 8
COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8]
STATES = [
    # Five open-eye frames and one short closed-eye frame make the blink read quickly.
    ("idle", [520, 400, 360, 80, 400, 520]),
    ("running-right", [120] * 7 + [220]),
    ("running-left", [120] * 7 + [220]),
    ("waving", [140, 140, 140, 280]),
    ("jumping", [140, 140, 140, 140, 280]),
    ("failed", [140] * 7 + [240]),
    ("waiting", [150] * 5 + [260]),
    ("running", [120] * 5 + [220]),
    ("review", [150] * 5 + [280]),
]
CHECK_A, CHECK_B = "#e8e6e2", "#ffffff"


def checkerboard(size: tuple[int, int], cell_size: int = 16) -> Image.Image:
    image = Image.new("RGB", size, CHECK_A)
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell_size):
        for x in range(0, size[0], cell_size):
            if (x // cell_size + y // cell_size) % 2:
                draw.rectangle((x, y, x + cell_size - 1, y + cell_size - 1), fill=CHECK_B)
    return image


def composite(frame: Image.Image, label: str | None = None) -> Image.Image:
    pad = 24 if label else 0
    result = checkerboard((CELL_W, CELL_H + pad))
    result.paste(frame, (0, pad), frame.getchannel("A"))
    if label:
        ImageDraw.Draw(result).text((6, 5), label, fill="#202020")
    return result


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with Image.open(ATLAS_PATH) as opened:
        if opened.size != (CELL_W * COLUMNS, CELL_H * len(COUNTS)):
            raise SystemExit(f"Expected a 1536x2288 atlas, got {opened.size}")
        atlas = opened.convert("RGBA")

    def cell(row: int, col: int) -> Image.Image:
        return atlas.crop((col * CELL_W, row * CELL_H, (col + 1) * CELL_W, (row + 1) * CELL_H))

    contact = Image.new("RGB", (COLUMNS * CELL_W, len(COUNTS) * (CELL_H + 24)), "#121212")
    draw = ImageDraw.Draw(contact)
    for row, count in enumerate(COUNTS):
        y0 = row * (CELL_H + 24)
        draw.text((8, y0 + 5), f"row {row}: {STATES[row][0] if row < len(STATES) else 'look'}", fill="white")
        for col in range(COLUMNS):
            x0 = col * CELL_W
            tile = checkerboard((CELL_W, CELL_H))
            frame = cell(row, col)
            tile.paste(frame, (0, 0), frame.getchannel("A"))
            contact.paste(tile, (x0, y0 + 24))
            border = "#37ad58" if col < count else "#d94b4b"
            draw.rectangle((x0, y0 + 24, x0 + CELL_W - 1, y0 + CELL_H + 23), outline=border, width=2)
            draw.text((x0 + 4, y0 + 26), str(col), fill="#202020")
    contact.save(OUTPUT / "contact-sheet.png")

    idle_strip = Image.new("RGB", (6 * CELL_W, CELL_H + 24), "#121212")
    strip_draw = ImageDraw.Draw(idle_strip)
    for col in range(6):
        x0 = col * CELL_W
        strip_draw.text((x0 + 6, 5), f"idle {col + 1}/6", fill="white")
        idle_strip.paste(composite(cell(0, col)), (x0, 24))
    idle_strip.save(OUTPUT / "idle-frames.png")

    directional = Image.new("RGB", (COLUMNS * CELL_W, 2 * (CELL_H + 24)), "#f3f3f3")
    draw = ImageDraw.Draw(directional)
    for index in range(16):
        row, col = 9 + index // COLUMNS, index % COLUMNS
        x0, y0 = col * CELL_W, (index // COLUMNS) * (CELL_H + 24)
        draw.rectangle((x0, y0, x0 + CELL_W - 1, y0 + 23), fill="#ffffff")
        draw.text((x0 + 5, y0 + 5), f"{index * 22.5:05g}°", fill="#202020")
        directional.paste(composite(cell(row, col)), (x0, y0 + 24))
    directional.save(OUTPUT / "directions.png")

    all_frames, all_durations = [], []
    state_frames = {}
    state_durations = {}
    for row, (name, durations) in enumerate(STATES):
        frames = [cell(row, col) for col in range(COUNTS[row])]
        frames[0].save(
            OUTPUT / f"{name}.gif",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            disposal=2,
            optimize=False,
        )
        state_frames[name] = frames
        state_durations[name] = durations
        for col, frame in enumerate(frames):
            all_frames.append(composite(frame, f"{name}: {col + 1}/{len(frames)}"))
        all_durations.extend(durations)

    all_frames[0].save(
        OUTPUT / "all-states.gif",
        save_all=True,
        append_images=all_frames[1:],
        duration=all_durations,
        loop=0,
        disposal=2,
    )
    if imageio_ffmpeg is None:
        print("imageio-ffmpeg is not installed; skipped all-states.mp4")
    else:
        writer = imageio_ffmpeg.write_frames(
            str(OUTPUT / "all-states.mp4"),
            (CELL_W, CELL_H + 24),
            fps=20,
            codec="libx264",
            pix_fmt_in="rgb24",
            pix_fmt_out="yuv420p",
            macro_block_size=1,
        )
        writer.send(None)
        try:
            for frame, duration in zip(all_frames, all_durations):
                pixels = np.asarray(frame, dtype=np.uint8)
                for _ in range(max(1, round(duration / 50))):
                    writer.send(pixels)
        finally:
            writer.close()

    look_frames = [composite(cell(9 + index // COLUMNS, index % COLUMNS), f"look {index * 22.5:g}°") for index in range(16)]
    look_frames[0].save(
        OUTPUT / "look-loop.gif",
        save_all=True,
        append_images=look_frames[1:],
        duration=180,
        loop=0,
        disposal=2,
    )

    transition = [composite(frame) for frame in state_frames["idle"] + state_frames["jumping"] + state_frames["idle"]]
    transition_durations = state_durations["idle"] + state_durations["jumping"] + state_durations["idle"]
    transition[0].save(
        OUTPUT / "idle-jump-idle.gif",
        save_all=True,
        append_images=transition[1:],
        duration=transition_durations,
        loop=0,
        disposal=2,
    )

    proof = Image.new("RGB", (CELL_W * 4, CELL_H + 24), CHECK_A)
    for index, (row, col, label) in enumerate([(0, 0, "idle"), (3, 1, "waving"), (4, 2, "jump peak"), (8, 3, "review")]):
        proof.paste(composite(cell(row, col), label), (index * CELL_W, 0))
    proof.save(OUTPUT / "four-state-stills.png")
    print(f"Rendered previews from {ATLAS_PATH} into {OUTPUT}")


if __name__ == "__main__":
    main()


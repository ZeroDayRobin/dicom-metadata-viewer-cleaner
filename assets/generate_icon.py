"""Rebuild the DICOM Reader application icon using Pillow."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
SIZE = 1024


def draw_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Transparent corners let the icon sit naturally on light and dark desktops.
    draw.rounded_rectangle((48, 48, 976, 976), radius=214, fill="#102C46")

    # Scan rings and four image pixels stay recognizable at taskbar size.
    draw.ellipse((191, 191, 833, 833), outline="#49D5E7", width=66)
    draw.arc((295, 295, 729, 729), start=25, end=335, fill="#A7EFF4", width=43)
    for box, color in (
        ((418, 418, 493, 493), "#F4FFFF"),
        ((531, 418, 606, 493), "#A7EFF4"),
        ((418, 531, 493, 606), "#A7EFF4"),
        ((531, 531, 606, 606), "#F4FFFF"),
    ):
        draw.rounded_rectangle(box, radius=13, fill=color)
    return image


def main() -> None:
    image = draw_icon()
    image.resize((256, 256), Image.Resampling.LANCZOS).save(ROOT / "dicom-reader.png")
    image.save(
        ROOT / "dicom-reader.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()

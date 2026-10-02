"""DICOM and ZIP loading, independent of the graphical interface."""

from dataclasses import dataclass
from pathlib import Path
import zipfile

import pydicom
from pydicom.dataset import Dataset
from pydicom.errors import InvalidDicomError


MAX_ZIP_MEMBER_SIZE = 512 * 1024 * 1024


@dataclass(frozen=True)
class Entry:
    source: Path
    name: str
    member: str | None = None


def list_entries(path: str | Path) -> list[Entry]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if not zipfile.is_zipfile(path):
        return [Entry(path, path.name)]

    entries = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            with archive.open(info) as stream:
                header = stream.read(132)
            if header[128:132] == b"DICM" or info.filename.lower().endswith((".dcm", ".dicom")):
                entries.append(Entry(path, info.filename, info.filename))
    return entries


def read_entry(entry: Entry) -> Dataset:
    def read(source):
        try:
            return pydicom.dcmread(source)
        except InvalidDicomError:
            if hasattr(source, "seek"):
                source.seek(0)
            return pydicom.dcmread(source, force=True)

    if entry.member is None:
        return read(entry.source)
    with zipfile.ZipFile(entry.source) as archive:
        info = archive.getinfo(entry.member)
        if info.file_size > MAX_ZIP_MEMBER_SIZE:
            raise ValueError("ZIP-Eintrag ist größer als 512 MiB")
        with archive.open(info) as stream:
            return read(stream)


def _value_text(element) -> str:
    value = element.value
    if isinstance(value, bytes):
        return f"<{len(value):,} bytes>".replace(",", ".")
    if value is None:
        return ""
    return str(value)


def metadata_rows(dataset: Dataset) -> list[tuple[int, str, str, str, str]]:
    """Return all file meta and dataset elements in display order."""
    rows: list[tuple[int, str, str, str, str]] = []

    def visit(ds: Dataset, depth: int) -> None:
        for element in ds:
            tag = f"({element.tag.group:04X},{element.tag.element:04X})"
            if element.VR == "SQ":
                rows.append((depth, tag, "SQ", element.name, f"{len(element.value)} item(s)"))
                for index, item in enumerate(element.value, 1):
                    rows.append((depth + 1, "", "", f"Item {index}", ""))
                    visit(item, depth + 2)
            else:
                rows.append((depth, tag, element.VR, element.name, _value_text(element)))

    if dataset.file_meta:
        rows.append((0, "", "", "File Meta Information", ""))
        visit(dataset.file_meta, 1)
    rows.append((0, "", "", "Dataset", ""))
    visit(dataset, 1)
    return rows


def preview_image(dataset: Dataset):
    """Decode the first image frame to an 8-bit Pillow image."""
    import numpy as np
    from PIL import Image
    from pydicom.pixels import apply_modality_lut, apply_voi_lut

    if "PixelData" not in dataset:
        raise ValueError("Keine Bilddaten vorhanden")
    pixels = dataset.pixel_array
    if int(dataset.get("NumberOfFrames", 1)) > 1:
        pixels = pixels[0]
    if pixels.ndim == 3 and pixels.shape[-1] in (3, 4):
        if pixels.dtype != np.uint8:
            pixels = np.clip(pixels, 0, 255).astype(np.uint8)
        return Image.fromarray(pixels[..., :3], "RGB")

    pixels = apply_modality_lut(pixels, dataset)
    pixels = apply_voi_lut(pixels, dataset)
    pixels = np.asarray(pixels, dtype=np.float64)
    low, high = float(np.nanmin(pixels)), float(np.nanmax(pixels))
    if high <= low:
        pixels = np.zeros(pixels.shape, dtype=np.uint8)
    else:
        pixels = np.clip((pixels - low) * 255 / (high - low), 0, 255).astype(np.uint8)
    if dataset.get("PhotometricInterpretation") == "MONOCHROME1":
        pixels = 255 - pixels
    return Image.fromarray(pixels, "L")

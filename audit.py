"""Read-only privacy hints for cleaned DICOM output. No values leave this module."""

from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from pydicom.pixels import apply_modality_lut, apply_voi_lut, pixel_array
from pydicom.uid import MediaStorageDirectoryStorage

from reader import list_entries, read_entry


REVIEW_TAGS = {
    0x00080080: "Institution Name",
    0x00080081: "Institution Address",
    0x00081010: "Station Name",
    0x00081030: "Study Description",
    0x00081032: "Procedure Code Sequence",
    0x0008103E: "Series Description",
    0x00181000: "Device Serial Number",
    0x00181020: "Software Versions",
    0x00181030: "Protocol Name",
    0x00181250: "Receive Coil Name",
    0x00321064: "Requested Procedure Code Sequence",
    0x00400007: "Scheduled Procedure Step Description",
    0x00400008: "Scheduled Protocol Code Sequence",
    0x00400260: "Performed Protocol Code Sequence",
    0x0040A160: "Text Value",
}
MAX_FRAMES_PER_INSTANCE = 64
MIN_OCR_SIDE = 30


@dataclass
class AuditResult:
    instances: int = 0
    metadata_files: int = 0
    metadata_counts: Counter = field(default_factory=Counter)
    pixel_frames_total: int = 0
    pixel_frames_checked: int = 0
    pixel_frames_with_text: int = 0
    pixel_frames_unchecked: int = 0
    text_locations: list[tuple[int, int]] = field(default_factory=list)
    ocr_unavailable: bool = False


def _metadata_tags_to_review(ds) -> set[int]:
    found = set()

    def visit(dataset):
        for element in dataset:
            tag = int(element.tag)
            if tag in REVIEW_TAGS and element.value:
                if element.VR == "SQ" or str(element.value).strip().upper() not in {"ANONYMIZED", "UNKNOWN"}:
                    found.add(tag)
            if tag == 0x00280301 and str(element.value).upper() == "YES":
                found.add(tag)
            if element.VR == "SQ":
                for item in element.value:
                    visit(item)

    visit(ds)
    return found


def _frame_indices(total: int) -> list[int]:
    if total <= MAX_FRAMES_PER_INSTANCE:
        return list(range(total))
    return sorted({round(i * (total - 1) / (MAX_FRAMES_PER_INSTANCE - 1))
                   for i in range(MAX_FRAMES_PER_INSTANCE)})


def _ocr_image(ds, index: int) -> np.ndarray:
    frame = np.asarray(pixel_array(ds, index=index))
    if frame.ndim == 2:
        frame = apply_modality_lut(frame, ds)
        frame = apply_voi_lut(frame, ds)
    values = np.asarray(frame, dtype=np.float64)
    if not np.isfinite(values).any():
        raise ValueError("No finite pixel values")
    low, high = float(np.nanmin(values)), float(np.nanmax(values))
    if high <= low:
        result = np.zeros(values.shape, dtype=np.uint8)
    else:
        result = np.clip((values - low) * 255 / (high - low), 0, 255).astype(np.uint8)
    if frame.ndim == 2 and str(ds.get("PhotometricInterpretation", "")) == "MONOCHROME1":
        result = 255 - result
    return result


@lru_cache(maxsize=1)
def create_local_ocr():
    """Use only models bundled with the installed package; never download."""
    import rapidocr
    from rapidocr import RapidOCR

    model_dir = Path(rapidocr.__file__).resolve().parent / "models"
    paths = {
        "Det.model_path": model_dir / "PP-OCRv6_det_small.onnx",
        "Cls.model_path": model_dir / "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        "Rec.model_path": model_dir / "PP-OCRv6_rec_small.onnx",
    }
    if not all(path.is_file() for path in paths.values()):
        raise FileNotFoundError("Lokale OCR-Modelle fehlen")
    return RapidOCR(params={**{key: str(path) for key, path in paths.items()},
                            "Global.log_level": "warning"})


def audit_source(source, ocr_engine_factory=create_local_ocr, progress=None) -> AuditResult:
    """Inspect every instance; OCR at most 64 evenly spread frames per instance."""
    result = AuditResult()
    entries = list_entries(source)
    engine = None
    for entry in entries:
        ds = read_entry(entry)
        sop_class = ds.get("SOPClassUID") or ds.file_meta.get("MediaStorageSOPClassUID", "")
        if str(sop_class) == str(MediaStorageDirectoryStorage):
            continue
        result.instances += 1
        tags = _metadata_tags_to_review(ds)
        if tags:
            result.metadata_files += 1
            result.metadata_counts.update(tags)

        if "PixelData" not in ds:
            if progress:
                progress(result.instances, len(entries))
            continue
        try:
            total = max(1, int(ds.get("NumberOfFrames", 1)))
        except (TypeError, ValueError):
            total = 1
        result.pixel_frames_total += total
        indices = _frame_indices(total)
        result.pixel_frames_unchecked += total - len(indices)
        for index in indices:
            try:
                image = _ocr_image(ds, index)
                if min(image.shape[:2]) < MIN_OCR_SIDE:
                    result.pixel_frames_unchecked += 1
                    continue
            except Exception:
                result.pixel_frames_unchecked += 1
                continue
            if engine is None and not result.ocr_unavailable:
                try:
                    engine = ocr_engine_factory()
                except Exception:
                    result.ocr_unavailable = True
            if result.ocr_unavailable:
                result.pixel_frames_unchecked += 1
                continue
            try:
                detected = engine(image)
                texts = getattr(detected, "txts", None) or ()
                scores = getattr(detected, "scores", None) or ()
                has_text = any(
                    len(str(value).strip()) >= 2 and float(score) >= 0.7
                    for value, score in zip(texts, scores)
                )
                result.pixel_frames_checked += 1
                if has_text:
                    result.pixel_frames_with_text += 1
                    result.text_locations.append((result.instances, index + 1))
            except Exception:
                result.pixel_frames_unchecked += 1
        if progress:
            progress(result.instances, len(entries))
    return result


def format_audit_report(audit: AuditResult) -> str:
    lines = [
        "Prüfbericht: Hinweise nach der Bereinigung (keine Freigabe zur Weitergabe)",
        f"Geprüfte DICOM-Instanzen: {audit.instances}",
        f"Instanzen mit auffälligen Metadatenfeldern: {audit.metadata_files}",
    ]
    if audit.metadata_counts:
        lines.append("Vorhandene Felder (Werte werden nicht protokolliert):")
        for tag, count in sorted(audit.metadata_counts.items()):
            label = REVIEW_TAGS.get(tag, "Burned In Annotation = YES")
            lines.append(f"- ({tag >> 16:04X},{tag & 0xFFFF:04X}) {label}: {count} Instanz(en)")
    else:
        lines.append("In der beobachteten Feldliste keine verbliebenen Werte gefunden.")
    lines.extend([
        "Bildpixel-OCR (lokal; erkannten Text nicht protokolliert):",
        f"- Bildframes vorhanden: {audit.pixel_frames_total}",
        f"- OCR-geprüft: {audit.pixel_frames_checked}",
        f"- Frames mit erkanntem Text: {audit.pixel_frames_with_text}",
        f"- nicht geprüft: {audit.pixel_frames_unchecked}",
    ])
    if audit.ocr_unavailable:
        lines.append("OCR war nicht verfügbar; betroffene Bildframes wurden nicht geprüft.")
    for instance, frame in audit.text_locations[:100]:
        lines.append(f"- Texthinweis: Instanz {instance}, Frame {frame}")
    if len(audit.text_locations) > 100:
        lines.append(f"- Weitere Texthinweise: {len(audit.text_locations) - 100}")
    lines.append(
        "OCR kann Text übersehen oder harmlose Bildbeschriftungen melden. "
        "Jede Ausgabe vor Weitergabe visuell prüfen."
    )
    return "\n".join(lines) + "\n"

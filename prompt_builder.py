"""Build a local, copyable AI prompt from a restricted technical DICOM summary."""

from collections import Counter

from pydicom.uid import MediaStorageDirectoryStorage

from reader import read_entry


KNOWN_MODALITIES = frozenset({
    "AR", "AS", "AU", "BDUS", "BI", "BMD", "CR", "CT", "DG", "DX", "ECG",
    "EPS", "ES", "GM", "HC", "HD", "IO", "IVUS", "KER", "KO", "LEN", "LS",
    "MG", "MR", "NM", "OAM", "OCT", "OP", "OPM", "OPT", "OT", "PLAN",
    "PR", "PT", "PX", "REG", "RESP", "RF", "RG", "RTDOSE", "RTIMAGE",
    "RTPLAN", "RTSTRUCT", "SEG", "SM", "SR", "STAIN", "TEXTURE", "TG",
    "US", "VA", "XA", "XC",
})


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 0 < number <= 100000 else None


def build_analysis_prompt(entries) -> str:
    if not entries:
        raise ValueError("Bitte zuerst DICOM-Dateien öffnen")
    modalities = Counter()
    dimensions = Counter()
    instances = 0
    frames = 0
    with_pixels = 0
    for entry in entries:
        ds = read_entry(entry)
        sop_class = ds.get("SOPClassUID") or ds.file_meta.get("MediaStorageSOPClassUID", "")
        if str(sop_class) == str(MediaStorageDirectoryStorage):
            continue
        instances += 1
        modality = str(ds.get("Modality", "")).upper()
        modalities[modality if modality in KNOWN_MODALITIES else "unbekannt"] += 1
        rows = _positive_int(ds.get("Rows"))
        columns = _positive_int(ds.get("Columns"))
        if rows and columns:
            dimensions[(rows, columns)] += 1
        frame_count = _positive_int(ds.get("NumberOfFrames")) or 1
        frames += frame_count
        if "PixelData" in ds:
            with_pixels += 1
    if not instances:
        raise ValueError("Keine analysierbaren DICOM-Instanzen gefunden")
    modality_lines = "\n".join(f"- {name}: {count}" for name, count in sorted(modalities.items()))
    dimension_lines = "\n".join(
        f"- {rows} × {columns}: {count} Datei(en)"
        for (rows, columns), count in sorted(dimensions.items())
    ) or "- keine Angaben"
    return (
        "Bitte analysiere die beigefügten DICOM-Dateien fachlich vorsichtig. "
        "Beschreibe Modalitäten, Bildserien, technische Bildqualität und erkennbare Auffälligkeiten "
        "nur, soweit die tatsächlich beigefügten Bilder dies hergeben. Benenne Unsicherheiten "
        "und Grenzen; stelle keine definitive Diagnose. Falls keine Dateien angehängt sind, "
        "werte ausschließlich die folgende technische Zusammenfassung aus und erfinde keine Bildbefunde.\n\n"
        f"Technische Zusammenfassung: {instances} DICOM-Instanz(en), {frames} Bildframe(s), "
        f"{with_pixels} Instanz(en) mit Pixeldaten.\n"
        f"Modalitäten:\n{modality_lines}\n"
        f"Bildgrößen:\n{dimension_lines}\n\n"
        "Diese Zusammenfassung wurde lokal erstellt. Patientendaten, Dateinamen, Freitextfelder, "
        "UIDs und Bildpixel sind darin nicht enthalten. Prüfe jede Datei vor einem eigenen Upload "
        "auf personenbezogene Angaben und sichtbare Merkmale."
    )

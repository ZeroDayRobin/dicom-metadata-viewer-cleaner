"""Local DICOM metadata cleaning. Pixel values are deliberately unchanged."""

from dataclasses import dataclass
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
import os
import re
import tempfile
import zipfile

import pydicom
from pydicom.dataset import FileMetaDataset
from pydicom.fileset import FileSet
from pydicom.uid import MediaStorageDirectoryStorage, PYDICOM_IMPLEMENTATION_UID, generate_uid
from dicomanonymizer import anonymize_dataset, initialize_actions_2024b
from dicomanonymizer.simpledicomanonymizer import dictionary as uid_mapping, get_UID

from reader import list_entries, read_entry
from audit import AuditResult, audit_source, format_audit_report


SCHEDULED_STEP_REPLACEMENTS = {
    0x00400001: "",           # Scheduled Station AE Title
    0x00400002: "00010101",   # Scheduled Procedure Step Start Date
    0x00400003: "000000.00",  # Scheduled Procedure Step Start Time
    0x00400004: "00010101",   # Scheduled Procedure Step End Date
    0x00400005: "000000.00",  # Scheduled Procedure Step End Time
    0x00400009: "ANONYMIZED", # Scheduled Procedure Step ID (Type 1)
    0x00400010: "",           # Scheduled Station Name
    0x00400011: "",           # Scheduled Procedure Step Location
}


def _clean_scheduled_step_fields(ds) -> None:
    """Apply explicit replacements at every nesting level."""
    def replace(_dataset, element):
        replacement = SCHEDULED_STEP_REPLACEMENTS.get(int(element.tag))
        if replacement is not None:
            element.value = replacement

    ds.walk(replace)


def _verify_scheduled_step_fields(ds) -> None:
    def verify(_dataset, element):
        replacement = SCHEDULED_STEP_REPLACEMENTS.get(int(element.tag))
        if replacement is not None and str(element.value) != replacement:
            raise ValueError(f"Nicht bereinigtes Scheduled-Procedure-Step-Feld: {element.tag}")

    ds.walk(verify)


@dataclass(frozen=True)
class CleanResult:
    count: int
    output: Path
    report: Path
    replaced_dicomdir: int = 0
    audit: AuditResult | None = None


def _patient_key(ds) -> tuple[str, str, str]:
    patient_id = str(ds.get("PatientID", "")).strip()
    issuer = str(ds.get("IssuerOfPatientID", "")).strip()
    name = str(ds.get("PatientName", "")).strip()
    if patient_id:
        return patient_id, issuer, ""
    return "", "", name or str(ds.get("StudyInstanceUID", ""))


def _sensitive_tokens(ds) -> set[tuple[str, bool]]:
    tokens = set()
    for keyword in ("PatientName", "PatientID", "PatientBirthDate"):
        value = str(ds.get(keyword, "")).strip()
        if value:
            tokens.add((value.casefold(), keyword == "PatientName" or len(value) >= 5))
            if keyword == "PatientName":
                tokens.update((part.casefold(), True) for part in re.split(r"[\^=\s]+", value) if len(part) >= 4)
    return tokens


def _text_values(ds):
    for element in ds:
        if element.VR == "SQ":
            for item in element.value:
                yield from _text_values(item)
        elif element.VR in {"AE", "CS", "LO", "LT", "PN", "SH", "ST", "UC", "UR", "UT", "DA", "DT", "TM"}:
            yield element.keyword, str(element.value).casefold()


def _linked_uids(ds, path=()):
    """Remember UID references that the base rules may blank inside sequences."""
    for element in ds:
        if element.VR == "SQ":
            for index, item in enumerate(element.value):
                yield from _linked_uids(item, path + ((element.tag, index),))
        elif element.VR == "UI" and (
            element.keyword.endswith("InstanceUID")
            or element.keyword.endswith("FrameOfReferenceUID")
        ) and element.value:
            yield path, element.tag, str(element.value)


def _restore_linked_uids(ds, references):
    for path, tag, original in references:
        item = ds
        for sequence_tag, index in path:
            if sequence_tag not in item or index >= len(item[sequence_tag].value):
                item = None
                break
            item = item[sequence_tag].value[index]
        if item is not None and tag in item:
            item[tag].value = get_UID(original)


def _clean_dataset(ds, mode: str, patient_numbers: dict[tuple[str, str, str], int]):
    old_class = str(ds.get("SOPClassUID") or ds.file_meta.get("MediaStorageSOPClassUID", ""))
    old_sop = str(ds.get("SOPInstanceUID") or ds.file_meta.get("MediaStorageSOPInstanceUID", ""))
    if old_class == str(MediaStorageDirectoryStorage):
        raise ValueError("DICOMDIR wird nicht bereinigt; Verweise auf Dateinamen müssten neu aufgebaut werden")
    if not old_class:
        raise ValueError("SOP-Klasse fehlt im Datensatz und Dateikopf")
    if ds.get("SOPClassUID") and ds.file_meta.get("MediaStorageSOPClassUID") and str(ds.SOPClassUID) != str(ds.file_meta.MediaStorageSOPClassUID):
        raise ValueError("SOP-Klasse in Datensatz und Dateikopf stimmt nicht überein")
    old_name = str(ds.get("PatientName", ""))
    old_id = str(ds.get("PatientID", ""))
    original_pixels = bytes(ds.PixelData) if "PixelData" in ds else None
    linked_uids = list(_linked_uids(ds))
    sensitive = _sensitive_tokens(ds)
    key = _patient_key(ds)
    if key not in patient_numbers:
        patient_numbers[key] = len(patient_numbers) + 1
    number = patient_numbers[key]
    transfer_syntax = ds.file_meta.get("TransferSyntaxUID") if ds.file_meta else None
    if not transfer_syntax:
        raise ValueError("Transfer Syntax fehlt; sichere Ausgabe nicht möglich")

    anonymize_dataset(ds, base_rules_gen=initialize_actions_2024b, delete_private_tags=True)
    _restore_linked_uids(ds, linked_uids)
    ds.SOPClassUID = old_class
    ds.SOPInstanceUID = get_UID(old_sop) if old_sop else generate_uid()

    # The profile rules also apply to person names inside nested sequences.
    def clear_names(dataset, element):
        if element.VR == "PN":
            element.value = ""

    ds.walk(clear_names)
    _clean_scheduled_step_fields(ds)
    if mode == "pseudonymize":
        ds.PatientName = f"Patient^{number:04d}"
        ds.PatientID = f"P{number:04d}"
    else:
        ds.PatientName = ""
        ds.PatientID = ""
    if (old_name and str(ds.PatientName) == old_name) or (old_id and str(ds.PatientID) == old_id):
        raise ValueError("Patientenname oder ID wurde nicht ersetzt")

    ds.PatientIdentityRemoved = "YES"
    ds.DeidentificationMethod = "2024b rules; scheduled step masked; pixels unchanged"

    if not ds.get("SOPClassUID") or not ds.get("SOPInstanceUID"):
        raise ValueError("SOP-Klasse oder Instanz-UID fehlt nach Bereinigung")
    if str(ds.SOPInstanceUID) == old_sop:
        raise ValueError("Instanz-UID wurde nicht ersetzt")
    if original_pixels is not None and bytes(ds.PixelData) != original_pixels:
        raise ValueError("Bilddaten wurden unerwartet verändert")

    meta = FileMetaDataset()
    meta.TransferSyntaxUID = transfer_syntax
    meta.MediaStorageSOPClassUID = ds.SOPClassUID
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    ds.file_meta = meta
    ds.preamble = b"\0" * 128

    for keyword, value in _text_values(ds):
        if keyword in {"PatientName", "PatientID"}:
            continue
        if any((token in value if partial else token == value) for token, partial in sensitive):
            raise ValueError("Ursprüngliche Patientenkennung in Metadaten verblieben")

    stream = BytesIO()
    ds.save_as(stream, enforce_file_format=True)
    data = stream.getvalue()
    checked = pydicom.dcmread(BytesIO(data))
    _verify_scheduled_step_fields(checked)
    if str(checked.file_meta.MediaStorageSOPInstanceUID) != str(checked.SOPInstanceUID):
        raise ValueError("Dateikopf und Datensatz enthalten unterschiedliche Instanz-UIDs")
    return data


def _is_dicomdir(ds) -> bool:
    sop_class = ds.get("SOPClassUID") or ds.file_meta.get("MediaStorageSOPClassUID", "")
    return str(sop_class) == str(MediaStorageDirectoryStorage)


def _prepare_fileset_instance(data: bytes, patient_number: int, index: int):
    """Supply anonymous required directory fields absent from sparse source files."""
    ds = pydicom.dcmread(BytesIO(data))
    if not ds.get("PatientID"):
        # A PATIENT directory record needs an ID, including in remove mode.
        ds.PatientID = f"P{patient_number:04d}"
    for keyword, value in (
        ("StudyDate", "19000101"), ("StudyTime", "000000"),
        ("StudyID", "1"), ("Modality", "OT"),
        ("SeriesNumber", "1"), ("InstanceNumber", str(index)),
    ):
        if not ds.get(keyword):
            setattr(ds, keyword, value)
    return ds


def _verify_fileset_zip(path: Path, count: int) -> None:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP-Ausgabe ist beschädigt")
        names = set(archive.namelist())
        if "DICOMDIR" not in names or len(names) != count + 1:
            raise ValueError("DICOMDIR oder DICOM-Dateien fehlen in der ZIP-Ausgabe")
        directory = pydicom.dcmread(BytesIO(archive.read("DICOMDIR")))
        references = [record for record in directory.DirectoryRecordSequence
                      if record.get("ReferencedFileID")]
        if len(references) != count:
            raise ValueError("DICOMDIR enthält nicht alle bereinigten DICOM-Dateien")
        referenced_names = set()
        for record in references:
            file_id = record.ReferencedFileID
            name = str(file_id) if isinstance(file_id, str) else "/".join(file_id)
            if name not in names:
                raise ValueError("DICOMDIR verweist auf eine fehlende Datei")
            ds = pydicom.dcmread(BytesIO(archive.read(name)), stop_before_pixels=True)
            _verify_scheduled_step_fields(ds)
            if str(record.ReferencedSOPInstanceUIDInFile) != str(ds.SOPInstanceUID):
                raise ValueError("DICOMDIR enthält eine falsche Instanz-UID")
            referenced_names.add(name)
        if referenced_names != names - {"DICOMDIR"}:
            raise ValueError("DICOMDIR-Verweise sind unvollständig")


def clean_source(source: str | Path, output: str | Path, mode: str,
                 progress=None, audit_progress=None) -> CleanResult:
    """Write a new cleaned DICOM file or ZIP; never overwrite existing files."""
    if mode not in {"pseudonymize", "remove"}:
        raise ValueError("Unbekannter Cleaner-Modus")
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output:
        raise ValueError("Originaldatei darf nicht überschrieben werden")
    if output.exists():
        raise FileExistsError(f"Ausgabedatei existiert bereits: {output}")
    report = output.with_name(output.name + ".report.txt")
    if report.exists():
        raise FileExistsError(f"Bericht existiert bereits: {report}")
    is_zip = zipfile.is_zipfile(source)
    if is_zip != (output.suffix.lower() == ".zip"):
        raise ValueError("ZIP-Eingaben brauchen eine ZIP-Ausgabe; DICOM-Eingaben eine DICOM-Ausgabe")
    entries = list_entries(source)
    if not entries:
        raise ValueError("Keine DICOM-Dateien gefunden")
    if not output.parent.is_dir():
        raise FileNotFoundError(output.parent)

    uid_mapping.clear()
    patient_numbers: dict[tuple[str, str, str], int] = {}
    cleaned_count = 0
    replaced_dicomdir = 0
    temp_name = None
    temp_report = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".tmp", delete=False) as temp:
            temp_name = Path(temp.name)
        if is_zip:
            with tempfile.TemporaryDirectory(dir=output.parent) as stage_name, ExitStack() as cleanup:
                fileset = FileSet()
                cleanup.callback(fileset._stage["t"].cleanup)
                for index, entry in enumerate(entries, 1):
                    dataset = read_entry(entry)
                    if _is_dicomdir(dataset):
                        replaced_dicomdir += 1
                    else:
                        patient_key = _patient_key(dataset)
                        data = _clean_dataset(dataset, mode, patient_numbers)
                        cleaned_count += 1
                        instance = _prepare_fileset_instance(
                            data, patient_numbers[patient_key], cleaned_count
                        )
                        try:
                            fileset.add(instance)
                        except (ValueError, KeyError, AttributeError) as exc:
                            raise ValueError(
                                f"DICOMDIR für Datei {index} kann nicht erstellt werden: {exc}"
                            ) from exc
                    if progress:
                        progress(index, len(entries))
                if cleaned_count == 0:
                    raise ValueError("ZIP enthält keine bereinigbaren DICOM-Instanzen (nur DICOMDIR)")
                fileset.write(stage_name)
                cleanup.callback(fileset._stage["t"].cleanup)
                stage = Path(stage_name)
                with zipfile.ZipFile(temp_name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for path in stage.rglob("*"):
                        if path.is_file():
                            archive.write(path, path.relative_to(stage).as_posix())
            _verify_fileset_zip(temp_name, cleaned_count)
        else:
            temp_name.write_bytes(_clean_dataset(read_entry(entries[0]), mode, patient_numbers))
            cleaned_count = 1
            if progress:
                progress(1, 1)
        audit = audit_source(temp_name, progress=audit_progress)
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".tmp", delete=False) as temp:
            temp_report = Path(temp.name)
        report_lines = [
            f"Modus: {mode}",
            f"DICOM-Dateien: {cleaned_count}",
            f"Ersetztes DICOMDIR: {replaced_dicomdir}",
            "DICOM-Metadaten nach Regeln von 2024b bereinigt.",
            "Verschachtelte Scheduled-Procedure-Step-Felder (Datum, Uhrzeit, AE, Station, Ort, ID) bereinigt.",
            "Pixeldaten wurden nicht bereinigt. Eingebrannte Namen und erkennbare Merkmale manuell prüfen.",
            "Originaldateien wurden nicht verändert. Keine Garantie vollständiger Anonymität.",
        ]
        if is_zip:
            report_lines.insert(3, "Ein neues DICOMDIR mit Verweisen auf die bereinigten Dateien wurde erstellt.")
            report_lines.insert(-1, "Für DICOMDIR nötige leere Kennfelder wurden mit neutralen Werten ergänzt.")
        temp_report.write_text(
            "\n".join(report_lines) + "\n\n" + format_audit_report(audit),
            encoding="utf-8",
        )
        if output.exists() or report.exists():
            raise FileExistsError("Ausgabe oder Bericht wurde zwischenzeitlich angelegt")
        os.replace(temp_report, report)
        temp_report = None
        try:
            os.replace(temp_name, output)
            temp_name = None
        except Exception:
            report.unlink(missing_ok=True)
            raise
        return CleanResult(cleaned_count, output, report, replaced_dicomdir, audit)
    finally:
        uid_mapping.clear()
        if temp_name is not None:
            temp_name.unlink(missing_ok=True)
        if temp_report is not None:
            temp_report.unlink(missing_ok=True)

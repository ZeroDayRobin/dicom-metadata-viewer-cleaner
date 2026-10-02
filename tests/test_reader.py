import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

from reader import list_entries, read_entry, metadata_rows, preview_image


def sample_dicom():
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.PatientName = "Test^Person"
    ds.PatientID = "123"
    item = Dataset()
    item.CodeMeaning = "Nested value"
    ds.ConceptCodeSequence = Sequence([item])
    ds.PixelData = b"\x01\x02"
    out = io.BytesIO()
    ds.save_as(out, enforce_file_format=True)
    return out.getvalue()


class ReaderTests(unittest.TestCase):
    def test_single_file_loads_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.dcm"
            path.write_bytes(sample_dicom())
            entries = list_entries(path)
            self.assertEqual([e.name for e in entries], ["image.dcm"])
            self.assertEqual(str(read_entry(entries[0]).PatientID), "123")

    def test_zip_lists_nested_dicom_without_extracting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "study.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("series/scan.dcm", sample_dicom())
                archive.writestr("notes.txt", "not dicom")
            entries = list_entries(path)
            self.assertEqual([e.name for e in entries], ["series/scan.dcm"])
            self.assertEqual(str(read_entry(entries[0]).PatientName), "Test^Person")

    def test_dicom_without_file_preamble_can_be_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.dcm"
            ds = Dataset()
            ds.PatientID = "legacy-42"
            ds.save_as(path, implicit_vr=True, little_endian=True)
            self.assertEqual(str(read_entry(list_entries(path)[0]).PatientID), "legacy-42")

    def test_rows_include_file_meta_sequence_and_binary_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.dcm"
            path.write_bytes(sample_dicom())
            rows = metadata_rows(read_entry(list_entries(path)[0]))
            flattened = "\n".join(str(row) for row in rows)
            self.assertIn("Transfer Syntax UID", flattened)
            self.assertIn("Nested value", flattened)
            self.assertIn("2 bytes", flattened)

    def test_preview_renders_monochrome_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.dcm"
            ds = FileDataset(None, {}, file_meta=FileMetaDataset(), preamble=b"\0" * 128)
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds.file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
            ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
            ds.Rows, ds.Columns = 2, 2
            ds.SamplesPerPixel = 1
            ds.PhotometricInterpretation = "MONOCHROME2"
            ds.BitsAllocated = ds.BitsStored = 8
            ds.HighBit = 7
            ds.PixelRepresentation = 0
            ds.PixelData = bytes([0, 64, 128, 255])
            ds.save_as(path, enforce_file_format=True)
            image = preview_image(read_entry(list_entries(path)[0]))
            self.assertEqual(image.size, (2, 2))
            self.assertEqual(image.getpixel((0, 0)), 0)
            self.assertEqual(image.getpixel((1, 1)), 255)


if __name__ == "__main__":
    unittest.main()

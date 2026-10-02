from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import pydicom
from PIL import Image, ImageDraw, ImageFont
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid

from audit import audit_source, format_audit_report
from cleaner import clean_source
from tests.test_cleaner import make_image


def make_text_image(path: Path):
    make_image(path, "123", generate_uid())
    ds = pydicom.dcmread(path)
    image = Image.new("L", (600, 180), 0)
    font = ImageFont.truetype("arial.ttf", 60)
    ImageDraw.Draw(image).text((20, 45), "PATIENT 12345", font=font, fill=255)
    ds.Rows, ds.Columns = image.height, image.width
    ds.PixelData = image.tobytes()
    ds.save_as(path, enforce_file_format=True)


class AuditTests(unittest.TestCase):
    def test_multiframe_ocr_counts_every_frame_when_within_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "multi.dcm"
            make_text_image(source)
            ds = pydicom.dcmread(source)
            ds.NumberOfFrames = 3
            ds.PixelData = bytes(ds.PixelData) * 3
            ds.save_as(source, enforce_file_format=True)

            class FakeOCR:
                def __call__(self, image):
                    return SimpleNamespace(txts=(), scores=())

            result = audit_source(source, ocr_engine_factory=FakeOCR, enable_ocr=True)
            self.assertEqual(result.pixel_frames_total, 3)
            self.assertEqual(result.pixel_frames_checked, 3)
            self.assertEqual(result.pixel_frames_unchecked, 0)

    def test_sampling_large_multiframe_file_reports_unchecked_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "multi.dcm"
            make_image(source, "123", generate_uid())
            ds = pydicom.dcmread(source)
            ds.Rows = ds.Columns = 30
            ds.NumberOfFrames = 65
            ds.PixelData = bytes([0] * 900) * 65
            ds.save_as(source, enforce_file_format=True)

            class FakeOCR:
                def __call__(self, image):
                    return SimpleNamespace(txts=(), scores=())

            result = audit_source(source, ocr_engine_factory=FakeOCR, enable_ocr=True)
            self.assertEqual(result.pixel_frames_total, 65)
            self.assertEqual(result.pixel_frames_checked, 64)
            self.assertEqual(result.pixel_frames_unchecked, 1)

    def test_nested_metadata_and_ocr_are_reported_without_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.dcm"
            make_text_image(source)
            ds = pydicom.dcmread(source)
            step = Dataset()
            step.ScheduledProcedureStepDescription = "MRT Fuß Secret"
            ds.ScheduledProcedureStepSequence = Sequence([step])
            ds.SoftwareVersions = "12.3.1 Secret"
            ds.save_as(source, enforce_file_format=True)

            class FakeOCR:
                def __call__(self, image):
                    return SimpleNamespace(txts=("Jane Doe",), scores=(0.99,))

            result = audit_source(source, ocr_engine_factory=FakeOCR, enable_ocr=True)
            report = format_audit_report(result)
            self.assertEqual(result.instances, 1)
            self.assertEqual(result.metadata_counts[0x00400007], 1)
            self.assertEqual(result.metadata_counts[0x00181020], 1)
            self.assertEqual(result.pixel_frames_checked, 1)
            self.assertEqual(result.pixel_frames_with_text, 1)
            self.assertIn("(0040,0007)", report)
            self.assertIn("(0018,1020)", report)
            for secret in ("MRT Fuß Secret", "12.3.1 Secret", "Jane Doe", "source.dcm"):
                self.assertNotIn(secret, report)

    def test_missing_ocr_is_explicitly_unchecked(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.dcm"
            make_text_image(source)

            def missing_engine():
                raise ImportError("OCR not installed")

            result = audit_source(source, ocr_engine_factory=missing_engine, enable_ocr=True)
            self.assertEqual(result.pixel_frames_checked, 0)
            self.assertEqual(result.pixel_frames_unchecked, 1)
            self.assertIn("nicht geprüft", format_audit_report(result))

    def test_bundled_local_ocr_detects_synthetic_pixel_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.dcm"
            make_text_image(source)
            result = audit_source(source, enable_ocr=True)
            self.assertEqual(result.pixel_frames_checked, 1)
            self.assertGreater(result.pixel_frames_with_text, 0)
            self.assertNotIn("PATIENT 12345", format_audit_report(result))

    def test_cleaner_writes_ocr_hint_for_new_copy_without_recognized_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "source.dcm", Path(tmp) / "clean.dcm"
            make_text_image(source)
            result = clean_source(source, output, "remove", enable_ocr=True)
            report = result.report.read_text(encoding="utf-8")
            self.assertEqual(result.audit.pixel_frames_checked, 1)
            self.assertGreater(result.audit.pixel_frames_with_text, 0)
            self.assertNotIn("PATIENT 12345", report)
            self.assertEqual(
                pydicom.dcmread(output).PixelData,
                pydicom.dcmread(source).PixelData,
            )

    def test_ocr_is_disabled_by_default_but_metadata_is_still_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "source.dcm", Path(tmp) / "clean.dcm"
            make_text_image(source)
            ds = pydicom.dcmread(source)
            ds.SoftwareVersions = "12.3.1"
            ds.save_as(source, enforce_file_format=True)

            engine_calls = []
            direct_audit = audit_source(
                source, ocr_engine_factory=lambda: engine_calls.append(True)
            )
            self.assertEqual(engine_calls, [])
            self.assertEqual(direct_audit.pixel_frames_unchecked, 1)

            result = clean_source(source, output, "remove")
            report = result.report.read_text(encoding="utf-8")
            self.assertEqual(result.audit.pixel_frames_total, 1)
            self.assertEqual(result.audit.pixel_frames_checked, 0)
            self.assertEqual(result.audit.pixel_frames_unchecked, 1)
            self.assertEqual(result.audit.metadata_counts[0x00181020], 1)
            self.assertIn("OCR deaktiviert", report)
            self.assertNotIn("PATIENT 12345", report)
            self.assertEqual(pydicom.dcmread(output).PixelData, ds.PixelData)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

from app import DicomApp


class AppIconTests(unittest.TestCase):
    def test_window_loads_project_icon(self):
        app = DicomApp()
        try:
            self.assertTrue((Path(__file__).resolve().parents[1] / "assets" / "dicom-reader.png").is_file())
            self.assertTrue((Path(__file__).resolve().parents[1] / "assets" / "dicom-reader.ico").is_file())
            self.assertIsNotNone(app.icon_image)
            self.assertEqual(app.icon_image.width(), 256)
            self.assertEqual(app.icon_image.height(), 256)
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import DicomApp
from audit import AuditResult


class InfoButtonTests(unittest.TestCase):
    def test_each_user_action_has_a_readable_info_button(self):
        app = DicomApp()
        try:
            expected = {
                "open": "DICOM-Datei oder ZIP",
                "pseudonymize": "Ersatzwerte",
                "remove": "Patientenname",
                "save": "Originaldatei",
                "ocr": "länger",
                "prompt": "keine Dateien",
                "search": "Metadaten",
            }
            self.assertEqual(set(app.info_buttons), set(expected))
            for key, phrase in expected.items():
                with self.subTest(key=key), patch("app.messagebox.showinfo") as showinfo:
                    app.info_buttons[key].invoke()
                    showinfo.assert_called_once()
                    self.assertIn(phrase, showinfo.call_args.args[1])
        finally:
            app.destroy()

    def test_ocr_checkbox_starts_disabled_and_warns_when_enabled(self):
        app = DicomApp()
        try:
            self.assertFalse(app.enable_ocr.get())
            with patch("app.messagebox.showwarning") as warning:
                app.ocr_checkbox.invoke()
                self.assertTrue(app.enable_ocr.get())
                warning.assert_called_once()
                self.assertIn("länger", warning.call_args.args[1])
                app.ocr_checkbox.invoke()
                self.assertFalse(app.enable_ocr.get())
                warning.assert_called_once()
        finally:
            app.destroy()

    def test_cleaner_receives_current_ocr_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.dcm"
            source.write_bytes(b"not a ZIP")
            app = DicomApp()
            try:
                app.entries = [SimpleNamespace(source=source)]
                for enabled in (False, True):
                    with self.subTest(enabled=enabled):
                        app.enable_ocr.set(enabled)
                        result = SimpleNamespace(
                            count=1, output=Path(tmp) / "clean.dcm",
                            report=Path(tmp) / "clean.dcm.report.txt",
                            replaced_dicomdir=0,
                            audit=AuditResult(ocr_enabled=enabled),
                        )
                        with patch("app.messagebox.askokcancel", return_value=True), \
                             patch("app.filedialog.asksaveasfilename", return_value=str(result.output)), \
                             patch("app.messagebox.showinfo"), \
                             patch("app.clean_source", return_value=result) as clean:
                            app.run_cleaner()
                        self.assertEqual(clean.call_args.kwargs["enable_ocr"], enabled)
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()

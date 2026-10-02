import unittest
from unittest.mock import patch

from app import DicomApp


class InfoButtonTests(unittest.TestCase):
    def test_each_user_action_has_a_readable_info_button(self):
        app = DicomApp()
        try:
            expected = {
                "open": "DICOM-Datei oder ZIP",
                "pseudonymize": "Ersatzwerte",
                "remove": "Patientenname",
                "save": "Originaldatei",
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


if __name__ == "__main__":
    unittest.main()

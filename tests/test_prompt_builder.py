import tempfile
import unittest
from pathlib import Path

import pydicom

from prompt_builder import build_analysis_prompt
from reader import list_entries
from tests.test_cleaner import make_image


class PromptBuilderTests(unittest.TestCase):
    def test_prompt_contains_only_allowlisted_technical_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "Secret Person.dcm"
            make_image(source, "123456", "1.2.3.4.5")
            ds = pydicom.dcmread(source)
            ds.Modality = "OT"
            ds.StudyDescription = "Secret hospital"
            ds.save_as(source, enforce_file_format=True)
            prompt = build_analysis_prompt(list_entries(source))
            self.assertIn("OT: 1", prompt)
            self.assertIn("1 × 1", prompt)
            for secret in ("Secret", "123456", "1.2.3.4.5", str(source)):
                self.assertNotIn(secret, prompt)
            self.assertIn("keine Dateien angehängt", prompt)


if __name__ == "__main__":
    unittest.main()

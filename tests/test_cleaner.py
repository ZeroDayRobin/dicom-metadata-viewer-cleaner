import tempfile
from io import BytesIO
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, MediaStorageDirectoryStorage, SecondaryCaptureImageStorage, generate_uid

from cleaner import clean_source
from app import DicomApp
from reader import Entry


def make_image(path, patient_id, study_uid):
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = generate_uid()
    ds.PatientName = "Secret^Person"
    ds.PatientID = patient_id
    ds.PatientBirthDate = "19700101"
    ds.StudyDescription = "Secret hospital"
    ds.Rows = ds.Columns = 1
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = b"\x7f\0"
    nested = Dataset()
    nested.PersonName = "Another^Secret"
    nested.ReferencedSOPInstanceUID = ds.SOPInstanceUID
    ds.ReferencedImageSequence = Sequence([nested])
    ds.add_new((0x0011, 0x0010), "LO", "SECRET_VENDOR")
    ds.add_new((0x0011, 0x1001), "LO", "secret private value")
    ds.save_as(path, enforce_file_format=True)


class CleanerTests(unittest.TestCase):
    def test_cleaner_report_includes_value_free_privacy_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source, output = folder / "source.dcm", folder / "clean.dcm"
            make_image(source, "123", generate_uid())
            ds = pydicom.dcmread(source)
            ds.SoftwareVersions = "12.3.1"
            ds.ReceiveCoilName = "SENSE_ANKLE_8_AC"
            ds.save_as(source, enforce_file_format=True)

            result = clean_source(source, output, "remove")
            report = result.report.read_text(encoding="utf-8")
            self.assertIn("Prüfbericht", report)
            self.assertIn("(0018,1020)", report)
            self.assertIn("(0018,1250)", report)
            self.assertNotIn("12.3.1", report)
            self.assertNotIn("SENSE_ANKLE_8_AC", report)
            self.assertIn("nicht geprüft: 1", report)
            self.assertEqual(result.audit.pixel_frames_unchecked, 1)

    def test_scheduled_step_fields_are_cleaned_inside_nested_sequences(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source, output = folder / "source.dcm", folder / "clean.dcm"
            make_image(source, "123", generate_uid())
            original = pydicom.dcmread(source)
            original_uid = str(original.SOPInstanceUID)

            def scheduled_step():
                step = Dataset()
                step.ScheduledStationAETitle = "WTTRRWWTTMRWP01"
                step.ScheduledProcedureStepStartDate = "20260928"
                step.ScheduledProcedureStepStartTime = "062000"
                step.ScheduledProcedureStepEndDate = "20260928"
                step.ScheduledProcedureStepEndTime = "064000"
                step.ScheduledProcedureStepID = "2.100496978"
                step.ScheduledStationName = "MR1 Witten"
                step.ScheduledProcedureStepLocation = "MR1 Witten"
                step.ScheduledProcedureStepDescription = "MRT Fuß"
                return step

            original.ScheduledProcedureStepSequence = Sequence([scheduled_step()])
            original.ScheduledProcedureStepSequence[0].ScheduledProcedureStepSequence = Sequence([scheduled_step()])
            original.save_as(source, enforce_file_format=True)

            clean_source(source, output, "remove")
            cleaned = pydicom.dcmread(output)
            steps = [
                cleaned.ScheduledProcedureStepSequence[0],
                cleaned.ScheduledProcedureStepSequence[0].ScheduledProcedureStepSequence[0],
            ]
            for step in steps:
                self.assertEqual(str(step.ScheduledStationAETitle), "")
                self.assertEqual(str(step.ScheduledProcedureStepStartDate), "00010101")
                self.assertEqual(str(step.ScheduledProcedureStepStartTime), "000000.00")
                self.assertEqual(str(step.ScheduledProcedureStepEndDate), "00010101")
                self.assertEqual(str(step.ScheduledProcedureStepEndTime), "000000.00")
                self.assertEqual(str(step.ScheduledProcedureStepID), "ANONYMIZED")
                self.assertEqual(str(step.ScheduledStationName), "")
                self.assertEqual(str(step.ScheduledProcedureStepLocation), "")
                self.assertEqual(str(step.ScheduledProcedureStepDescription), "MRT Fuß")
            self.assertEqual(str(cleaned.PatientName), "")
            self.assertEqual(str(cleaned.PatientID), "")
            self.assertNotEqual(str(cleaned.PatientBirthDate), "19700101")
            self.assertNotEqual(str(cleaned.SOPInstanceUID), original_uid)
            self.assertFalse(any(element.tag.is_private for element in cleaned))

    def test_scheduled_step_fields_stay_clean_in_fileset_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source, output = folder / "source.zip", folder / "clean.zip"
            with zipfile.ZipFile(source, "w") as archive:
                for index in (1, 2):
                    path = folder / f"image{index}.dcm"
                    make_image(path, "123", generate_uid())
                    ds = pydicom.dcmread(path)
                    step = Dataset()
                    step.ScheduledStationAETitle = "WTTRRWWTTMRWP01"
                    step.ScheduledProcedureStepStartDate = "20260928"
                    step.ScheduledProcedureStepStartTime = "062000"
                    step.ScheduledProcedureStepEndDate = "20260928"
                    step.ScheduledProcedureStepEndTime = "064000"
                    step.ScheduledProcedureStepID = "2.100496978"
                    step.ScheduledStationName = "MR1 Witten"
                    step.ScheduledProcedureStepLocation = "MR1 Witten"
                    ds.ScheduledProcedureStepSequence = Sequence([step])
                    ds.save_as(path, enforce_file_format=True)
                    archive.write(path, f"OLDNAME/IMAGE{index}")

            result = clean_source(source, output, "remove")
            self.assertEqual(result.count, 2)
            with zipfile.ZipFile(output) as archive:
                self.assertIn("DICOMDIR", archive.namelist())
                names = [name for name in archive.namelist() if name != "DICOMDIR"]
                self.assertEqual(len(names), 2)
                for name in names:
                    ds = pydicom.dcmread(BytesIO(archive.read(name)))
                    step = ds.ScheduledProcedureStepSequence[0]
                    self.assertEqual(str(step.ScheduledStationAETitle), "")
                    self.assertEqual(str(step.ScheduledProcedureStepStartDate), "00010101")
                    self.assertEqual(str(step.ScheduledProcedureStepStartTime), "000000.00")
                    self.assertEqual(str(step.ScheduledProcedureStepEndDate), "00010101")
                    self.assertEqual(str(step.ScheduledProcedureStepEndTime), "000000.00")
                    self.assertEqual(str(step.ScheduledProcedureStepID), "ANONYMIZED")
                    self.assertEqual(str(step.ScheduledStationName), "")
                    self.assertEqual(str(step.ScheduledProcedureStepLocation), "")

    def test_pseudonymize_keeps_image_and_consistent_study_uid(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            study_uid = generate_uid()
            with zipfile.ZipFile(folder / "input.zip", "w") as archive:
                for index in (1, 2):
                    path = folder / f"scan{index}.dcm"
                    make_image(path, "123", study_uid)
                    archive.write(path, f"Secret Person/scan{index}.dcm")
            source_bytes = (folder / "input.zip").read_bytes()
            result = clean_source(folder / "input.zip", folder / "clean.zip", "pseudonymize")
            self.assertEqual(result.count, 2)
            self.assertEqual((folder / "input.zip").read_bytes(), source_bytes)
            with zipfile.ZipFile(folder / "clean.zip") as archive:
                names = archive.namelist()
                self.assertIn("DICOMDIR", names)
                instance_names = [name for name in names if name != "DICOMDIR"]
                self.assertEqual(len(instance_names), 2)
                datasets = [pydicom.dcmread(BytesIO(archive.read(name))) for name in instance_names]
                directory = pydicom.dcmread(BytesIO(archive.read("DICOMDIR")))
                refs = [record for record in directory.DirectoryRecordSequence if record.get("ReferencedFileID")]
                self.assertEqual(len(refs), 2)
                self.assertEqual(
                    {"/".join(record.ReferencedFileID) for record in refs}, set(instance_names)
                )
            self.assertEqual(str(datasets[0].PatientID), str(datasets[1].PatientID))
            self.assertNotEqual(str(datasets[0].PatientID), "123")
            self.assertEqual(str(datasets[0].StudyInstanceUID), str(datasets[1].StudyInstanceUID))
            self.assertNotEqual(str(datasets[0].StudyInstanceUID), study_uid)
            self.assertEqual(bytes(datasets[0].PixelData), b"\x7f\0")
            self.assertEqual(str(datasets[0].file_meta.MediaStorageSOPInstanceUID), str(datasets[0].SOPInstanceUID))
            self.assertEqual(str(datasets[0].ReferencedImageSequence[0].ReferencedSOPInstanceUID), str(datasets[0].SOPInstanceUID))
            self.assertFalse(any(element.tag.is_private for element in datasets[0]))
            report = result.report.read_text(encoding="utf-8")
            self.assertNotIn("Secret", report)
            self.assertIn("Pixeldaten wurden nicht bereinigt", report)
            self.assertIn("Geprüfte DICOM-Instanzen: 2", report)

    def test_remove_mode_clears_patient_identity_and_nested_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.dcm"
            make_image(source, "123", generate_uid())
            clean_source(source, folder / "clean.dcm", "remove")
            ds = pydicom.dcmread(folder / "clean.dcm")
            self.assertEqual(str(ds.PatientName), "")
            self.assertEqual(str(ds.PatientID), "")
            self.assertEqual(str(ds.ReferencedImageSequence[0].PersonName), "")
            self.assertEqual(bytes(ds.PixelData), b"\x7f\0")
            self.assertNotIn("Secret", str(ds))

    def test_short_patient_id_does_not_false_positive_on_pseudonym(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.dcm"
            make_image(source, "0001", generate_uid())
            clean_source(source, folder / "clean.dcm", "pseudonymize")
            self.assertNotEqual(str(pydicom.dcmread(folder / "clean.dcm").PatientID), "0001")

    def test_refuses_to_overwrite_input_or_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.dcm"
            make_image(source, "123", generate_uid())
            with self.assertRaises(ValueError):
                clean_source(source, source, "remove")
            output = folder / "clean.dcm"
            output.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                clean_source(source, output, "remove")
            self.assertEqual(output.read_bytes(), b"existing")

    def test_gui_requires_warning_acknowledgement_before_output_selection(self):
        app = DicomApp()
        try:
            app.entries = [Entry(Path("example.dcm"), "example.dcm")]
            with patch("app.messagebox.askokcancel", return_value=False) as warning, \
                 patch("app.filedialog.asksaveasfilename") as save_dialog:
                app.run_cleaner()
            self.assertIn("Bild", warning.call_args.args[1])
            save_dialog.assert_not_called()
        finally:
            app.destroy()

    def test_gui_runs_remove_mode_after_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source, output = folder / "source.dcm", folder / "clean.dcm"
            make_image(source, "123", generate_uid())
            app = DicomApp()
            try:
                app.open_path(str(source))
                app.clean_mode.set("remove")
                with patch("app.messagebox.askokcancel", return_value=True), \
                     patch("app.filedialog.asksaveasfilename", return_value=str(output)), \
                     patch("app.messagebox.showinfo") as done:
                    app.run_cleaner()
                self.assertTrue(output.is_file())
                self.assertEqual(str(pydicom.dcmread(output).PatientID), "")
                done.assert_called_once()
                self.assertIn("Prüfbericht", done.call_args.args[1])
            finally:
                app.destroy()

    def test_dicomdir_is_rejected_because_file_references_cannot_be_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "DICOMDIR"
            make_image(source, "123", generate_uid())
            ds = pydicom.dcmread(source)
            ds.SOPClassUID = MediaStorageDirectoryStorage
            ds.file_meta.MediaStorageSOPClassUID = MediaStorageDirectoryStorage
            ds.save_as(source, enforce_file_format=True)
            output = folder / "clean.dcm"
            with self.assertRaises(ValueError):
                clean_source(source, output, "remove")
            self.assertFalse(output.exists())

    def test_cleaner_recovers_sop_identifiers_present_only_in_file_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "meta_only.dcm"
            make_image(source, "123", generate_uid())
            ds = pydicom.dcmread(source)
            old_instance = str(ds.file_meta.MediaStorageSOPInstanceUID)
            del ds.SOPClassUID
            del ds.SOPInstanceUID
            ds.save_as(source, enforce_file_format=True)
            output = folder / "clean.dcm"
            clean_source(source, output, "remove")
            cleaned = pydicom.dcmread(output)
            self.assertEqual(str(cleaned.SOPClassUID), str(SecondaryCaptureImageStorage))
            self.assertEqual(str(cleaned.SOPInstanceUID), str(cleaned.file_meta.MediaStorageSOPInstanceUID))
            self.assertNotEqual(str(cleaned.SOPInstanceUID), old_instance)

    def test_zip_with_dicomdir_replaces_stale_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            image = folder / "image.dcm"
            dicomdir = folder / "DICOMDIR"
            make_image(image, "123", generate_uid())
            make_image(dicomdir, "123", generate_uid())
            directory_ds = pydicom.dcmread(dicomdir)
            directory_ds.SOPClassUID = MediaStorageDirectoryStorage
            directory_ds.file_meta.MediaStorageSOPClassUID = MediaStorageDirectoryStorage
            directory_ds.save_as(dicomdir, enforce_file_format=True)
            source, output = folder / "input.zip", folder / "clean.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.write(dicomdir, "DICOMDIR")
                archive.write(image, "PATIENTNAME/IMAGE001")
            result = clean_source(source, output, "remove")
            self.assertEqual(result.count, 1)
            self.assertEqual(result.replaced_dicomdir, 1)
            with zipfile.ZipFile(output) as archive:
                self.assertIn("DICOMDIR", archive.namelist())
                image_names = [name for name in archive.namelist() if name != "DICOMDIR"]
                self.assertEqual(len(image_names), 1)
                cleaned = pydicom.dcmread(BytesIO(archive.read(image_names[0])))
                self.assertEqual(str(cleaned.PatientName), "")
                self.assertEqual(str(cleaned.PatientID), "P0001")
            self.assertIn("Ersetztes DICOMDIR: 1", result.report.read_text(encoding="utf-8"))

    def test_zip_with_only_dicomdir_does_not_publish_empty_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            dicomdir = folder / "DICOMDIR"
            make_image(dicomdir, "123", generate_uid())
            ds = pydicom.dcmread(dicomdir)
            ds.SOPClassUID = MediaStorageDirectoryStorage
            ds.file_meta.MediaStorageSOPClassUID = MediaStorageDirectoryStorage
            ds.save_as(dicomdir, enforce_file_format=True)
            source, output = folder / "input.zip", folder / "clean.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.write(dicomdir, "DICOMDIR")
            with self.assertRaises(ValueError):
                clean_source(source, output, "remove")
            self.assertFalse(output.exists())
            self.assertFalse((folder / "clean.zip.report.txt").exists())


if __name__ == "__main__":
    unittest.main()

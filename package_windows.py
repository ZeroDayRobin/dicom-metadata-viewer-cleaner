"""Package the PyInstaller directory with license notices into a portable ZIP."""

from importlib import metadata
from pathlib import Path
from shutil import copy2, copytree, rmtree
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
STAGE = DIST / "DicomMetadataViewerCleaner-Windows-x64"
ARCHIVE = DIST / (STAGE.name + ".zip")
EXECUTABLE = DIST / "DicomMetadataViewerCleaner" / "DicomMetadataViewerCleaner.exe"


def main():
    if not EXECUTABLE.is_file():
        raise FileNotFoundError("Build the application before packaging it")
    if STAGE.resolve().parent != DIST.resolve() or STAGE.is_symlink():
        raise RuntimeError("Unsafe staging directory")
    if STAGE.exists():
        rmtree(STAGE)
    copytree(EXECUTABLE.parent, STAGE)
    for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        copy2(ROOT / filename, STAGE / filename)
    (STAGE / "START-HERE.txt").write_text(
        "DICOM Metadata Viewer & Cleaner - Windows x64\n\n"
        "1. ZIP vollstaendig entpacken.\n"
        "2. DicomMetadataViewerCleaner.exe starten.\n"
        "3. DICOM oder ZIP in der Anwendung oeffnen.\n\n"
        "Python und Internet sind fuer die Nutzung nicht erforderlich. "
        "Dateien bleiben lokal.\n"
        "Vor einer Weitergabe bereinigter DICOM-Daten den Pruefbericht und "
        "sichtbare Bildinhalte selbst kontrollieren.\n"
        "Lizenztexte stehen im Ordner THIRD_PARTY_LICENSES.\n",
        encoding="utf-8",
    )

    licenses = STAGE / "THIRD_PARTY_LICENSES"
    licenses.mkdir()
    packages = []
    for distribution in sorted(metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = distribution.metadata["Name"]
        version = distribution.version
        package_dir = licenses / f"{name}-{version}"
        count = 0
        for file in distribution.files or ():
            relative = Path(str(file))
            if not any(word in relative.name.lower() for word in ("license", "notice", "copying")):
                continue
            source = Path(distribution.locate_file(file))
            if not source.is_file():
                continue
            target = package_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            copy2(source, target)
            count += 1
        packages.append(f"{name} {version}: {count} license/notice file(s)")
    for extra in (ROOT / "third_party").iterdir():
        if extra.is_file():
            copy2(extra, licenses / extra.name)
    python_license = Path(__import__("sys").base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        copy2(python_license, licenses / "Python-LICENSE.txt")
    (licenses / "PACKAGE_LIST.txt").write_text(
        "License files copied from the installed build environment. Some packages "
        "are included here even if they are not loaded at runtime.\n\n"
        + "\n".join(packages) + "\n",
        encoding="utf-8",
    )

    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED, compresslevel=6) as zip_file:
        for file in STAGE.rglob("*"):
            if file.is_file():
                zip_file.write(file, file.relative_to(DIST))
    print(ARCHIVE)


if __name__ == "__main__":
    main()

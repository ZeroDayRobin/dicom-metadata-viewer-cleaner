$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.14 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.14 is required to build this Windows package.' }
}

& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name DicomMetadataViewerCleaner --icon assets\dicom-reader.ico `
    --add-data 'assets\dicom-reader.png;assets' --collect-data rapidocr `
    --hidden-import dicomanonymizer.dicom_anonymization_databases.dicomfields_2024b app.py
if ($LASTEXITCODE -ne 0) { throw 'Windows build failed.' }

& .\.venv\Scripts\python.exe package_windows.py
if ($LASTEXITCODE -ne 0) { throw 'ZIP packaging failed.' }

Write-Host 'Portable Windows ZIP: dist\DicomMetadataViewerCleaner-Windows-x64.zip'

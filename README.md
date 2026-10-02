# DICOM Metadata Viewer & Cleaner

Offline DICOM and ZIP metadata viewer with a local cleaner, nested tag inspection, and DICOMDIR export.

**Features:** searchable DICOM metadata including nested sequences, image preview, ZIP inspection, local metadata cleaning, DICOMDIR creation, and a local post-cleaning audit. Available for Windows, Linux, and macOS through Python launchers.

Kleine lokale Desktop-Anwendung zum Lesen von DICOM-Dateien und ZIP-Archiven mit DICOM-Dateien. Die Anwendung zeigt eine Bildvorschau, File-Meta-Informationen und sämtliche DICOM-Datenelemente einschließlich verschachtelter Sequenzen. Die Tags lassen sich durchsuchen; ein Klick zeigt den vollständigen Textwert. Binärdaten werden mit ihrer Größe angezeigt.

**Zweck und Grenzen:** Dieses Projekt ist für die technische Sichtung von DICOM-Dateien und die Vorbereitung einer manuellen Datenschutzprüfung gedacht. Es wurde nicht für Diagnose, Therapieentscheidungen oder einen klinischen Arbeitsablauf validiert. Die medizinprodukterechtliche Einordnung hängt von der tatsächlichen Zweckbestimmung und Darstellung des Projekts ab; ein Hinweistext ersetzt diese Prüfung nicht. Für einen solchen Einsatz sind eine eigene fachliche und rechtliche Bewertung sowie geeignete Validierung erforderlich.

Die `ⓘ`-Schaltflächen neben Öffnen, den Cleaner-Modi, Speichern, KI-Prompt und Suche erklären die jeweilige Funktion und ihre Grenzen direkt in der Anwendung.

Das Programmsymbol liegt als [PNG](assets/dicom-reader.png) und [Windows-ICO](assets/dicom-reader.ico) im Ordner `assets`. Das Fenster lädt das PNG beim Start; die ICO-Datei kann für eine Windows-Verknüpfung verwendet werden. Mit `python assets/generate_icon.py` lassen sich beide Dateien aus der lokalen Vorlage erneut erzeugen.

## Start unter Windows

### Portables Windows-ZIP

Auf der [Releases-Seite](https://github.com/ZeroDayRobin/dicom-metadata-viewer-cleaner/releases) die Datei `DicomMetadataViewerCleaner-Windows-x64.zip` herunterladen, **vollständig entpacken** und `DicomMetadataViewerCleaner.exe` starten. Python, Paketinstallation und Internet sind dafür nicht erforderlich. Die EXE benötigt den mitgelieferten Ordner `_internal`; sie darf nicht einzeln herauskopiert werden. Die Lizenzhinweise liegen im ZIP unter `THIRD_PARTY_LICENSES`.

Das ZIP wird auf einem Windows-x64-System mit `powershell -ExecutionPolicy Bypass -File .\build-windows.ps1` aus dem Quellcode erstellt. Der Build benötigt Python 3.14 und beim ersten Installieren der Build-Abhängigkeiten Internet. Die Ausgabe liegt in `dist/`.

### Start aus dem Quellcode

Python 3.11 oder neuer installieren und **[start.bat](start.bat)** doppelklicken. Die Batchdatei legt beim ersten Start `.venv` an, prüft die Pakete aus `requirements.txt`, installiert fehlende Pakete und öffnet den Reader. Bei späteren Starts werden bereits passende Pakete weiterverwendet.

Der Reader verarbeitet DICOM-Dateien ausschließlich lokal und benötigt zur Nutzung kein Internet. Nur die Installation fehlender Python-Pakete durch `start.bat` kann beim ersten Start Internetzugang erfordern.

Optional kann eine DICOM-Datei oder ein ZIP auf `start.bat` gezogen werden.

## Start unter Linux

Python 3.11 bis 3.13 mit `venv`, `pip` und Tkinter installieren. In einer grafischen Desktop-Sitzung im Projektordner starten:

```sh
sh start-linux.sh
```

Für eine Datei: `sh start-linux.sh /pfad/zur/datei.dcm`. `sh start-linux.sh --check` prüft Installation und Tkinter ohne Fensterstart. Der Launcher legt `.venv-linux` an und installiert die Pakete beim ersten Start. Wenn `python3` nicht die passende Version ist, kann `DICOM_PYTHON=/pfad/zu/python3.13 sh start-linux.sh` verwendet werden. Je nach Distribution heißt das Tk-Paket beispielsweise `python3-tk`; `python3 -m tkinter` prüft die lokale GUI-Installation.

## Start unter macOS

macOS 13 oder neuer auf Intel- oder Apple-Silicon-Macs und Python 3.11 bis 3.13 mit Tkinter verwenden. Im Terminal im Projektordner:

```sh
sh start-macos.command
```

Zum Start per Doppelklick die Datei einmal ausführbar machen: `chmod +x start-macos.command`; danach `start-macos.command` im Finder öffnen. Eine DICOM-Datei oder ein ZIP kann als Argument übergeben werden; `sh start-macos.command --check` prüft die Installation. Der Launcher legt `.venv-macos` an und nutzt [requirements-macos.txt](requirements-macos.txt) mit einer für Intel und Apple Silicon verfügbaren ONNX-Runtime-Version. Wenn nötig, `DICOM_PYTHON=/pfad/zu/python3.13 sh start-macos.command` verwenden.

Linux und macOS verwenden dieselbe GUI und dieselben Funktionen wie Windows. Die Startdateien richten eine Python-Umgebung ein; sie sind keine fertig gebauten `.app`- oder AppImage-Pakete. Auf beiden Systemen kann die erste Paketinstallation Internetzugang benötigen; danach verarbeitet der Reader DICOM-Dateien lokal.

## Manueller Start

Eine passende Python-Version installieren, dann im Projektordner:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Eine Datei kann auch direkt übergeben werden:

```powershell
python app.py "C:\Pfad\zu\scan.dcm"
python app.py "C:\Pfad\zu\studie.zip"
```

Im ZIP werden Dateien mit DICOM-Kennung sowie Dateien mit `.dcm` oder `.dicom` angezeigt. ZIP-Inhalte werden direkt gelesen und nicht entpackt. Einzelne ZIP-Einträge sind auf 512 MiB begrenzt. Bei komprimierten DICOM-Bilddaten hängt die Vorschau vom verfügbaren Decoder ab; die Metadaten bleiben auch ohne Bilddecoder lesbar.

## Cleaner

Nach dem Öffnen einer DICOM-Datei oder eines ZIPs einen Modus auswählen und **Bereinigte Kopie speichern…** klicken:

- **Pseudonymisieren:** Patientennamen und IDs durch konsistente Ersatzwerte ersetzen.
- **Identifikatoren entfernen:** Patientennamen und IDs leeren, soweit das Dateiformat dies zulässt. Bei ZIP-Ausgaben erhält jede Patientengruppe für das DICOMDIR eine neue neutrale ID wie `P0001`.

In beiden Modi werden weitere Metadaten nach den Regeln der DICOM-Version 2024b mit `dicom-anonymizer` bereinigt, private Tags entfernt und zusammengehörige UIDs konsistent neu vergeben. Der Cleaner schreibt nur neue Dateien, prüft sie durch erneutes Einlesen und erstellt einen Bericht ohne Patientenwerte. Bei ZIP-Ausgaben erhalten die DICOM-Dateien neutrale Namen; andere ZIP-Inhalte werden nicht übernommen.

Zusätzlich bereinigt der Reader die Felder `(0040,0001)` bis `(0040,0005)`, `(0040,0009)`, `(0040,0010)` und `(0040,0011)` auch innerhalb verschachtelter Sequenzen. Geplante Datumswerte werden `00010101`, Uhrzeiten `000000.00`; AE-Titel, Stationsname und Ort werden geleert, die Schritt-ID wird `ANONYMIZED`. Die geschriebenen Dateien werden darauf geprüft. Prozedurbeschreibungen und -codes sowie Softwareversion und Spulenname bleiben erhalten und müssen vor Weitergabe gesondert bewertet werden.

**Wichtig:** Vor jedem Lauf erscheint ein Warnhinweis. Die Pixeldaten bleiben unverändert. Sichtbare Namen im Bild, erkennbare Gesichter und unerwartete Freitexte müssen vor einer Weitergabe geprüft werden. Die Ausgabe ist nicht automatisch anonym; auch pseudonymisierte Gesundheitsdaten können weiterhin personenbezogen sein. Der Prüfbericht ist keine Freigabe zur Veröffentlichung. Bei nicht verarbeitbaren Dateien wird der Lauf abgebrochen, ohne die Originale zu ändern.

Nach dem Speichern folgt ein **Prüfbericht**. Er zählt verbliebene auffällige Metadatenfelder auch in Sequenzen, etwa Prozedurbeschreibungen, Codes, Softwareversionen und Spulennamen. Außerdem untersucht RapidOCR die Bildpixel lokal auf erkennbaren Text (bei Mehrbilddateien höchstens 64 über die Datei verteilte Frames). Der Bericht nennt Treffer und nicht geprüfte Frames, speichert aber weder Metadatenwerte noch erkannte Texte. Ein OCR-Treffer kann harmlose Bildbeschriftung sein; ein ausbleibender Treffer beweist keine Anonymität. Die Bildpixel werden nicht verändert oder automatisch geschwärzt. Die benötigten OCR-Modelle werden mit dem Python-Paket installiert und beim Lesen ausschließlich aus der lokalen Paketinstallation geladen.

Bei ZIP-Ausgaben werden die bereinigten Dateien in eine neue DICOM File-set-Struktur geschrieben. Der Cleaner erstellt ein neues `DICOMDIR` mit Verweisen auf die neuen Dateinamen und prüft diese Verweise. Ein vorhandenes altes `DICOMDIR` wird ersetzt und im Bericht gezählt. Ein einzelnes `DICOMDIR` ohne Bilddateien kann der Cleaner nicht bereinigen. Falls eine besondere SOP-Klasse nicht in ein DICOMDIR aufgenommen werden kann, bricht der Lauf mit einer Fehlermeldung ab.

## Lokaler KI-Prompt

Nach dem Öffnen einer Datei oder eines ZIPs **KI-Prompt erzeugen…** klicken. Ein Fenster zeigt einen kopierbaren Prompt mit einer technischen Zusammenfassung: Anzahl der Instanzen und Frames, bekannte Modalitäten sowie Bildgrößen. Dateinamen, Pfade, UIDs, Patientenfelder, freie Beschreibungen und Pixeldaten werden nicht in den Prompt übernommen. Es findet keine Internetverbindung oder automatische KI-Analyse statt. Ohne separat angehängte DICOM-Dateien kann eine KI daraus keine Bildbefunde ableiten. Vor einem eigenen Upload müssen die Dateien einschließlich der Bilddaten auf personenbezogene Merkmale geprüft werden.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Die Anwendung liest Dateien lokal und schreibt keine Patientendaten in eine externe Datenbank oder einen Netzwerkdienst.

## Veröffentlichung und Datenschutz

Das Repository enthält nur Quellcode, Programmsymbol und synthetische Tests. Lade keine echten DICOM-Dateien, ZIP-Archive, Screenshots mit Patientendaten oder Bereinigungsberichte in GitHub Issues, Pull Requests oder Commits hoch. Ein `.gitignore` schließt gängige DICOM-Dateinamen und ZIP-Dateien aus, schützt aber nicht vor bereits versionierten oder absichtlich hinzugefügten Dateien. Prüfe vor dem ersten Push alle Dateien und die Git-Historie; siehe [Veröffentlichungscheckliste](PUBLISHING.md).

Der Reader sendet bei der Nutzung keine DICOM-Daten an einen Dienst; die OCR läuft mit lokal installierten Modellen. Die Installation von Abhängigkeiten über die Startdateien beziehungsweise `pip` kann Netzwerkzugriff auf Paketquellen erfordern. Wenn du den erzeugten Prompt selbst in einen externen KI-Dienst kopierst oder Dateien selbst hochlädst, gelten dessen Bedingungen und deine eigenen Datenschutzpflichten.

Der eigene Quellcode steht unter der [MIT-Lizenz](LICENSE) mit dem Rechteinhaber `ZeroDayRobin`. Für separat installierte Python-Pakete und OCR-Modelle gelten deren eigene Lizenzen; Hinweise stehen in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Sicherheitsmeldungen: [SECURITY.md](SECURITY.md).

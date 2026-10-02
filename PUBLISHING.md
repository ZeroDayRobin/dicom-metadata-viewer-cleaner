# Checkliste vor einer öffentlichen Veröffentlichung

1. Prüfe, ob `ZeroDayRobin` in `LICENSE` der richtige Rechteinhaber für den eigenen Quellcode ist und ob du die nötigen Rechte zur Lizenzierung hast.
2. Verwende einen neuen, leeren Git-Verlauf für dieses Quellcodeverzeichnis. Prüfe auch lokale Git-Historie, falls du doch ein vorhandenes Repository hochlädst: gelöschte Dateien können in alten Commits weiter enthalten sein.
3. Prüfe `git status --short --untracked-files=all` und `git ls-files` vor dem Push. Öffne jede zu veröffentlichende Datei und das Programmsymbol auf Namen, Pfade, Patientendaten, Zugangsdaten und fremde Bildrechte. Verlasse dich dabei nicht allein auf `.gitignore`.
4. Veröffentliche ausschließlich synthetische DICOM-Testdaten, wenn du später Beispiele hinzufügst. Gib auch in Issues, Pull Requests und Screenshots keine echten Patienteninformationen preis.
5. Prüfe Zweckbeschreibung, Cleaner-Hinweise und OCR-Grenzen vor jeder Veröffentlichung. Bewirb das Programm nicht als klinisch validiertes Diagnosewerkzeug oder als Garantie für Anonymisierung.
6. Wenn du eine EXE, ein ZIP mit installierten Paketen oder andere Binärdateien verteilst, prüfe die Lizenzen und erforderlichen Lizenzdateien **aller** mitgelieferten Abhängigkeiten und Modelle erneut. `THIRD_PARTY_NOTICES.md` beschreibt nur die direkt verwendeten Pakete der Quellcodeversion.
7. Kläre bei tatsächlicher Verarbeitung oder Weitergabe von Gesundheitsdaten die Rechtsgrundlage, Zugriffsrechte und deine organisatorischen Datenschutzpflichten unabhängig vom Tool. Bei klinischer Zweckbestimmung ist eine gesonderte Medizinproduktebewertung nötig.

Diese Checkliste und die MIT-Lizenz ersetzen keine Rechtsberatung oder technische Freigabe konkreter Datensätze.

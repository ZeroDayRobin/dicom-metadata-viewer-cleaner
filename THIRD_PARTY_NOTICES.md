# Drittanbieter und Lizenzhinweise

Dieses Repository enthält keine Kopien der folgenden Python-Pakete oder OCR-Modelle. `pip install -r requirements.txt` installiert sie gesondert. Die MIT-Lizenz dieses Projekts ersetzt deren jeweilige Lizenzen nicht.

| Direkte Abhängigkeit | Im Projekt verwendeter Versionsbereich | Lizenzhinweis | Quelle |
| --- | --- | --- | --- |
| pydicom | `>=3.0,<4` | MIT | [Projekt](https://github.com/pydicom/pydicom) |
| NumPy | `>=2.0,<3` | BSD-3-Clause und Lizenzen enthaltener Komponenten; maßgeblich ist die Lizenzdatei des installierten Pakets | [Projekt](https://github.com/numpy/numpy) |
| Pillow | `>=11,<13` | MIT-CMU | [Projekt](https://github.com/python-pillow/Pillow) |
| dicom-anonymizer | `>=2.1,<3` | BSD-3-Clause | [Projekt](https://github.com/KitwareMedical/dicom-anonymizer) |
| RapidOCR | `==3.9.2` | Apache-2.0; gebündelte OCR-Modelle stammen aus PaddleOCR und haben eigene Zuordnungshinweise | [Projekt und Modellhinweise](https://github.com/RapidAI/RapidOCR) |
| ONNX Runtime | Windows/Linux: `>=1.27,<2`; macOS: `==1.23.2` | MIT; enthält weitere Drittanbieterhinweise | [Projekt](https://github.com/microsoft/onnxruntime) |

Die Angaben wurden anhand der lokal installierten Paketmetadaten und der Projektseiten erstellt. Transitive Abhängigkeiten sind hier nicht vollständig aufgeführt. Für eine Weitergabe von Paketen, Modellen oder ausführbaren Bündeln müssen die konkreten installierten Versionen und deren `LICENSE`-/`NOTICE`-Dateien geprüft und erforderliche Hinweise mitgegeben werden. Insbesondere enthält das hier installierte RapidOCR-3.9.2-Wheel keine separate Modell-Lizenzdatei; vor einer gebündelten Weitergabe ist die Modellzuordnung anhand der Herstellerangaben erneut zu prüfen. Beim reinen Quellcode-Upload werden diese Pakete und Modelle nicht mit veröffentlicht.

"""Simple local DICOM viewer. Start with: python app.py"""

import sys
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from cleaner import clean_source
from prompt_builder import build_analysis_prompt
from reader import list_entries, metadata_rows, preview_image, read_entry


class DicomApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DICOM Reader")
        self.geometry("1200x760")
        self.minsize(850, 520)
        icon_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets"
        with Image.open(icon_dir / "dicom-reader.png") as icon:
            self.icon_image = ImageTk.PhotoImage(icon, master=self)
        self.iconphoto(True, self.icon_image)
        self.entries = []
        self.rows = []
        self.photo = None
        self.image = None
        self.info_buttons = {}

        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        ttk.Style(self).configure("Privacy.TLabel", foreground="#c62828", font=("Segoe UI", 10, "bold"))
        self.privacy_label = ttk.Label(
            toolbar,
            text="Dateien bleiben lokal und kein Internet nötig!",
            style="Privacy.TLabel",
        )
        self.privacy_label.pack(side="right", padx=(12, 0))
        ttk.Button(toolbar, text="DICOM / ZIP öffnen…", command=self.open_dialog).pack(side="left")
        self.add_info_button(
            toolbar, "open", "DICOM / ZIP öffnen",
            "Wählt eine DICOM-Datei oder ZIP-Datei aus und zeigt ihre Metadaten und, falls möglich, "
            "eine Bildvorschau. Die Dateien werden lokal gelesen und dabei nicht verändert.",
        )
        self.source_label = ttk.Label(toolbar, text="Keine Datei geöffnet", padding=(12, 0))
        self.source_label.pack(side="left")

        mode_bar = ttk.Frame(self, padding=(8, 0, 8, 2))
        mode_bar.pack(fill="x")
        ttk.Label(mode_bar, text="Cleaner:").pack(side="left")
        self.clean_mode = tk.StringVar(value="pseudonymize")
        ttk.Radiobutton(
            mode_bar, text="Pseudonymisieren", variable=self.clean_mode, value="pseudonymize"
        ).pack(side="left", padx=(8, 0))
        self.add_info_button(
            mode_bar, "pseudonymize", "Pseudonymisieren",
            "Patientenname und Patienten-ID erhalten konsistente Ersatzwerte. Weitere geeignete "
            "Metadaten werden bereinigt, UIDs neu vergeben und private Tags entfernt. "
            "Bildpixel bleiben unverändert; sichtbare Namen müssen zusätzlich geprüft werden.",
        )
        ttk.Radiobutton(
            mode_bar, text="Identifikatoren entfernen", variable=self.clean_mode, value="remove"
        ).pack(side="left", padx=(8, 0))
        self.add_info_button(
            mode_bar, "remove", "Identifikatoren entfernen",
            "Leert Patientenname und Patienten-ID. In ZIP-Ausgaben bekommt jede Patientengruppe "
            "eine neutrale ID wie P0001, die für das neue DICOMDIR nötig ist. Andere Metadaten "
            "werden ebenfalls bereinigt; Bildpixel bleiben unverändert.",
        )

        action_bar = ttk.Frame(self, padding=(8, 0, 8, 8))
        action_bar.pack(fill="x")
        ttk.Button(action_bar, text="Bereinigte Kopie speichern…", command=self.run_cleaner).pack(
            side="left"
        )
        self.add_info_button(
            action_bar, "save", "Bereinigte Kopie speichern",
            "Zeigt zuerst einen Warnhinweis und speichert danach eine neue bereinigte Kopie. "
            "Die Originaldatei bleibt erhalten. Bei ZIP-Ausgaben wird ein neues DICOMDIR erstellt; "
            "zusätzlich entsteht ein Prüfbericht mit Metadatenhinweisen und lokaler Bildtext-Erkennung. "
            "OCR-Treffer sind nur Hinweise; Bilddaten müssen vor Weitergabe visuell geprüft werden.",
        )
        ttk.Button(action_bar, text="KI-Prompt erzeugen…", command=self.show_ai_prompt).pack(
            side="left", padx=(12, 0)
        )
        self.add_info_button(
            action_bar, "prompt", "KI-Prompt erzeugen",
            "Erstellt lokal einen kopierbaren Text aus technischen DICOM-Merkmalen. "
            "Es werden keine Dateien an eine KI gesendet und keine Bilder analysiert. "
            "Der Prompt enthält keine Patientennamen, IDs, Dateipfade oder Bildpixel.",
        )

        main = ttk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        left = ttk.Frame(main)
        right = ttk.Frame(main)
        main.add(left, weight=1)
        main.add(right, weight=4)

        ttk.Label(left, text="Dateien im Archiv").pack(anchor="w", pady=(0, 4))
        files_frame = ttk.Frame(left)
        files_frame.pack(fill="both", expand=True)
        self.files = tk.Listbox(files_frame, exportselection=False)
        self.files.pack(side="left", fill="both", expand=True)
        file_scroll = ttk.Scrollbar(files_frame, orient="vertical", command=self.files.yview)
        file_scroll.pack(side="right", fill="y")
        self.files.configure(yscrollcommand=file_scroll.set)
        self.files.bind("<<ListboxSelect>>", self.select_file)

        top = ttk.Frame(right)
        top.pack(fill="x")
        ttk.Label(top, text="Metadaten").pack(side="left")
        ttk.Label(top, text="Suche:").pack(side="left", padx=(24, 5))
        self.add_info_button(
            top, "search", "Metadaten durchsuchen",
            "Filtert die angezeigten Metadaten der aktuell ausgewählten DICOM-Datei nach "
            "Tag, Wert, VR oder Name. Die Suche verändert keine Dateien.",
        )
        self.search = tk.StringVar()
        search_box = ttk.Entry(top, textvariable=self.search)
        search_box.pack(side="left", fill="x", expand=True)
        self.search.trace_add("write", lambda *_: self.show_rows())

        body = ttk.PanedWindow(right, orient="vertical")
        body.pack(fill="both", expand=True, pady=(6, 0))
        table_frame = ttk.Frame(body)
        bottom = ttk.Frame(body)
        body.add(table_frame, weight=4)
        body.add(bottom, weight=2)

        self.tree = ttk.Treeview(table_frame, columns=("tag", "vr", "name", "value"), show="headings")
        for column, title, width in (("tag", "Tag", 105), ("vr", "VR", 45),
                                     ("name", "Name", 240), ("value", "Wert", 430)):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, minwidth=40, stretch=column in ("name", "value"))
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self.show_detail)

        preview_frame = ttk.LabelFrame(bottom, text="Bildvorschau", padding=6)
        preview_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.preview = ttk.Label(preview_frame, text="Keine Bilddaten", anchor="center")
        self.preview.pack(fill="both", expand=True)
        self.preview.bind("<Configure>", lambda *_: self.refresh_preview())

        detail_frame = ttk.LabelFrame(bottom, text="Vollständiger Wert", padding=6)
        detail_frame.pack(side="left", fill="both", expand=True)
        self.detail = tk.Text(detail_frame, wrap="word", height=8, state="disabled")
        self.detail.pack(fill="both", expand=True)

        self.status = ttk.Label(self, text="Bereit", padding=(8, 3))
        self.status.pack(fill="x")

    def add_info_button(self, parent, key, title, description):
        button = ttk.Button(
            parent, text="ⓘ", width=2,
            command=lambda: messagebox.showinfo(title, description, parent=self),
        )
        button.pack(side="left", padx=(3, 0))
        self.info_buttons[key] = button
        return button

    def open_dialog(self):
        path = filedialog.askopenfilename(
            title="DICOM-Datei oder ZIP auswählen",
            filetypes=[("DICOM und ZIP", "*.dcm *.dicom *.zip"), ("Alle Dateien", "*.*")],
        )
        if path:
            self.open_path(path)

    def show_ai_prompt(self):
        try:
            prompt = build_analysis_prompt(self.entries)
        except Exception as exc:
            messagebox.showerror("KI-Prompt konnte nicht erzeugt werden", str(exc))
            return
        dialog = tk.Toplevel(self)
        dialog.title("Lokaler KI-Prompt")
        dialog.geometry("820x550")
        dialog.transient(self)
        ttk.Label(
            dialog,
            text="Nur technische Zusammenfassung. Es wird nichts hochgeladen oder an eine KI gesendet.",
            padding=10,
        ).pack(anchor="w")
        frame = ttk.Frame(dialog, padding=(10, 0, 10, 8))
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word")
        text.insert("1.0", prompt)
        text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        scroll.pack(side="right", fill="y")
        text.configure(yscrollcommand=scroll.set)

        def copy_prompt():
            self.clipboard_clear()
            self.clipboard_append(text.get("1.0", "end-1c"))
            self.status.configure(text="KI-Prompt in Zwischenablage kopiert")

        ttk.Button(dialog, text="Prompt kopieren", command=copy_prompt).pack(pady=(0, 10))

    def run_cleaner(self):
        if not self.entries:
            messagebox.showinfo("Cleaner", "Bitte zuerst eine DICOM-Datei oder ein ZIP öffnen.")
            return
        warning = (
            "Die Bereinigung verändert nur DICOM-Metadaten. Namen oder andere Merkmale "
            "können weiterhin direkt im Bild sichtbar sein. Auch unbekannte Freitexte "
            "oder besondere DICOM-Objekte müssen geprüft werden.\n\n"
            "Die Originaldatei bleibt erhalten. Es wird eine neue Kopie geschrieben und "
            "danach erneut geprüft. Bitte die Ausgabe vor Weitergabe visuell kontrollieren.\n\n"
            "Der Prüfbericht nennt verbliebene auffällige Metadatenfelder und mögliche "
            "Bildtexte aus einer lokalen OCR-Prüfung. Erkannte Texte werden nicht protokolliert; "
            "nicht geprüfte Frames werden ausgewiesen.\n\n"
            "Bei ZIP-Ausgaben wird ein neues DICOMDIR mit passenden Dateiverweisen erstellt. "
            "Dafür können leere Kennfelder neutrale Ersatzwerte erhalten.\n\n"
            "Bereinigung jetzt durchführen?"
        )
        if not messagebox.askokcancel("Hinweis vor der Bereinigung", warning, icon="warning"):
            return

        source = self.entries[0].source
        is_zip = zipfile.is_zipfile(source)
        extension = ".zip" if is_zip else ".dcm"
        output = filedialog.asksaveasfilename(
            title="Bereinigte Kopie speichern",
            initialdir=str(source.parent),
            initialfile=f"bereinigt{extension}",
            defaultextension=extension,
            filetypes=[("ZIP-Archiv", "*.zip")] if is_zip else [("DICOM-Datei", "*.dcm")],
        )
        if not output:
            return
        try:
            def progress(done, total):
                self.status.configure(text=f"Bereinigung läuft: {done}/{total} Datei(en)")
                self.update_idletasks()

            def audit_progress(done, _total):
                self.status.configure(text=f"Prüfbericht: {done} DICOM-Instanz(en) geprüft")
                self.update_idletasks()

            result = clean_source(
                source, output, self.clean_mode.get(),
                progress=progress, audit_progress=audit_progress,
            )
        except Exception as exc:
            self.status.configure(text="Bereinigung fehlgeschlagen")
            messagebox.showerror("Bereinigung fehlgeschlagen", str(exc))
            return
        self.status.configure(text=f"{result.count} Datei(en) bereinigt: {result.output}")
        dicomdir_note = (
            f"\n{result.replaced_dicomdir} altes DICOMDIR ersetzt; neues DICOMDIR erstellt.\n"
            if is_zip else ""
        )
        messagebox.showinfo(
            "Bereinigung abgeschlossen",
            f"{result.count} Datei(en) als neue Kopie gespeichert.\n\n"
            f"Ausgabe: {result.output}\nBericht: {result.report}\n"
            f"{dicomdir_note}\n"
            f"Prüfbericht: {result.audit.metadata_files} Instanz(en) mit Metadatenhinweisen; "
            f"{result.audit.pixel_frames_with_text} Frame(s) mit OCR-Text; "
            f"{result.audit.pixel_frames_unchecked} Frame(s) nicht geprüft.\n\n"
            "Bitte Bilddaten vor einer Weitergabe auf sichtbare Namen und erkennbare Merkmale prüfen.",
        )

    def open_path(self, path):
        try:
            entries = list_entries(path)
        except Exception as exc:
            messagebox.showerror("Datei kann nicht geöffnet werden", str(exc))
            return
        self.entries = entries
        self.files.delete(0, "end")
        for entry in entries:
            self.files.insert("end", entry.name)
        self.source_label.configure(text=str(path))
        self.rows = []
        self.show_rows()
        self.image = None
        self.refresh_preview()
        self.status.configure(text=f"{len(entries)} DICOM-Datei(en) gefunden")
        if entries:
            self.files.selection_set(0)
            self.select_file()

    def select_file(self, _event=None):
        selection = self.files.curselection()
        if not selection:
            return
        entry = self.entries[selection[0]]
        try:
            dataset = read_entry(entry)
            self.rows = metadata_rows(dataset)
            self.show_rows()
            try:
                self.image = preview_image(dataset)
                preview_status = "Bildvorschau geladen"
            except Exception as exc:
                self.image = None
                preview_status = f"Bildvorschau nicht verfügbar: {exc}"
            self.refresh_preview()
            self.status.configure(text=f"{entry.name} · {len(self.rows)} Metadatenzeilen · {preview_status}")
        except Exception as exc:
            self.rows = []
            self.show_rows()
            self.image = None
            self.refresh_preview()
            messagebox.showerror("DICOM-Datei kann nicht gelesen werden", f"{entry.name}\n\n{exc}")

    def show_rows(self):
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().casefold().strip()
        parents = {}
        for index, (depth, tag, vr, name, value) in enumerate(self.rows):
            matches = not query or query in f"{tag} {vr} {name} {value}".casefold()
            if not matches:
                continue
            parent = parents.get(depth - 1, "") if not query else ""
            item = self.tree.insert(parent, "end", values=(tag, vr, name, value[:250]))
            self.tree.item(item, tags=(str(index),))
            if not query:
                parents[depth] = item

    def show_detail(self, _event=None):
        selection = self.tree.selection()
        value = ""
        if selection:
            tags = self.tree.item(selection[0], "tags")
            if tags:
                value = self.rows[int(tags[0])][4]
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", value)
        self.detail.configure(state="disabled")

    def refresh_preview(self):
        if self.image is None:
            self.preview.configure(image="", text="Keine darstellbare Bildvorschau")
            self.photo = None
            return
        width = max(self.preview.winfo_width() - 12, 100)
        height = max(self.preview.winfo_height() - 12, 100)
        image = self.image.copy()
        image.thumbnail((width, height))
        self.photo = ImageTk.PhotoImage(image)
        self.preview.configure(image=self.photo, text="")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        from audit import create_local_ocr

        create_local_ocr()
        app = DicomApp()
        app.withdraw()
        app.update_idletasks()
        app.destroy()
        sys.exit(0)
    app = DicomApp()
    if len(sys.argv) > 1:
        app.open_path(sys.argv[1])
    app.mainloop()

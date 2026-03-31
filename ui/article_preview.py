"""Okno podglądu wygenerowanego artykułu (Markdown)."""

from pathlib import Path
import customtkinter as ctk
from ui.components import ACCENT_GREEN, ACCENT_GREEN_HOVER


class ArticlePreviewWindow(ctk.CTkToplevel):
    """Okno podglądu artykułu — wyświetla zawartość pliku .md."""

    def __init__(self, master, filepath: str, title: str = ""):
        super().__init__(master)
        self.title(f"Podgląd: {title or Path(filepath).name}")
        self.geometry("900x700")
        self.minsize(600, 400)
        self.transient(master.winfo_toplevel())

        self._filepath = filepath
        self._build_ui()
        self._load_content()
        self.after(100, self.focus_force)

    def _build_ui(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(10, 5))

        self.filename_label = ctk.CTkLabel(
            toolbar,
            text=Path(self._filepath).name,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="gray60",
        )
        self.filename_label.pack(side="left")

        self.chars_label = ctk.CTkLabel(
            toolbar,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray50",
        )
        self.chars_label.pack(side="left", padx=(15, 0))

        ctk.CTkButton(
            toolbar,
            text="Otwórz folder",
            fg_color="gray30",
            hover_color="gray40",
            width=120,
            height=28,
            font=ctk.CTkFont(size=12),
            command=self._open_folder,
        ).pack(side="right")

        ctk.CTkButton(
            toolbar,
            text="Kopiuj wszystko",
            fg_color="gray30",
            hover_color="gray40",
            width=120,
            height=28,
            font=ctk.CTkFont(size=12),
            command=self._copy_all,
        ).pack(side="right", padx=(0, 8))

        # Obszar tekstu
        self.textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
            state="disabled",
        )
        self.textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def _load_content(self):
        try:
            content = Path(self._filepath).read_text(encoding="utf-8")
            char_count = len(content)
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", content)
            self.textbox.configure(state="disabled")

            color = ACCENT_GREEN if 8500 <= char_count <= 9500 else "#F59E0B"
            self.chars_label.configure(
                text=f"{char_count:,} znaków",
                text_color=color,
            )
        except Exception as e:
            self.textbox.configure(state="normal")
            self.textbox.insert("1.0", f"Błąd odczytu pliku:\n{e}")
            self.textbox.configure(state="disabled")

    def _copy_all(self):
        try:
            content = Path(self._filepath).read_text(encoding="utf-8")
            self.clipboard_clear()
            self.clipboard_append(content)
        except Exception:
            pass

    def _open_folder(self):
        import subprocess, platform
        folder = str(Path(self._filepath).parent)
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", folder])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

"""Reużywalne komponenty UI dla Bulk Blog Writer."""

import customtkinter as ctk


# Kolory motywu SemTree
ACCENT_GREEN = "#2BE275"
ACCENT_GREEN_HOVER = "#25C466"
COLOR_GRAY = "#6B7280"
COLOR_BLUE = "#3B82F6"
COLOR_ORANGE = "#F59E0B"
COLOR_RED = "#EF4444"
COLOR_GREEN = "#22C55E"


class StatusBadge(ctk.CTkLabel):
    """Kolorowy badge ze statusem artykułu."""

    STATUS_CONFIG = {
        "waiting": {"text": "Oczekuje", "fg_color": COLOR_GRAY},
        "generating": {"text": "Generowanie...", "fg_color": COLOR_BLUE},
        "success": {"text": "Gotowy", "fg_color": COLOR_GREEN},
        "warning": {"text": "Gotowy", "fg_color": COLOR_ORANGE},
        "error": {"text": "Błąd", "fg_color": COLOR_RED},
    }

    def __init__(self, master, status: str = "waiting", detail: str = "", **kwargs):
        config = self.STATUS_CONFIG.get(status, self.STATUS_CONFIG["waiting"])
        text = config["text"]
        if detail:
            text = f"{text} ({detail})"
        super().__init__(
            master,
            text=text,
            fg_color=config["fg_color"],
            corner_radius=6,
            text_color="white",
            font=ctk.CTkFont(size=11),
            padx=8,
            pady=2,
            **kwargs,
        )

    def set_status(self, status: str, detail: str = ""):
        config = self.STATUS_CONFIG.get(status, self.STATUS_CONFIG["waiting"])
        text = config["text"]
        if detail:
            text = f"{text} ({detail})"
        self.configure(text=text, fg_color=config["fg_color"])


class LogConsole(ctk.CTkTextbox):
    """Mały obszar tekstowy z logiem generowania."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("height", 100)
        kwargs.setdefault("font", ctk.CTkFont(family="Consolas", size=11))
        kwargs.setdefault("state", "disabled")
        kwargs.setdefault("wrap", "word")
        super().__init__(master, **kwargs)

    def append(self, message: str):
        """Dodaje linię do konsoli."""
        self.configure(state="normal")
        self.insert("end", message + "\n")
        self.see("end")
        self.configure(state="disabled")

    def clear(self):
        """Czyści konsolę."""
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")

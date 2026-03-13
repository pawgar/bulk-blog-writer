"""Zakładka Historia — log wygenerowanych artykułów."""

import json
from pathlib import Path
from datetime import datetime

import customtkinter as ctk

from ui.components import ACCENT_GREEN, ACCENT_GREEN_HOVER, COLOR_RED

HISTORY_PATH = Path(__file__).parent.parent / "history.json"


def load_history() -> dict:
    """Wczytuje historię z pliku."""
    if not HISTORY_PATH.exists():
        return {"sessions": []}
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"sessions": []}


def save_history(data: dict):
    """Zapisuje historię do pliku."""
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_session(session: dict):
    """Dodaje sesję do historii."""
    history = load_history()
    history["sessions"].insert(0, session)
    save_history(history)


class HistoryTab(ctk.CTkFrame):
    """Zakładka z historią generowania."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Tytuł
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="Historia generowania",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="Odśwież",
            width=80,
            fg_color="gray30",
            hover_color="gray40",
            command=self.refresh,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            header,
            text="Wyczyść historię",
            width=130,
            fg_color=COLOR_RED,
            hover_color="#DC2626",
            command=self._clear_history,
        ).pack(side="right")

        # Scrollable area
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.no_data_label = ctk.CTkLabel(
            self.scroll_frame,
            text="Brak historii generowania.",
            font=ctk.CTkFont(size=14),
            text_color="gray50",
        )

    def refresh(self):
        """Odświeża listę sesji."""
        # Usuń istniejące elementy
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        history = load_history()
        sessions = history.get("sessions", [])

        if not sessions:
            self.no_data_label = ctk.CTkLabel(
                self.scroll_frame,
                text="Brak historii generowania.",
                font=ctk.CTkFont(size=14),
                text_color="gray50",
            )
            self.no_data_label.pack(pady=40)
            return

        for session in sessions:
            self._create_session_card(session)

    def _create_session_card(self, session: dict):
        """Tworzy kartę dla jednej sesji generowania."""
        card = ctk.CTkFrame(self.scroll_frame, corner_radius=8)
        card.pack(fill="x", pady=(0, 8))

        # Główny wiersz
        main_row = ctk.CTkFrame(card, fg_color="transparent")
        main_row.pack(fill="x", padx=12, pady=8)

        # Data
        ts = session.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            date_str = ts[:16] if ts else "—"

        ctk.CTkLabel(
            main_row,
            text=date_str,
            font=ctk.CTkFont(size=12, weight="bold"),
            width=130,
        ).pack(side="left")

        # Plik XLSX
        xlsx_name = session.get("xlsx_file", "—")
        if len(xlsx_name) > 35:
            xlsx_name = "..." + xlsx_name[-32:]
        ctk.CTkLabel(
            main_row, text=xlsx_name, font=ctk.CTkFont(size=12), width=250
        ).pack(side="left", padx=(5, 0))

        # Domena
        ctk.CTkLabel(
            main_row,
            text=session.get("domain", "—") or "—",
            font=ctk.CTkFont(size=12),
            width=130,
        ).pack(side="left", padx=(5, 0))

        # Język
        ctk.CTkLabel(
            main_row,
            text=session.get("language", "—").upper(),
            font=ctk.CTkFont(size=12),
            width=40,
        ).pack(side="left", padx=(5, 0))

        # Statystyki
        total = session.get("total", 0)
        success = session.get("success", 0)
        failed = session.get("failed", 0)
        stats_text = f"{success}/{total}"
        stats_color = ACCENT_GREEN if failed == 0 else "#F59E0B"

        ctk.CTkLabel(
            main_row,
            text=stats_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=stats_color,
            width=60,
        ).pack(side="left", padx=(5, 0))

        if failed > 0:
            ctk.CTkLabel(
                main_row,
                text=f"({failed} błędów)",
                font=ctk.CTkFont(size=11),
                text_color=COLOR_RED,
            ).pack(side="left", padx=(2, 0))

        # Czas
        elapsed = session.get("elapsed_seconds", 0)
        if elapsed:
            mins = elapsed // 60
            secs = elapsed % 60
            ctk.CTkLabel(
                main_row,
                text=f"{mins}m {secs}s",
                font=ctk.CTkFont(size=11),
                text_color="gray50",
            ).pack(side="right")

        # Rozwijane szczegóły — artykuły
        articles = session.get("articles", [])
        if articles:
            detail_btn = ctk.CTkButton(
                card,
                text=f"Pokaż {len(articles)} artykułów ▼",
                fg_color="transparent",
                hover_color="gray25",
                text_color="gray50",
                font=ctk.CTkFont(size=11),
                height=24,
                command=lambda c=card, a=articles: self._toggle_details(c, a),
            )
            detail_btn.pack(anchor="w", padx=12, pady=(0, 4))

    def _toggle_details(self, card: ctk.CTkFrame, articles: list):
        """Pokazuje/ukrywa szczegóły artykułów."""
        detail_tag = "_details_frame"
        existing = getattr(card, detail_tag, None)
        if existing:
            existing.destroy()
            setattr(card, detail_tag, None)
            return

        details = ctk.CTkFrame(card, fg_color="gray15", corner_radius=6)
        details.pack(fill="x", padx=12, pady=(0, 8))
        setattr(card, detail_tag, details)

        for art in articles:
            row = ctk.CTkFrame(details, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=1)

            status = art.get("status", "")
            icon = "✅" if status == "success" else "❌"
            chars = art.get("chars", 0)
            chars_str = f" ({chars} zn.)" if chars else ""

            ctk.CTkLabel(
                row,
                text=f"{icon} {art.get('filename', '—')}{chars_str}",
                font=ctk.CTkFont(size=11),
                anchor="w",
            ).pack(side="left")

    def _clear_history(self):
        """Czyści całą historię."""
        save_history({"sessions": []})
        self.refresh()

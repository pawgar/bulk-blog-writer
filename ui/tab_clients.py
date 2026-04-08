"""Zakładka Klienci — karty klientów per domena."""

import customtkinter as ctk

from clients_manager import (
    load_clients, save_client, delete_client, CLIENT_FIELDS, INTERNAL_LINKS_FIELD,
)
from ui.components import ACCENT_GREEN, ACCENT_GREEN_HOVER, COLOR_RED


class ClientsTab(ctk.CTkFrame):
    """Zakładka z kartami klientów — profil per domena."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._current_domain: str | None = None
        self._entries: dict[str, ctk.CTkTextbox] = {}
        self._build_ui()
        self.refresh_list()

    def _build_ui(self):
        # Dwie kolumny: lista domen (lewa) + formularz (prawa)
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # === Lewa kolumna: lista klientów ===
        left = ctk.CTkFrame(container, fg_color="transparent", width=260)
        left.pack(side="left", fill="y", padx=(0, 15))
        left.pack_propagate(False)

        ctk.CTkLabel(
            left, text="Klienci",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", pady=(0, 8))

        # Dodawanie nowego klienta
        add_frame = ctk.CTkFrame(left, fg_color="transparent")
        add_frame.pack(fill="x", pady=(0, 8))

        self._new_domain_entry = ctk.CTkEntry(
            add_frame, placeholder_text="domena.pl",
            font=ctk.CTkFont(size=12), height=32,
        )
        self._new_domain_entry.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            add_frame, text="+", width=36, height=32,
            fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_HOVER,
            text_color="black", font=ctk.CTkFont(size=16, weight="bold"),
            command=self._add_client,
        ).pack(side="left", padx=(6, 0))

        # Lista domen (scrollable)
        self._list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._list_frame.pack(fill="both", expand=True)

        # === Prawa kolumna: formularz ===
        right = ctk.CTkFrame(container, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        self._form_title = ctk.CTkLabel(
            right, text="Wybierz klienta z listy",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="gray50",
        )
        self._form_title.pack(anchor="w", pady=(0, 10))

        self._form_frame = ctk.CTkFrame(right, fg_color="transparent")
        self._form_frame.pack(fill="both", expand=True)

        # Budujemy pola formularza
        for field_key, label in CLIENT_FIELDS.items():
            row = ctk.CTkFrame(self._form_frame, fg_color="transparent")
            row.pack(fill="x", pady=(0, 8))

            ctk.CTkLabel(
                row, text=label,
                font=ctk.CTkFont(size=13), width=160, anchor="w",
            ).pack(side="left", anchor="n", pady=(4, 0))

            textbox = ctk.CTkTextbox(
                row, height=50, font=ctk.CTkFont(size=12),
                wrap="word", state="disabled",
            )
            textbox.pack(side="left", fill="x", expand=True)
            self._entries[field_key] = textbox

        # Sekcja linków wewnętrznych
        links_row = ctk.CTkFrame(self._form_frame, fg_color="transparent")
        links_row.pack(fill="x", pady=(0, 8))

        links_label_frame = ctk.CTkFrame(links_row, fg_color="transparent")
        links_label_frame.pack(side="left", anchor="n", pady=(4, 0))

        ctk.CTkLabel(
            links_label_frame, text="Linki wewnętrzne",
            font=ctk.CTkFont(size=13), width=160, anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            links_label_frame, text="(jeden URL per linia)",
            font=ctk.CTkFont(size=10), text_color="gray50", width=160, anchor="w",
        ).pack(anchor="w")

        self._links_textbox = ctk.CTkTextbox(
            links_row, height=90, font=ctk.CTkFont(size=12),
            wrap="word", state="disabled",
        )
        self._links_textbox.pack(side="left", fill="x", expand=True)

        # Przyciski pod formularzem
        btn_frame = ctk.CTkFrame(self._form_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(15, 0))

        self._save_btn = ctk.CTkButton(
            btn_frame, text="Zapisz kartę klienta",
            fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_HOVER,
            text_color="black", font=ctk.CTkFont(size=14, weight="bold"),
            width=200, height=38, command=self._save_client, state="disabled",
        )
        self._save_btn.pack(side="left")

        self._delete_btn = ctk.CTkButton(
            btn_frame, text="Usuń klienta",
            fg_color=COLOR_RED, hover_color="#DC2626",
            width=130, height=38, command=self._delete_client, state="disabled",
        )
        self._delete_btn.pack(side="left", padx=(12, 0))

        self._status_label = ctk.CTkLabel(
            btn_frame, text="", font=ctk.CTkFont(size=12),
        )
        self._status_label.pack(side="left", padx=(15, 0))

    def refresh_list(self):
        """Odświeża listę klientów w lewej kolumnie."""
        for widget in self._list_frame.winfo_children():
            widget.destroy()

        clients = load_clients()
        if not clients:
            ctk.CTkLabel(
                self._list_frame,
                text="Brak klientów.\nDodaj domenę powyżej.",
                text_color="gray50", font=ctk.CTkFont(size=12),
            ).pack(pady=20)
            return

        for domain in sorted(clients.keys()):
            client = clients[domain]
            industry = client.get("industry", "")
            subtitle = industry[:30] + "..." if len(industry) > 30 else industry

            btn = ctk.CTkButton(
                self._list_frame,
                text=f"{domain}\n{subtitle}" if subtitle else domain,
                fg_color="gray25" if domain != self._current_domain else ACCENT_GREEN,
                hover_color="gray35",
                text_color="white" if domain != self._current_domain else "black",
                font=ctk.CTkFont(size=12),
                anchor="w",
                height=42,
                command=lambda d=domain: self._select_client(d),
            )
            btn.pack(fill="x", pady=(0, 4))

    def _add_client(self):
        """Dodaje nowego klienta z pustą kartą."""
        domain = self._new_domain_entry.get().strip().lower()
        if not domain:
            return
        # Usuń protokół i ścieżkę
        domain = domain.removeprefix("https://").removeprefix("http://").rstrip("/")
        domain = domain.removeprefix("www.")

        clients = load_clients()
        if domain not in clients:
            save_client(domain, {k: "" for k in CLIENT_FIELDS})
            self._new_domain_entry.delete(0, "end")
        self._current_domain = domain
        self.refresh_list()
        self._load_form(domain)

    def _select_client(self, domain: str):
        """Zaznacza klienta i ładuje formularz."""
        self._current_domain = domain
        self.refresh_list()
        self._load_form(domain)

    def _load_form(self, domain: str):
        """Wypełnia formularz danymi klienta."""
        clients = load_clients()
        data = clients.get(domain, {})

        self._form_title.configure(
            text=f"Karta klienta: {domain}",
            text_color="white",
        )

        for field_key, textbox in self._entries.items():
            textbox.configure(state="normal")
            textbox.delete("1.0", "end")
            textbox.insert("1.0", data.get(field_key, ""))

        # Linki wewnętrzne
        self._links_textbox.configure(state="normal")
        self._links_textbox.delete("1.0", "end")
        self._links_textbox.insert("1.0", data.get(INTERNAL_LINKS_FIELD, ""))

        self._save_btn.configure(state="normal")
        self._delete_btn.configure(state="normal")
        self._status_label.configure(text="")

    def _save_client(self):
        """Zapisuje kartę klienta."""
        if not self._current_domain:
            return
        data = {}
        for field_key, textbox in self._entries.items():
            data[field_key] = textbox.get("1.0", "end").strip()
        data[INTERNAL_LINKS_FIELD] = self._links_textbox.get("1.0", "end").strip()
        save_client(self._current_domain, data)
        self._status_label.configure(
            text="Zapisano.",
            text_color=ACCENT_GREEN,
        )
        self.refresh_list()

    def _delete_client(self):
        """Usuwa klienta."""
        if not self._current_domain:
            return
        delete_client(self._current_domain)
        self._current_domain = None
        self.refresh_list()
        self._clear_form()

    def _clear_form(self):
        """Czyści formularz."""
        self._form_title.configure(
            text="Wybierz klienta z listy", text_color="gray50"
        )
        for textbox in self._entries.values():
            textbox.configure(state="normal")
            textbox.delete("1.0", "end")
            textbox.configure(state="disabled")
        self._links_textbox.configure(state="normal")
        self._links_textbox.delete("1.0", "end")
        self._links_textbox.configure(state="disabled")
        self._save_btn.configure(state="disabled")
        self._delete_btn.configure(state="disabled")
        self._status_label.configure(text="")

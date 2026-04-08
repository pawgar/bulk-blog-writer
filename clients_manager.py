"""Zarządzanie kartami klientów — profil per domena."""

import json
from pathlib import Path

CLIENTS_PATH = Path(__file__).parent / "clients.json"

# Pola karty klienta
CLIENT_FIELDS = {
    "industry": "Branża / kategoria",
    "description": "Krótki opis firmy",
    "tone": "Ton komunikacji",
    "audience": "Grupa docelowa",
    "usp": "Wyróżniki / USP",
    "avoid": "Czego unikać",
}


def load_clients() -> dict[str, dict]:
    """Wczytuje karty klientów z pliku JSON."""
    if not CLIENTS_PATH.exists():
        return {}
    try:
        with open(CLIENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_clients(clients: dict[str, dict]):
    """Zapisuje karty klientów do pliku JSON."""
    with open(CLIENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(clients, f, indent=2, ensure_ascii=False)


def get_client(domain: str) -> dict | None:
    """Zwraca kartę klienta dla domeny lub None."""
    if not domain:
        return None
    clients = load_clients()
    # Dokładne dopasowanie
    if domain in clients:
        return clients[domain]
    # Dopasowanie bez www.
    bare = domain.removeprefix("www.")
    if bare in clients:
        return clients[bare]
    return None


def save_client(domain: str, data: dict):
    """Zapisuje/aktualizuje kartę klienta."""
    clients = load_clients()
    clients[domain] = data
    save_clients(clients)


def delete_client(domain: str):
    """Usuwa kartę klienta."""
    clients = load_clients()
    clients.pop(domain, None)
    save_clients(clients)


def build_client_context(domain: str) -> str:
    """Buduje blok kontekstu klienta do wstrzyknięcia w prompt.
    Zwraca pusty string gdy brak karty klienta.
    """
    client = get_client(domain)
    if not client:
        return ""

    lines = [f"\n**Kontekst klienta dla {domain}:**"]
    field_labels = {
        "industry": "Branża",
        "description": "O firmie",
        "tone": "Ton komunikacji",
        "audience": "Grupa docelowa",
        "usp": "Wyróżniki",
        "avoid": "Czego unikać",
    }
    for key, label in field_labels.items():
        value = client.get(key, "").strip()
        if value:
            lines.append(f"- {label}: {value}")

    if len(lines) == 1:
        return ""  # Pusta karta
    return "\n".join(lines)

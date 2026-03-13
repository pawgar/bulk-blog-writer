# Bulk Blog Writer

Lokalna aplikacja desktopowa (Python + CustomTkinter) do masowego generowania artykułów blogowych SEO przez Anthropic Claude API.

Czyta content plan z pliku XLSX, generuje każdy artykuł jako osobny API request (czysty kontekst, zero degradacji jakości) i zapisuje wyniki jako pliki `.md`.

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

## Funkcje

- **Masowe generowanie** — wczytaj XLSX z content planem, zaznacz artykuły, kliknij generuj
- **Każdy artykuł = osobny request** — zero kontekstu z poprzednich artykułów, stała jakość
- **7 języków** — PL, DE, NL, ES, SV, CS, EN
- **Tryb zapleczowy** — artykuły bez kontekstu konkretnej domeny
- **Wiele domen w jednym planie** — pliki grupowane w podkatalogi per domena
- **Progress tracking** — progress bar, czas trwania, szacowany czas do końca
- **Retry logic** — automatyczny retry przy timeout/429/5xx
- **Historia generowania** — log wszystkich sesji w JSON
- **Dark mode** — domyślny ciemny motyw

## Instalacja

```bash
git clone https://github.com/pawgar/bulk-blog-writer.git
cd bulk-blog-writer
pip install customtkinter anthropic openpyxl
```

## Konfiguracja

Skopiuj plik konfiguracyjny i uzupełnij API key:

```bash
cp config.example.json config.json
```

Albo ustaw API key bezpośrednio w zakładce **Ustawienia** w aplikacji.

## Uruchomienie

```bash
python main.py
```

## Format XLSX (content plan)

Aplikacja oczekuje pliku XLSX z kolumnami:

| Kolumna | Wymagana | Opis |
|---------|----------|------|
| Tytuł wpisu | ✅ Tak | Tytuł artykułu |
| Główne słowo kluczowe | Nie | Fraza do optymalizacji SEO |
| Słowa kluczowe poboczne | Nie | Dodatkowe frazy SEO |
| Dodatkowe informacje | Nie | Wskazówki dla AI |
| Domena | Nie | Domena docelowa per artykuł |

Mapowanie kolumn jest elastyczne — rozpoznaje polskie i angielskie nazwy nagłówków.

## Interfejs

Aplikacja ma trzy zakładki:

### Generuj
- Wczytaj plik XLSX z content planem
- Ustaw domenę docelową i język
- Zaznacz artykuły do wygenerowania (zaznacz/odznacz wszystkie)
- Kliknij "Generuj zaznaczone"
- Statusy: Oczekuje → Generowanie → Gotowy (zielony/pomarańczowy) / Błąd

### Historia
- Przeglądaj poprzednie sesje generowania
- Statystyki: ile artykułów, ile błędów, czas generowania

### Ustawienia
- Anthropic API Key
- Model (claude-opus-4-6 / claude-sonnet-4-6)
- Domyślny katalog wyjściowy i język
- Opóźnienie między requestami (1-30s)
- Test połączenia z API

## Struktura plików wyjściowych

Jedna domena:
```
output/2026-03-13_143022/
├── 001-panele-fotowoltaiczne-na-dom.md
├── 002-fotowoltaika-pompa-ciepla.md
└── 003-koszt-fotowoltaiki-2026.md
```

Wiele domen:
```
output/2026-03-13_143022/
├── solarexpert-pl/
│   ├── 001-solarexpert-pl-panele-fotowoltaiczne.md
│   └── 002-solarexpert-pl-fotowoltaika-pompa-ciepla.md
├── peptides24-nl/
│   └── 003-peptides24-nl-semaglutide-afvallen.md
└── _bez-domeny/
    └── 004-jak-czytac-rachunek.md
```

## Katalog skill/

Katalog `skill/` zawiera system prompt dla Claude API:

- **SKILL-api.md** — zoptymalizowana wersja prompta SEO blog writer pod tryb batch
- **banned-ai-patterns.md** — listy zakazanych fraz AI w 7 językach

Możesz edytować te pliki, aby dostosować styl i zasady generowania artykułów.

## Wymagania

- Python 3.10+
- Klucz API Anthropic (claude-opus-4-6 lub claude-sonnet-4-6)

## Licencja

MIT

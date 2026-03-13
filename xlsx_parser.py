"""Parsowanie content planu z pliku XLSX."""

import openpyxl


def parse_content_plan(filepath: str) -> list[dict]:
    """Parsuje XLSX z content-plan-creator. Zwraca listę dict z artykułami."""
    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active
    headers = [str(c.value or "").strip().lower() for c in ws[1]]

    # Elastyczne mapowanie kolumn
    col_map = {}
    for i, h in enumerate(headers):
        if any(k in h for k in ["tytuł", "title", "tytul"]):
            col_map["title"] = i
        elif any(k in h for k in ["główne", "glowne", "main"]) and any(
            k in h for k in ["słowo", "slowo", "keyword"]
        ):
            col_map["main_kw"] = i
        elif any(k in h for k in ["poboczne", "secondary", "supporting"]):
            col_map["secondary_kw"] = i
        elif any(k in h for k in ["dodatkowe", "additional", "info", "uwagi"]):
            col_map["notes"] = i
        elif any(k in h for k in ["domena", "domain"]):
            col_map["domain"] = i

    if "title" not in col_map:
        wb.close()
        raise ValueError(
            "Nie znaleziono kolumny z tytułem wpisu. "
            "Oczekiwane nazwy: 'Tytuł wpisu', 'Title'."
        )

    articles = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if col_map["title"] >= len(row):
            continue
        title = str(row[col_map["title"]] or "").strip()
        if not title:
            continue

        def _get(key: str) -> str:
            idx = col_map.get(key)
            if idx is None or idx >= len(row):
                return ""
            return str(row[idx] or "").strip()

        articles.append(
            {
                "title": title,
                "main_kw": _get("main_kw"),
                "secondary_kw": _get("secondary_kw"),
                "notes": _get("notes"),
                "domain": _get("domain"),
            }
        )

    wb.close()
    return articles

"""Wrapper na Anthropic API — generowanie artykułu blogowego."""

import time
import anthropic
from system_prompt import load_system_prompt

# System prompt ładowany raz przy imporcie modułu
SYSTEM_PROMPT = load_system_prompt()

LANG_NAMES = {
    "pl": "polski",
    "de": "niemiecki",
    "nl": "holenderski",
    "es": "hiszpański",
    "sv": "szwedzki",
    "cs": "czeski",
    "en": "angielski",
}


def build_user_prompt(
    article: dict, global_domain: str, lang: str, is_zaplecze: bool
) -> str:
    """Buduje user prompt dla pojedynczego artykułu."""
    # Domena z XLSX ma priorytet, potem globalna z UI
    domain = article.get("domain") or global_domain

    parts = [
        f"Napisz artykuł blogowy w języku {LANG_NAMES.get(lang, lang)}.",
        f"**Tytuł (propozycja):** {article['title']}",
    ]

    # Słowa kluczowe — opcjonalne
    if article.get("main_kw"):
        parts.append(f"**Główne słowo kluczowe:** {article['main_kw']}")
    if article.get("secondary_kw"):
        parts.append(f"**Słowa kluczowe poboczne:** {article['secondary_kw']}")

    if not article.get("main_kw") and not article.get("secondary_kw"):
        parts.append(
            "\nBrak słów kluczowych — pisz artykuł bez optymalizacji pod konkretne "
            "frazy SEO. Skup się na jakości merytorycznej, E-E-A-T i naturalności "
            "tekstu. Zasady strukturalne (H2/H3/listy/długość) obowiązują bez zmian."
        )

    if article.get("notes"):
        parts.append(f"**Dodatkowe wskazówki:** {article['notes']}")

    if is_zaplecze:
        parts.append("\nArtykuł ZAPLECZOWY — bez kontekstu konkretnego serwisu.")
    elif domain:
        parts.append(f"\n**Domena docelowa:** {domain}")

    parts.append(
        "\n8500-9500 znaków ze spacjami. Format Markdown. BEZ linków wewnętrznych. "
        "BEZ meta description."
    )

    return "\n".join(parts)


def generate_article(
    client: anthropic.Anthropic,
    article: dict,
    domain: str,
    lang: str,
    is_zaplecze: bool,
    model: str,
) -> str:
    """Generuje pojedynczy artykuł przez Anthropic API. Zwraca tekst Markdown."""
    user_prompt = build_user_prompt(article, domain, lang, is_zaplecze)

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        timeout=120.0,
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text
    return text


def generate_article_with_retry(
    client: anthropic.Anthropic,
    article: dict,
    domain: str,
    lang: str,
    is_zaplecze: bool,
    model: str,
    max_retries: int = 1,
) -> str:
    """Generuje artykuł z retry logic (1 retry po 5s przy timeout/5xx/429)."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return generate_article(client, article, domain, lang, is_zaplecze, model)
        except anthropic.AuthenticationError:
            # Nie retryujemy przy złym API key
            raise
        except (
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
        ) as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(5)
            else:
                raise
        except anthropic.APIStatusError as e:
            if e.status_code in (429, 500, 502, 503, 504):
                last_error = e
                if attempt < max_retries:
                    time.sleep(5)
                else:
                    raise
            else:
                raise
    raise last_error

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
    "lt": "litewski",
    "lv": "łotewski",
}


def build_user_prompt(
    article: dict, global_domain: str, lang: str, is_zaplecze: bool
) -> str:
    """Buduje user prompt dla pojedynczego artykułu."""
    # Domena z XLSX ma priorytet, potem globalna z UI
    domain = article.get("domain") or global_domain

    parts = [
        f"Napisz artykuł blogowy w języku {LANG_NAMES.get(lang, lang)}.",
        f"**Tytuł (DOKŁADNY, nie zmieniaj ani jednego słowa):** {article['title']}",
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
        "\n\nKRYTYCZNE ZASADY:"
        "\n1. Tytuł artykułu (H1) MUSI być DOKŁADNIE taki jak podany powyżej — nie zmieniaj ani jednego słowa, nie dodawaj, nie usuwaj, nie przeformułowuj."
        "\n2. ZAKAZ pogrubiania nagłówków — nagłówki H1/H2/H3 używają TYLKO składni Markdown (# ## ###), NIGDY nie dodawaj **pogrubienia** wewnątrz nagłówków. Przykład poprawny: `## Jak działa fotowoltaika`. Przykład BŁĘDNY: `## **Jak działa fotowoltaika**`."
    )

    return "\n".join(parts)


def estimate_session_cost(article_count: int) -> dict:
    """Szacuje koszt sesji przed uruchomieniem dla obu modeli."""
    # Szacunkowe tokeny: system prompt (~7000) + avg user prompt (~250) + avg output (~3200)
    system_tokens = len(SYSTEM_PROMPT) // 4
    avg_user_tokens = 250
    avg_output_tokens = 3200

    pricing = {
        "claude-opus-4-6": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    }

    result = {}
    for model_name, prices in pricing.items():
        input_per_art = system_tokens + avg_user_tokens
        output_per_art = avg_output_tokens
        cost_per_art = (
            input_per_art / 1_000_000 * prices["input"]
            + output_per_art / 1_000_000 * prices["output"]
        )
        result[model_name] = {
            "cost_per_article": cost_per_art,
            "total_cost": cost_per_art * article_count,
            "input_tokens_per_article": input_per_art,
            "output_tokens_per_article": output_per_art,
        }
    return result


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Oblicza koszt w USD na podstawie tokenów i modelu."""
    # Cennik Anthropic (USD per 1M tokenów)
    pricing = {
        "claude-opus-4-6": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    }
    prices = pricing.get(model, pricing["claude-sonnet-4-6"])
    cost = (input_tokens / 1_000_000 * prices["input"]) + (
        output_tokens / 1_000_000 * prices["output"]
    )
    return cost


def generate_article(
    client: anthropic.Anthropic,
    article: dict,
    domain: str,
    lang: str,
    is_zaplecze: bool,
    model: str,
) -> dict:
    """Generuje pojedynczy artykuł przez Anthropic API. Zwraca dict z tekstem i usage."""
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

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = calculate_cost(input_tokens, output_tokens, model)

    return {
        "text": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
    }


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
            result = generate_article(client, article, domain, lang, is_zaplecze, model)
            return result
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
            if e.status_code in (429, 500, 502, 503, 504, 529):
                last_error = e
                if attempt < max_retries:
                    time.sleep(5)
                else:
                    raise
            else:
                raise
    raise last_error

"""Ładuje system prompt z plików skill/ — wersja API."""

from pathlib import Path


def load_system_prompt() -> str:
    """Ładuje system prompt z plików skill/ — wersja API okrojona z zbędnych sekcji."""
    skill_dir = Path(__file__).parent / "skill"

    skill_md = (skill_dir / "SKILL-api.md").read_text(encoding="utf-8")
    banned_patterns = (skill_dir / "banned-ai-patterns.md").read_text(encoding="utf-8")

    return f"{skill_md}\n\n---\n\n{banned_patterns}"

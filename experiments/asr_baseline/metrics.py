import re
import unicodedata
from collections.abc import Sequence


def normalize_text(text: str) -> str:
    """Normaliza caixa, pontuacao e espacos sem remover acentos."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in normalized
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _edit_distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for reference_index, reference_item in enumerate(reference, start=1):
        current = [reference_index]
        for hypothesis_index, hypothesis_item in enumerate(hypothesis, start=1):
            substitution_cost = 0 if reference_item == hypothesis_item else 1
            current.append(
                min(
                    previous[hypothesis_index] + 1,
                    current[hypothesis_index - 1] + 1,
                    previous[hypothesis_index - 1] + substitution_cost,
                )
            )
        previous = current
    return previous[-1]


def word_error_rate(reference: str, hypothesis: str) -> float | None:
    """Calcula WER; retorna None quando nao existe referencia avaliavel."""
    reference_words = normalize_text(reference).split()
    if not reference_words:
        return None
    hypothesis_words = normalize_text(hypothesis).split()
    return _edit_distance(reference_words, hypothesis_words) / len(reference_words)


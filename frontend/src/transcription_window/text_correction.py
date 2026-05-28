from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from symspellpy import SymSpell, Verbosity
except Exception:  # pragma: no cover - fallback when symspellpy is missing
    SymSpell = None
    Verbosity = None


class SymSpellCorrector:
    """Corretor leve baseado em SymSpell."""

    def __init__(
        self,
        dictionary_path: Optional[str] = None,
        max_edit_distance: int = 2,
        prefix_length: int = 7,
    ):
        self._ready = False
        self._symspell = None
        self._max_edit_distance = max_edit_distance
        self._prefix_length = prefix_length

        if SymSpell is None:
            return

        dictionary = dictionary_path or str(self._default_dictionary_path())
        if not dictionary or not Path(dictionary).exists():
            return

        symspell = SymSpell(max_edit_distance=self._max_edit_distance, prefix_length=self._prefix_length)
        loaded = symspell.load_dictionary(dictionary, term_index=0, count_index=1)
        if not loaded:
            return

        self._symspell = symspell
        self._ready = True

    @property
    def is_ready(self) -> bool:
        return self._ready

    def correct(self, text: str) -> str:
        if not self._ready or not text:
            return text

        suggestions = self._symspell.lookup_compound(
            text,
            max_edit_distance=self._max_edit_distance,
            suggestion_verbosity=Verbosity.TOP,
        )
        if not suggestions:
            return text

        return suggestions[0].term

    @staticmethod
    def _default_dictionary_path() -> Path:
        return Path(__file__).resolve().parents[3] / "resources" / "pt_word_freq.txt"

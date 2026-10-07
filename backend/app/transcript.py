from dataclasses import dataclass


DISPLAY_MODES = {"translation_only", "transcript_only", "both"}


@dataclass(frozen=True)
class TranscriptChunk:
    """Resultado de uma fala pronto para consumo pelas interfaces."""

    channel: str
    original_text: str
    translated_text: str
    display_mode: str = "translation_only"

    def __post_init__(self) -> None:
        if self.display_mode not in DISPLAY_MODES:
            raise ValueError(f"Modo de exibicao invalido: {self.display_mode}")

    def format_for_display(self) -> str:
        if self.display_mode == "transcript_only":
            return self.original_text
        if self.display_mode == "both":
            parts = [part for part in (self.original_text, self.translated_text) if part]
            return "\n".join(parts)
        return self.translated_text or self.original_text

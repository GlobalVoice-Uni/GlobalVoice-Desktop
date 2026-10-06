from typing import Optional, Protocol, Tuple

import numpy as np


class AudioSourcePort(Protocol):
    """Contrato comum para microfone e audio de saida do sistema."""

    step_duration_s: float
    target_sample_rate: int
    input_sample_rate: int
    display_name: str

    def __enter__(self):
        """Abre a fonte e retorna a propria instancia."""

    def __exit__(self, exc_type, exc, tb) -> None:
        """Fecha a fonte mesmo quando a sessao termina com erro."""

    def read_step(self, timeout_s: float = 2.0) -> Tuple[np.ndarray, float]:
        """Retorna um bloco mono em 16 kHz e seu pico de amplitude."""


class TranscriberPort(Protocol):
    """Contrato minimo para motores de transcricao.

    Mantendo este contrato estavel, podemos trocar implementacoes
    (local, HTTP, WebSocket) sem alterar a sessao realtime.
    """

    def transcribe(
        self,
        audio_16k: np.ndarray,
        language: str,
        context_prompt: Optional[str] = None,
    ) -> str:
        """Transcreve um enunciado de audio em 16 kHz.

        Args:
            audio_16k: audio mono em 16 kHz.
            language: idioma usado pelo modelo (ex.: "pt" ou "en").
            context_prompt: texto de contexto opcional para estabilizar continuidade.
        """


class SpeechDetectorPort(Protocol):
    """Contrato de detector de fala para segmentacao em tempo real."""

    def reset(self) -> None:
        """Reseta estado interno entre sessoes."""

    def detect(self, audio_16k: np.ndarray, peak: float) -> bool:
        """Retorna True quando o bloco atual deve ser tratado como fala."""

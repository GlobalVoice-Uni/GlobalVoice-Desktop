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


class SpeechSynthesizerPort(Protocol):
    """Converte uma fala traduzida em áudio mono normalizado."""

    def synthesize(self, text: str, language: str) -> Tuple[np.ndarray, int]:
        """Retorna amostras float32 e frequência em Hz."""


class AudioSinkPort(Protocol):
    """Reproduz áudio em uma saída selecionada pelo usuário."""

    def play(self, audio: np.ndarray, sample_rate: int, stop_event) -> None:
        """Reproduz em blocos para permitir cancelamento entre blocos."""


class TranslatorPort(Protocol):
    """Contrato para tradução local ou remota de um trecho confirmado."""

    def ensure_available(
        self,
        source_language: str,
        target_language: str,
    ) -> None:
        """Valida o par antes de iniciar uma sessão."""

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        """Traduz texto entre dois códigos de idioma suportados."""


class SpeechDetectorPort(Protocol):
    """Contrato de detector de fala para segmentacao em tempo real."""

    def reset(self) -> None:
        """Reseta estado interno entre sessoes."""

    def detect(self, audio_16k: np.ndarray, peak: float) -> bool:
        """Retorna True quando o bloco atual deve ser tratado como fala."""

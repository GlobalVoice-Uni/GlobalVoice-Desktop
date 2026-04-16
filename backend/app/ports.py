from typing import Optional, Protocol

import numpy as np


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

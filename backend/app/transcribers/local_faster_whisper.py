from typing import Optional

import numpy as np
import torch
from faster_whisper import WhisperModel


class LocalFasterWhisperTranscriber:
    """Adapter local de transcricao baseado em Faster-Whisper."""

    def __init__(self, model_size: str = "small", device: str = "cpu"):
        # model_size e device sao expostos para facilitar tuning da aplicacao.
        self.model_size = model_size
        self.device_request = device
        self.device = self._resolve_device(device)
        self.model = self._load_model()

    def _resolve_device(self, requested: str) -> str:
        """Mapeia escolha da UI para device suportado pelo WhisperModel."""
        if requested == "gpu":
            if not torch.cuda.is_available():
                raise RuntimeError("GPU solicitada, mas CUDA nao esta disponivel.")
            return "cuda"
        return "cpu"

    def _load_model(self) -> WhisperModel:
        """Inicializa modelo com fallback de compute_type em GPU."""
        if self.device == "cuda":
            last_error = None
            for compute_type in ("float16", "int8_float16", "float32"):
                try:
                    return WhisperModel(
                        self.model_size,
                        device="cuda",
                        compute_type=compute_type,
                        num_workers=1,
                    )
                except Exception as exc:
                    last_error = exc
            raise RuntimeError("Nao foi possivel inicializar Faster-Whisper em GPU.") from last_error

        return WhisperModel(
            self.model_size,
            device="cpu",
            compute_type="int8",
            num_workers=1,
        )

    def transcribe(
        self,
        audio_16k: np.ndarray,
        language: str,
        context_prompt: Optional[str] = None,
    ) -> str:
        """Executa transcricao de um enunciado e retorna texto consolidado."""
        segments, _ = self.model.transcribe(
            audio_16k,
            language=language,
            beam_size=5,
            initial_prompt=context_prompt,
            condition_on_previous_text=False,
            no_speech_threshold=0.35,
            vad_filter=True,
            temperature=0.0,
        )

        return " ".join(s.text.strip() for s in segments if s.text.strip()).strip()

from typing import Optional

import ctranslate2
import numpy as np
from faster_whisper import WhisperModel


class LocalFasterWhisperTranscriber:
    """Adapter local de transcricao baseado em Faster-Whisper."""

    _GPU_COMPUTE_PREFERENCE = (
        "float16",
        "int8_float16",
        "float32",
        "int8",
        "int8_float32",
    )

    def __init__(self, model_size: str = "small", device: str = "auto"):
        # model_size e device sao expostos para facilitar tuning da aplicacao.
        self.model_size = model_size
        self.device_request = (device or "auto").strip().lower()
        self.device = "cpu"
        self.compute_type = "int8"
        self.fallback_message: Optional[str] = None
        self.model = self._load_model()

    def _supported_cuda_compute_types(self) -> tuple[str, ...]:
        """Consulta o runtime efetivamente usado pelo Faster-Whisper."""
        try:
            if ctranslate2.get_cuda_device_count() < 1:
                return ()
            supported = ctranslate2.get_supported_compute_types("cuda")
        except Exception:
            return ()

        return tuple(
            compute_type
            for compute_type in self._GPU_COMPUTE_PREFERENCE
            if compute_type in supported
        )

    def _load_cpu_model(self) -> WhisperModel:
        self.device = "cpu"
        self.compute_type = "int8"
        return WhisperModel(
            self.model_size,
            device="cpu",
            compute_type=self.compute_type,
            num_workers=1,
        )

    def _load_model(self) -> WhisperModel:
        """Usa GPU quando compativel e recua para CPU sem interromper a sessao."""
        if self.device_request != "cpu":
            compute_types = self._supported_cuda_compute_types()
            for compute_type in compute_types:
                try:
                    model = WhisperModel(
                        self.model_size,
                        device="cuda",
                        compute_type=compute_type,
                        num_workers=1,
                    )
                    self.device = "cuda"
                    self.compute_type = compute_type
                    return model
                except Exception:
                    continue

            if compute_types:
                self.fallback_message = (
                    "A aceleracao por GPU nao pode ser iniciada. Usando CPU automaticamente."
                )
            else:
                self.fallback_message = (
                    "Nenhuma GPU compativel foi encontrada. Usando CPU automaticamente."
                )

        return self._load_cpu_model()

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

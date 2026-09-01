from typing import Optional

import ctranslate2
import numpy as np
from faster_whisper import WhisperModel

from ..cuda_runtime import prepare_cuda_runtime
from ..runtime_status import (
    ActiveDevice,
    DevicePreference,
    FallbackReason,
    RuntimeProvider,
    RuntimeStatus,
)


class LocalFasterWhisperTranscriber:
    """Adapter local de transcricao baseado em Faster-Whisper."""

    _GPU_COMPUTE_PREFERENCE = (
        "float16",
        "int8_float16",
        "float32",
        "int8",
        "int8_float32",
    )

    def __init__(self, model_size: str = "small", device: str = "gpu"):
        # model_size e device sao expostos para facilitar tuning da aplicacao.
        self.model_size = model_size
        self.device_preference = DevicePreference.from_value(device)
        self.device_request = self.device_preference.value
        self.device = "cpu"
        self.compute_type = "int8"
        self.fallback_reason: Optional[FallbackReason] = None
        self.fallback_message: Optional[str] = None
        self.model = self._load_model()
        self.runtime_status = self._build_runtime_status()
        if self.runtime_status.is_fallback:
            self.fallback_message = self.runtime_status.user_message

    def _probe_cuda_compute_types(
        self,
    ) -> tuple[tuple[str, ...], Optional[FallbackReason]]:
        """Consulta o runtime efetivamente usado pelo Faster-Whisper."""
        try:
            if ctranslate2.get_cuda_device_count() < 1:
                return (), FallbackReason.ACCELERATOR_NOT_FOUND
            if not prepare_cuda_runtime().available:
                return (), FallbackReason.CUDA_LIBRARIES_MISSING
            supported = ctranslate2.get_supported_compute_types("cuda")
        except Exception:
            return (), FallbackReason.RUNTIME_UNAVAILABLE

        compute_types = tuple(
            compute_type
            for compute_type in self._GPU_COMPUTE_PREFERENCE
            if compute_type in supported
        )
        if not compute_types:
            return (), FallbackReason.RUNTIME_UNAVAILABLE
        return compute_types, None

    def _build_runtime_status(self) -> RuntimeStatus:
        active_device = ActiveDevice.GPU if self.device == "cuda" else ActiveDevice.CPU
        provider = RuntimeProvider.CUDA if active_device == ActiveDevice.GPU else RuntimeProvider.CPU
        return RuntimeStatus(
            preference=self.device_preference,
            active_device=active_device,
            engine="faster-whisper",
            provider=provider,
            compute_type=self.compute_type,
            fallback_reason=self.fallback_reason,
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
        if self.device_preference == DevicePreference.GPU:
            compute_types, probe_failure = self._probe_cuda_compute_types()
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
                self.fallback_reason = FallbackReason.INITIALIZATION_FAILED
            else:
                self.fallback_reason = probe_failure

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

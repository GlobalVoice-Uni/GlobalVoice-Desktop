"""Execucao do Silero VAD em streaming sem dependencia de PyTorch."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


FRAME_SAMPLES = 512
CONTEXT_SAMPLES = 64
SAMPLE_RATE = 16_000
MODEL_FILENAME = "silero_vad_16k_op15.onnx"


def _default_model_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "backend" / "assets" / MODEL_FILENAME
    return Path(__file__).resolve().parents[2] / "assets" / MODEL_FILENAME


@dataclass(frozen=True)
class VadFrameResult:
    probability: float
    active: bool
    event: Optional[dict[str, int]]


class SileroOnnxStreamingModel:
    """Mantem o estado recorrente do Silero v6 entre quadros de 32 ms."""

    def __init__(
        self,
        threshold: float = 0.5,
        min_silence_duration_ms: int = 120,
        speech_pad_ms: int = 30,
        model_path: Optional[str | Path] = None,
    ) -> None:
        import onnxruntime

        resolved_model = Path(model_path or _default_model_path()).resolve()
        if not resolved_model.is_file():
            raise FileNotFoundError(f"Modelo Silero ONNX nao encontrado: {resolved_model}")

        options = onnxruntime.SessionOptions()
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.log_severity_level = 4

        self._session = onnxruntime.InferenceSession(
            str(resolved_model),
            providers=["CPUExecutionProvider"],
            sess_options=options,
        )
        input_names = {item.name for item in self._session.get_inputs()}
        if {"input", "h", "c"}.issubset(input_names):
            self._model_format = "separate_lstm_state"
        elif {"input", "state", "sr"}.issubset(input_names):
            self._model_format = "combined_state"
        else:
            raise RuntimeError(
                "Formato ONNX do Silero nao reconhecido: "
                + ", ".join(sorted(input_names))
            )

        self.threshold = threshold
        self.min_silence_samples = SAMPLE_RATE * min_silence_duration_ms / 1000
        self.speech_pad_samples = SAMPLE_RATE * speech_pad_ms / 1000
        self.reset()

    def reset(self) -> None:
        self._hidden = np.zeros((1, 1, 128), dtype=np.float32)
        self._cell = np.zeros((1, 1, 128), dtype=np.float32)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, CONTEXT_SAMPLES), dtype=np.float32)
        self._triggered = False
        self._temporary_end = 0
        self._current_sample = 0

    def process(self, audio: np.ndarray) -> VadFrameResult:
        frame = np.asarray(audio, dtype=np.float32).reshape(-1)
        if frame.size != FRAME_SAMPLES:
            raise ValueError(
                f"O Silero ONNX requer exatamente {FRAME_SAMPLES} amostras por quadro."
            )

        model_input = np.concatenate((self._context, frame.reshape(1, -1)), axis=1)
        if self._model_format == "separate_lstm_state":
            output, self._hidden, self._cell = self._session.run(
                None,
                {
                    "input": model_input,
                    "h": self._hidden,
                    "c": self._cell,
                },
            )
        else:
            output, self._state = self._session.run(
                None,
                {
                    "input": model_input,
                    "state": self._state,
                    "sr": np.asarray(SAMPLE_RATE, dtype=np.int64),
                },
            )
        self._context = model_input[:, -CONTEXT_SAMPLES:]
        probability = float(np.asarray(output).reshape(-1)[0])
        event = self._advance_state(probability)
        return VadFrameResult(
            probability=probability,
            active=self._triggered,
            event=event,
        )

    def _advance_state(self, probability: float) -> Optional[dict[str, int]]:
        self._current_sample += FRAME_SAMPLES

        if probability >= self.threshold and self._temporary_end:
            self._temporary_end = 0

        if probability >= self.threshold and not self._triggered:
            self._triggered = True
            speech_start = max(
                0,
                self._current_sample - self.speech_pad_samples - FRAME_SAMPLES,
            )
            return {"start": int(speech_start)}

        if probability < self.threshold - 0.15 and self._triggered:
            if not self._temporary_end:
                self._temporary_end = self._current_sample
            if self._current_sample - self._temporary_end < self.min_silence_samples:
                return None

            speech_end = (
                self._temporary_end + self.speech_pad_samples - FRAME_SAMPLES
            )
            self._temporary_end = 0
            self._triggered = False
            return {"end": int(speech_end)}

        return None

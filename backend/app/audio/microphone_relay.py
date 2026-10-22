"""Encaminha o microfone ao cabo virtual sem esperar STT ou tradução."""

from __future__ import annotations

from collections import deque
from math import gcd
import threading
from typing import Callable

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly


class MicrophoneRelay:
    """Fila curta entre callbacks de captura e reprodução do PortAudio."""

    def __init__(
        self,
        output_device_id: str,
        enabled: Callable[[], bool],
        sounddevice_module=sd,
        max_buffer_ms: float = 20.0,
    ) -> None:
        self.output_device_id = int(output_device_id)
        self.enabled = enabled
        self._sd = sounddevice_module
        self._max_buffer_ms = max_buffer_ms
        self._lock = threading.Lock()
        self._blocks: deque[np.ndarray] = deque()
        self._queued_samples = 0
        self._sample_rate = 0
        self._input_sample_rate = 0
        self._stream = None
        self.underflow_callbacks = 0

    @property
    def output_latency_s(self) -> float | None:
        if self._stream is None:
            return None
        return float(self._stream.latency)

    def start(self, input_sample_rate: int) -> None:
        device = self._sd.query_devices(self.output_device_id, kind="output")
        self._sample_rate = int(device["default_samplerate"])
        self._input_sample_rate = int(input_sample_rate)
        if self._sample_rate <= 0 or self._input_sample_rate <= 0:
            raise ValueError("Frequência de áudio inválida para o cabo virtual.")
        self._stream = self._sd.OutputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            latency="low",
            blocksize=0,
            device=self.output_device_id,
            callback=self._output_callback,
        )
        try:
            self._stream.start()
        except Exception:
            self._stream.close()
            self._stream = None
            raise

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        with self._lock:
            self._blocks.clear()
            self._queued_samples = 0

    def push(self, audio: np.ndarray) -> None:
        if not self.enabled():
            with self._lock:
                self._blocks.clear()
                self._queued_samples = 0
            return
        block = np.asarray(audio, dtype=np.float32).reshape(-1)
        if self._input_sample_rate != self._sample_rate:
            divisor = gcd(self._input_sample_rate, self._sample_rate)
            block = resample_poly(
                block,
                self._sample_rate // divisor,
                self._input_sample_rate // divisor,
            ).astype(np.float32)
        else:
            block = block.copy()
        max_samples = max(1, int(self._sample_rate * self._max_buffer_ms / 1000))
        with self._lock:
            self._blocks.append(block)
            self._queued_samples += len(block)
            while self._queued_samples > max_samples and self._blocks:
                excess = self._queued_samples - max_samples
                oldest = self._blocks[0]
                if len(oldest) <= excess:
                    self._queued_samples -= len(self._blocks.popleft())
                else:
                    self._blocks[0] = oldest[excess:]
                    self._queued_samples -= excess

    def _output_callback(self, outdata, frames, time_info, status) -> None:
        del time_info, status
        outdata.fill(0)
        if not self.enabled():
            with self._lock:
                self._blocks.clear()
                self._queued_samples = 0
            return
        filled = 0
        with self._lock:
            while filled < frames and self._blocks:
                oldest = self._blocks[0]
                count = min(frames - filled, len(oldest))
                outdata[filled : filled + count, 0] = oldest[:count]
                filled += count
                self._queued_samples -= count
                if count == len(oldest):
                    self._blocks.popleft()
                else:
                    self._blocks[0] = oldest[count:]
        if filled < frames:
            self.underflow_callbacks += 1

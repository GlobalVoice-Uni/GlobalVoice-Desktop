import re
import time
from collections import deque
from typing import Callable, Optional

import numpy as np

from ..audio.audio_capture import MicrophoneAudioSource
from ..ports import SpeechDetectorPort, TranscriberPort
from ..detectors.speech_detectors import EnergySpeechDetector


class RealtimeTranscriptionSession:
    """Orquestra captura, segmentacao por fala/silencio e commit de texto.

    A sessao recebe blocos do microfone, fecha enunciados por detector de fala,
    chama o transcritor e publica somente texto novo para evitar repeticao.
    """

    def __init__(
        self,
        audio_source: MicrophoneAudioSource,
        transcriber: TranscriberPort,
        speech_detector: Optional[SpeechDetectorPort] = None,
        language: str = "pt-br",
        context_window: int = 0,
        speech_peak_threshold: float = 0.0018,
        max_silence_inside_utterance_s: float = 0.4,
        min_speech_window_s: float = 0.2,
        min_silence_window_s: Optional[float] = None,
        max_utterance_s: float = 3.2,
        min_utterance_s: float = 0.7,
        boundary_overlap_s: float = 0.45,
        tail_guard_words: int = 4,
        forced_split_policy: str = "protect_boundary",
        forced_split_extra_tail_words: int = 1,
    ):
        # Dependencias injetadas para facilitar troca de implementacao no futuro.
        self.audio_source = audio_source
        self.transcriber = transcriber
        self.speech_detector = speech_detector
        self.language = "pt" if language == "pt-br" else language
        self.context_window = max(0, context_window)

        # Parametros de segmentacao e protecao de fronteira entre blocos.
        self.speech_peak_threshold = speech_peak_threshold
        self.max_silence_inside_utterance_s = max_silence_inside_utterance_s
        self.min_speech_window_s = max(0.0, min_speech_window_s)
        self.min_silence_window_s = max(
            0.05,
            (
                min_silence_window_s
                if min_silence_window_s is not None
                else max_silence_inside_utterance_s
            ),
        )
        self.max_utterance_s = max_utterance_s
        self.min_utterance_s = min_utterance_s
        self.boundary_overlap_s = boundary_overlap_s
        self.tail_guard_words = max(0, tail_guard_words)
        self.forced_split_policy = (forced_split_policy or "protect_boundary").strip().lower()
        self.forced_split_extra_tail_words = max(0, forced_split_extra_tail_words)

        self._stop_requested = False
        self._live_words = deque(maxlen=1400)
        self._context_words = deque(maxlen=self.context_window)
        self._full_parts = []
        self._pending_tail_words = []
        self._pending_tail_overlap_limit = self.tail_guard_words
        self._min_overlap_words_for_dedupe = 2

    def stop(self) -> None:
        """Solicita parada assicrona da sessao em execucao."""
        self._stop_requested = True

    def get_full_transcript(self) -> str:
        """Retorna o texto final acumulado na sessao."""
        return " ".join(self._full_parts).strip()

    def run(
        self,
        on_text: Callable[[str], None],
        on_status: Optional[Callable[[str], None]] = None,
        max_duration_s: Optional[float] = None,
    ) -> str:
        """Executa o loop realtime e envia cada trecho confirmado via callback.

        Args:
            on_text: callback chamado com novos trechos confirmados.
            on_status: callback opcional para mensagens de estado.
            max_duration_s: limite opcional de duracao; None = continuo ate stop().
        """
        self._reset_state()
        self._stop_requested = False

        detector: SpeechDetectorPort = self.speech_detector or EnergySpeechDetector(
            peak_threshold=self.speech_peak_threshold
        )
        detector.reset()

        speech_active = False
        speech_buffers = []
        speech_candidate_buffers = []
        speech_candidate_steps = 0
        silence_steps = 0
        idle_silence_steps = 0
        carryover_audio = np.zeros(0, dtype=np.float32)

        if on_status:
            on_status("Inicializando captura de audio...")

        started_at = time.time()

        with self.audio_source:
            min_speech_steps = max(
                1,
                int(np.ceil(self.min_speech_window_s / self.audio_source.step_duration_s)),
            )
            min_silence_steps = max(
                1,
                int(np.ceil(self.min_silence_window_s / self.audio_source.step_duration_s)),
            )
            max_utt_samples = int(self.max_utterance_s * self.audio_source.target_sample_rate)
            min_utt_samples = int(self.min_utterance_s * self.audio_source.target_sample_rate)
            overlap_samples = int(self.boundary_overlap_s * self.audio_source.target_sample_rate)

            if on_status:
                on_status(
                    "Microfone ativo em "
                    f"{self.audio_source.input_sample_rate} Hz (ASR: {self.audio_source.target_sample_rate} Hz)."
                )

            while not self._stop_requested:
                if max_duration_s is not None and (time.time() - started_at) >= max_duration_s:
                    break

                audio, peak = self.audio_source.read_step()
                has_speech = detector.detect(audio, peak)

                if speech_active:
                    idle_silence_steps = 0
                    speech_buffers.append(audio)
                    if has_speech:
                        silence_steps = 0
                    else:
                        silence_steps += 1
                else:
                    if has_speech:
                        idle_silence_steps = 0
                        speech_candidate_buffers.append(audio)
                        speech_candidate_steps += 1
                        if speech_candidate_steps >= min_speech_steps:
                            speech_buffers = [carryover_audio] if len(carryover_audio) > 0 else []
                            speech_buffers.extend(speech_candidate_buffers)
                            carryover_audio = np.zeros(0, dtype=np.float32)

                            speech_active = True
                            silence_steps = 0
                            speech_candidate_buffers = []
                            speech_candidate_steps = 0
                    else:
                        idle_silence_steps += 1
                        speech_candidate_buffers = []
                        speech_candidate_steps = 0

                    if (
                        self._pending_tail_words
                        and idle_silence_steps >= min_silence_steps
                    ):
                        # Se houve pausa real apos corte forcado, publica a cauda sem esperar nova fala.
                        self._flush_pending_tail(on_text)
                        idle_silence_steps = 0

                utter_len = sum(len(x) for x in speech_buffers) if speech_buffers else 0
                natural_split = speech_active and silence_steps >= min_silence_steps
                forced_by_time = speech_active and utter_len >= max_utt_samples
                should_finalize = natural_split or forced_by_time

                if should_finalize:
                    # forced_split e usado somente quando tempo maximo estoura sem pausa natural.
                    forced_split = forced_by_time and not natural_split
                    apply_boundary_protection = forced_split and self._should_protect_forced_split_boundary()

                    utter = np.concatenate(speech_buffers).astype(np.float32)
                    speech_active = False
                    speech_buffers = []
                    silence_steps = 0

                    if apply_boundary_protection and overlap_samples > 0 and len(utter) > overlap_samples:
                        # Sobreposicao apenas em corte forcado para salvar fronteira de palavra.
                        carryover_audio = utter[-overlap_samples:].copy()
                    else:
                        carryover_audio = np.zeros(0, dtype=np.float32)

                    self._process_utterance(
                        utter=utter,
                        min_utt_samples=min_utt_samples,
                        forced_split=apply_boundary_protection,
                        on_text=on_text,
                    )

        remaining_buffers = speech_buffers if speech_buffers else speech_candidate_buffers
        if remaining_buffers:
            utter = np.concatenate(remaining_buffers).astype(np.float32)
            self._process_utterance(
                utter=utter,
                min_utt_samples=int(self.min_utterance_s * self.audio_source.target_sample_rate),
                forced_split=False,
                on_text=on_text,
            )

        if self._pending_tail_words:
            # Esvazia palavras protegidas no final para nao perder texto util.
            self._flush_pending_tail(on_text)

        return self.get_full_transcript()

    def _reset_state(self) -> None:
        """Limpa buffers internos antes de iniciar uma nova sessao."""
        self._live_words.clear()
        self._context_words = deque(maxlen=self.context_window)
        self._full_parts = []
        self._pending_tail_words = []
        self._pending_tail_overlap_limit = self.tail_guard_words

    def _should_protect_forced_split_boundary(self) -> bool:
        """Define se corte forcado aplica overlap + tail guard."""
        return self.forced_split_policy not in {"hard_cut", "none", "disabled"}

    def _process_utterance(
        self,
        utter: np.ndarray,
        min_utt_samples: int,
        forced_split: bool,
        on_text: Callable[[str], None],
    ) -> None:
        """Transcreve um enunciado completo e aplica regras de commit."""
        if len(utter) < min_utt_samples:
            return

        context_prompt = " ".join(self._context_words) if self._context_words else None
        text = self.transcriber.transcribe(
            utter,
            language=self.language,
            context_prompt=context_prompt,
        )
        if text:
            self._commit_transcribed_text(text, forced_split=forced_split, on_text=on_text)

    def _flush_pending_tail(self, on_text: Callable[[str], None]) -> None:
        """Publica cauda pendente quando nao ha nova fala para reconciliação."""
        if not self._pending_tail_words:
            return

        tail_new_words = self._extract_new_suffix(" ".join(self._pending_tail_words))
        self._append_words(tail_new_words, on_text)
        self._pending_tail_words = []
        self._pending_tail_overlap_limit = self.tail_guard_words

    def _extract_new_suffix(self, candidate_text: str):
        """Extrai apenas o sufixo novo comparando com historico ja emitido."""
        words = [w for w in candidate_text.split() if w.strip()]
        if not words:
            return []

        def _norm(token: str) -> str:
            return re.sub(r"[^\w]", "", token.lower())

        history = list(self._live_words)
        max_overlap = min(len(history), len(words), 30)
        overlap = 0

        for k in range(max_overlap, 0, -1):
            if k < self._min_overlap_words_for_dedupe:
                continue
            if [_norm(w) for w in history[-k:]] == [_norm(w) for w in words[:k]]:
                overlap = k
                break

        return words[overlap:]

    def _looks_like_loop(self, words) -> bool:
        """Heuristica simples para bloquear repeticoes patalogicas."""
        if len(words) < 28:
            return False

        lower_words = [w.lower() for w in words]
        uniq_ratio = len(set(lower_words)) / len(lower_words)
        if uniq_ratio < 0.20:
            return True

        bigrams = [f"{lower_words[i]} {lower_words[i + 1]}" for i in range(len(lower_words) - 1)]
        counts = {}
        for bg in bigrams:
            counts[bg] = counts.get(bg, 0) + 1

        return max(counts.values()) >= 10 if counts else False

    def _append_words(self, new_words, on_text: Callable[[str], None]) -> None:
        """Anexa palavras novas ao texto final e notifica callback da UI."""
        if not new_words or self._looks_like_loop(new_words):
            return

        text = " ".join(new_words)

        self._full_parts.append(text)

        for w in new_words:
            self._live_words.append(w)
            clean = w.rstrip(".,!?;:")
            if clean:
                self._context_words.append(clean)

        on_text(text)

    def _merge_with_pending_tail(self, words):
        """Reconcilia palavras de cauda entre quebras forcadas consecutivas."""
        if not self._pending_tail_words:
            return words

        def _norm(token: str) -> str:
            return re.sub(r"[^\w]", "", token.lower())

        pending = self._pending_tail_words
        max_overlap = min(len(pending), len(words), self._pending_tail_overlap_limit)
        overlap = 0

        for k in range(max_overlap, 0, -1):
            if [_norm(w) for w in pending[-k:]] == [_norm(w) for w in words[:k]]:
                overlap = k
                break

        merged = pending + words[overlap:]
        self._pending_tail_words = []
        self._pending_tail_overlap_limit = self.tail_guard_words
        return merged

    def _commit_transcribed_text(self, text: str, forced_split: bool, on_text: Callable[[str], None]) -> None:
        """Aplica dedupe e tail guard antes de publicar texto."""
        words = [w for w in text.split() if w.strip()]
        if not words:
            return

        words = self._merge_with_pending_tail(words)

        if forced_split:
            guard_words = self.tail_guard_words + self.forced_split_extra_tail_words
            if guard_words <= 0:
                commit_words = words
                self._pending_tail_words = []
                self._pending_tail_overlap_limit = self.tail_guard_words
            else:
                # Segura as ultimas palavras para confirmar na proxima janela.
                if len(words) <= guard_words:
                    self._pending_tail_words = words
                    self._pending_tail_overlap_limit = guard_words
                    return
                commit_words = words[:-guard_words]
                self._pending_tail_words = words[-guard_words:]
                self._pending_tail_overlap_limit = guard_words
        else:
            commit_words = words

        if commit_words:
            new_words = self._extract_new_suffix(" ".join(commit_words))
            self._append_words(new_words, on_text)

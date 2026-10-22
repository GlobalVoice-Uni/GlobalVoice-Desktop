import re
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from ..ports import AudioSourcePort, SpeechDetectorPort, TranscriberPort
from ..detectors.speech_detectors import EnergySpeechDetector


_RAMP_START_UTTERANCE_S = 1.8
_RAMP_STEP_UTTERANCE_S = 0.2
_STEADY_MAX_UTTERANCE_S = 2.4


@dataclass(frozen=True)
class TranscriptionTiming:
    """Mede espera e processamento de um trecho enviado ao STT."""

    audio_duration_s: float
    queue_wait_s: float
    processing_s: float
    real_time_factor: float


@dataclass(frozen=True)
class _TranscriptionJob:
    utter: np.ndarray
    min_utt_samples: int
    forced_split: bool
    begins_visual_speech: bool
    guard_words_override: Optional[int]
    queued_at: float


class _FlushPendingTail:
    pass


_STOP_TRANSCRIPTION_WORKER = object()


class _TranscriptionWorker:
    """Mantem captura/VAD ativos enquanto o STT processa em outra thread."""

    def __init__(
        self,
        session: "RealtimeTranscriptionSession",
        on_text: Callable[[str], None],
        on_status: Optional[Callable[[str], None]],
        on_speech_start: Optional[Callable[[], None]],
    ):
        self._session = session
        self._on_text = on_text
        self._on_status = on_status
        self._on_speech_start = on_speech_start
        self._jobs: queue.Queue[object] = queue.Queue()
        self._error: Optional[Exception] = None
        self._last_warning_at = 0.0
        self._thread = threading.Thread(
            target=self._run,
            name="globalvoice-transcription",
            daemon=True,
        )

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.flush_pending_tail()
        self._jobs.put(_STOP_TRANSCRIPTION_WORKER)
        self._thread.join()
        if exc is None and self._error is not None:
            raise self._error
        return False

    def submit(
        self,
        utter: np.ndarray,
        min_utt_samples: int,
        forced_split: bool,
        begins_visual_speech: bool = False,
        guard_words_override: Optional[int] = None,
    ) -> bool:
        if len(utter) < min_utt_samples:
            return False
        self._jobs.put(
            _TranscriptionJob(
                utter=utter,
                min_utt_samples=min_utt_samples,
                forced_split=forced_split,
                begins_visual_speech=begins_visual_speech,
                guard_words_override=guard_words_override,
                queued_at=time.perf_counter(),
            )
        )
        return True

    def flush_pending_tail(self) -> None:
        self._jobs.put(_FlushPendingTail())

    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            try:
                if job is _STOP_TRANSCRIPTION_WORKER:
                    return
                if isinstance(job, _FlushPendingTail):
                    self._session._flush_pending_tail(self._on_text)
                    continue

                assert isinstance(job, _TranscriptionJob)
                processing_started = time.perf_counter()
                queue_wait_s = processing_started - job.queued_at
                if job.begins_visual_speech and self._on_speech_start:
                    self._on_speech_start()
                transcription_processing_s = self._session._process_utterance(
                    utter=job.utter,
                    min_utt_samples=job.min_utt_samples,
                    forced_split=job.forced_split,
                    on_text=self._on_text,
                    guard_words_override=job.guard_words_override,
                )
                audio_duration_s = (
                    len(job.utter) / self._session.audio_source.target_sample_rate
                )
                timing = TranscriptionTiming(
                    audio_duration_s=audio_duration_s,
                    queue_wait_s=queue_wait_s,
                    processing_s=transcription_processing_s,
                    real_time_factor=(
                        transcription_processing_s / audio_duration_s
                        if audio_duration_s
                        else 0.0
                    ),
                )
                self._session._record_transcription_timing(timing)
                self._warn_if_pipeline_is_slow(timing)
            except Exception as worker_error:
                self._error = worker_error
                self._session._stop_requested = True
                return
            finally:
                self._jobs.task_done()

    def _warn_if_pipeline_is_slow(self, timing: TranscriptionTiming) -> None:
        if self._on_status is None:
            return
        if timing.real_time_factor < 0.9 and timing.queue_wait_s < 1.0:
            return

        now = time.monotonic()
        if now - self._last_warning_at < 5.0:
            return
        self._last_warning_at = now
        self._on_status(
            "Atraso detectado: STT levou "
            f"{timing.processing_s:.1f}s para {timing.audio_duration_s:.1f}s de áudio; "
            f"espera na fila {timing.queue_wait_s:.1f}s."
        )


class RealtimeTranscriptionSession:
    """Orquestra captura, segmentacao por fala/silencio e commit de texto.

    A sessao recebe blocos do microfone, fecha enunciados por detector de fala,
    chama o transcritor e publica somente texto novo para evitar repeticao.
    """

    def __init__(
        self,
        audio_source: AudioSourcePort,
        transcriber: TranscriberPort,
        speech_detector: Optional[SpeechDetectorPort] = None,
        language: str = "pt-br",
        capture_mode: str = "automatic",
        context_window: int = 0,
        speech_peak_threshold: float = 0.0018,
        max_silence_inside_utterance_s: float = 0.55,
        min_speech_window_s: float = 0.2,
        min_silence_window_s: Optional[float] = None,
        new_speech_silence_s: float = 2.0,
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
        self.capture_mode = (
            "push_to_talk" if capture_mode == "push_to_talk" else "automatic"
        )
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
        # A pausa que fecha um chunk tecnico pode ser curta para manter a
        # transcricao responsiva. Uma pausa maior separa falas visualmente.
        self.new_speech_silence_s = max(
            self.min_silence_window_s,
            new_speech_silence_s,
        )
        self.max_utterance_s = max_utterance_s
        self.min_utterance_s = min_utterance_s
        self.boundary_overlap_s = boundary_overlap_s
        self.tail_guard_words = max(0, tail_guard_words)
        self.forced_split_policy = (forced_split_policy or "protect_boundary").strip().lower()
        self.forced_split_extra_tail_words = max(0, forced_split_extra_tail_words)

        self._stop_requested = False
        self._talk_active = False
        self._microphone_muted = False
        self._live_words = deque(maxlen=1400)
        self._context_words = deque(maxlen=self.context_window)
        self._full_parts = []
        self._pending_tail_words = []
        self._pending_tail_overlap_limit = self.tail_guard_words
        self._min_overlap_words_for_dedupe = 2
        self._transcription_timings = deque(maxlen=20)

    def stop(self) -> None:
        """Solicita parada assicrona da sessao em execucao."""
        self._stop_requested = True

    def set_talk_active(self, active: bool) -> None:
        """Habilita a captura enquanto o modo apertar-para-falar estiver ativo."""
        self._talk_active = bool(active)

    def set_microphone_muted(self, muted: bool) -> None:
        """Ignora a captura automatica enquanto o microfone estiver mutado."""
        self._microphone_muted = bool(muted)

    def get_full_transcript(self) -> str:
        """Retorna o texto final acumulado na sessao."""
        return " ".join(self._full_parts).strip()

    def get_last_transcription_timing(self) -> Optional[TranscriptionTiming]:
        """Retorna a medicao mais recente sem expor detalhes da thread."""
        if not self._transcription_timings:
            return None
        return self._transcription_timings[-1]

    def _record_transcription_timing(self, timing: TranscriptionTiming) -> None:
        self._transcription_timings.append(timing)

    def run(
        self,
        on_text: Callable[[str], None],
        on_status: Optional[Callable[[str], None]] = None,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_voice_activity: Optional[Callable[[bool], None]] = None,
        max_duration_s: Optional[float] = None,
    ) -> str:
        """Executa o loop realtime e envia cada trecho confirmado via callback.

        Args:
            on_text: callback chamado com novos trechos confirmados.
            on_status: callback opcional para mensagens de estado.
            on_speech_start: callback disparado no inicio de cada nova fala.
            on_voice_activity: callback de atividade instantanea do VAD.
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
        silence_before_candidate_steps = 0
        carryover_audio = np.zeros(0, dtype=np.float32)
        carryover_silence_buffers = []
        talk_was_active = False
        visual_speech_started = False
        voice_was_active = False
        microphone_was_muted = False
        utterance_starts_visual_speech = False
        completed_chunks_in_speech = 0

        def publish_voice_activity(active: bool) -> None:
            nonlocal voice_was_active
            normalized = bool(active)
            if normalized == voice_was_active:
                return
            voice_was_active = normalized
            if on_voice_activity:
                on_voice_activity(normalized)

        if on_status:
            on_status("Inicializando captura de áudio...")

        started_at = time.time()

        with self.audio_source, _TranscriptionWorker(
            session=self,
            on_text=on_text,
            on_status=on_status,
            on_speech_start=on_speech_start,
        ) as transcription_worker:
            min_speech_steps = max(
                1,
                int(np.ceil(self.min_speech_window_s / self.audio_source.step_duration_s)),
            )
            min_silence_steps = max(
                1,
                int(np.ceil(self.min_silence_window_s / self.audio_source.step_duration_s)),
            )
            new_speech_silence_steps = max(
                min_silence_steps,
                int(
                    np.ceil(
                        self.new_speech_silence_s
                        / self.audio_source.step_duration_s
                    )
                ),
            )
            min_utt_samples = int(self.min_utterance_s * self.audio_source.target_sample_rate)
            overlap_samples = int(self.boundary_overlap_s * self.audio_source.target_sample_rate)

            if on_status:
                source_name = getattr(self.audio_source, "display_name", "Fonte de áudio")
                on_status(
                    f"Captura ativa: {source_name} em "
                    f"{self.audio_source.input_sample_rate} Hz "
                    f"(ASR: {self.audio_source.target_sample_rate} Hz)."
                )

            while not self._stop_requested:
                if max_duration_s is not None and (time.time() - started_at) >= max_duration_s:
                    break

                audio, peak = self.audio_source.read_step()

                if self.capture_mode == "push_to_talk":
                    if self._talk_active:
                        if not talk_was_active:
                            speech_buffers = []
                            carryover_audio = np.zeros(0, dtype=np.float32)
                            carryover_silence_buffers = []
                            utterance_starts_visual_speech = True
                            completed_chunks_in_speech = 0
                        talk_was_active = True
                        speech_buffers.append(audio)

                        utter_len = sum(len(chunk) for chunk in speech_buffers)
                        if utter_len >= self._max_utterance_samples(completed_chunks_in_speech):
                            utter = np.concatenate(speech_buffers).astype(np.float32)
                            protect_boundary = self._should_protect_forced_split_boundary()
                            if protect_boundary and overlap_samples > 0 and len(utter) > overlap_samples:
                                speech_buffers = [utter[-overlap_samples:].copy()]
                            else:
                                speech_buffers = []
                            submitted = transcription_worker.submit(
                                utter=utter,
                                min_utt_samples=max(
                                    1,
                                    int(
                                        self.min_speech_window_s
                                        * self.audio_source.target_sample_rate
                                    ),
                                ),
                                forced_split=protect_boundary,
                                begins_visual_speech=utterance_starts_visual_speech,
                                guard_words_override=self._responsive_tail_guard_words(
                                    completed_chunks_in_speech
                                ),
                            )
                            if submitted:
                                completed_chunks_in_speech += 1
                            utterance_starts_visual_speech = False
                    else:
                        if talk_was_active and speech_buffers:
                            utter = np.concatenate(speech_buffers).astype(np.float32)
                            transcription_worker.submit(
                                utter=utter,
                                min_utt_samples=max(
                                    1,
                                    int(
                                        self.min_speech_window_s
                                        * self.audio_source.target_sample_rate
                                    ),
                                ),
                                forced_split=False,
                                begins_visual_speech=utterance_starts_visual_speech,
                            )
                        if talk_was_active:
                            transcription_worker.flush_pending_tail()
                        talk_was_active = False
                        speech_buffers = []
                        utterance_starts_visual_speech = False
                    continue

                if self._microphone_muted:
                    publish_voice_activity(False)
                    if not microphone_was_muted:
                        transcription_worker.flush_pending_tail()
                        detector.reset()
                        speech_active = False
                        speech_buffers = []
                        speech_candidate_buffers = []
                        speech_candidate_steps = 0
                        silence_steps = 0
                        idle_silence_steps = 0
                        silence_before_candidate_steps = 0
                        carryover_audio = np.zeros(0, dtype=np.float32)
                        carryover_silence_buffers = []
                        visual_speech_started = False
                        utterance_starts_visual_speech = False
                        completed_chunks_in_speech = 0
                    microphone_was_muted = True
                    continue

                if microphone_was_muted:
                    detector.reset()
                    microphone_was_muted = False

                has_speech = detector.detect(audio, peak)
                publish_voice_activity(has_speech)

                if speech_active:
                    idle_silence_steps = 0
                    carryover_silence_buffers = []
                    speech_buffers.append(audio)
                    if has_speech:
                        silence_steps = 0
                    else:
                        silence_steps += 1
                else:
                    if has_speech:
                        carryover_silence_buffers = []
                        if speech_candidate_steps == 0:
                            silence_before_candidate_steps = idle_silence_steps
                            idle_silence_steps = 0
                        speech_candidate_buffers.append(audio)
                        speech_candidate_steps += 1
                        if speech_candidate_steps >= min_speech_steps:
                            speech_buffers = [carryover_audio] if len(carryover_audio) > 0 else []
                            speech_buffers.extend(speech_candidate_buffers)
                            carryover_audio = np.zeros(0, dtype=np.float32)

                            speech_active = True
                            starts_visual_speech = (
                                not visual_speech_started
                                or silence_before_candidate_steps
                                >= new_speech_silence_steps
                            )
                            utterance_starts_visual_speech = starts_visual_speech
                            if starts_visual_speech:
                                completed_chunks_in_speech = 0
                            visual_speech_started = True
                            silence_steps = 0
                            silence_before_candidate_steps = 0
                            speech_candidate_buffers = []
                            speech_candidate_steps = 0
                    else:
                        idle_silence_steps += 1
                        if len(carryover_audio) > 0:
                            carryover_silence_buffers.append(audio)
                        silence_before_candidate_steps = 0
                        speech_candidate_buffers = []
                        speech_candidate_steps = 0

                    if idle_silence_steps == min_silence_steps:
                        if len(carryover_audio) > 0:
                            # O resto de um corte forcado precisa de sua propria
                            # janela de STT quando a fala termina logo depois.
                            tail = np.concatenate(
                                [carryover_audio, *carryover_silence_buffers]
                            ).astype(np.float32)
                            submitted = transcription_worker.submit(
                                utter=tail,
                                min_utt_samples=max(
                                    1, int(self.min_speech_window_s * self.audio_source.target_sample_rate),
                                ),
                                forced_split=False,
                            )
                            if submitted:
                                completed_chunks_in_speech += 1
                            carryover_audio = np.zeros(0, dtype=np.float32)
                            carryover_silence_buffers = []
                        transcription_worker.flush_pending_tail()

                utter_len = sum(len(x) for x in speech_buffers) if speech_buffers else 0
                natural_split = speech_active and silence_steps >= min_silence_steps
                forced_by_time = (
                    speech_active
                    and utter_len >= self._max_utterance_samples(completed_chunks_in_speech)
                )
                should_finalize = natural_split or forced_by_time

                if should_finalize:
                    # forced_split e usado somente quando tempo maximo estoura sem pausa natural.
                    forced_split = forced_by_time and not natural_split
                    apply_boundary_protection = forced_split and self._should_protect_forced_split_boundary()

                    utter = np.concatenate(speech_buffers).astype(np.float32)
                    speech_active = False
                    speech_buffers = []
                    idle_silence_steps = silence_steps if natural_split else 0
                    silence_steps = 0

                    if apply_boundary_protection and overlap_samples > 0 and len(utter) > overlap_samples:
                        # Sobreposicao apenas em corte forcado para salvar fronteira de palavra.
                        carryover_audio = utter[-overlap_samples:].copy()
                    else:
                        carryover_audio = np.zeros(0, dtype=np.float32)
                    carryover_silence_buffers = []

                    submitted = transcription_worker.submit(
                        utter=utter,
                        min_utt_samples=min_utt_samples,
                        forced_split=apply_boundary_protection,
                        begins_visual_speech=utterance_starts_visual_speech,
                        guard_words_override=self._responsive_tail_guard_words(
                            completed_chunks_in_speech
                        ),
                    )
                    if submitted:
                        completed_chunks_in_speech += 1
                    if natural_split:
                        # A pausa ja atingiu o limite neste passo; aguardar o
                        # proximo bloco deixava o ultimo texto preso no worker.
                        transcription_worker.flush_pending_tail()
                    utterance_starts_visual_speech = False

            if len(carryover_audio) > 0 and not speech_buffers:
                tail = np.concatenate(
                    [carryover_audio, *carryover_silence_buffers, *speech_candidate_buffers]
                ).astype(np.float32)
                transcription_worker.submit(
                    utter=tail,
                    min_utt_samples=max(
                        1, int(self.min_speech_window_s * self.audio_source.target_sample_rate),
                    ),
                    forced_split=False,
                )
                speech_candidate_buffers = []

            remaining_buffers = speech_buffers if speech_buffers else speech_candidate_buffers
            if remaining_buffers:
                utter = np.concatenate(remaining_buffers).astype(np.float32)
                final_min_utterance_s = (
                    self.min_speech_window_s
                    if self.capture_mode == "push_to_talk"
                    else self.min_utterance_s
                )
                transcription_worker.submit(
                    utter=utter,
                    min_utt_samples=max(
                        1,
                        int(final_min_utterance_s * self.audio_source.target_sample_rate),
                    ),
                    forced_split=False,
                    begins_visual_speech=utterance_starts_visual_speech,
                )

            # O worker faz o flush final e drena os trechos antes de encerrar.

        publish_voice_activity(False)

        return self.get_full_transcript()

    def _reset_state(self) -> None:
        """Limpa buffers internos antes de iniciar uma nova sessao."""
        self._live_words.clear()
        self._context_words = deque(maxlen=self.context_window)
        self._full_parts = []
        self._pending_tail_words = []
        self._pending_tail_overlap_limit = self.tail_guard_words
        self._transcription_timings.clear()

    def _should_protect_forced_split_boundary(self) -> bool:
        """Define se corte forcado aplica overlap + tail guard."""
        return self.forced_split_policy not in {"hard_cut", "none", "disabled"}

    def _max_utterance_samples(self, completed_chunks: int) -> int:
        """Aumenta suavemente o trecho inicial e mantém um teto responsivo."""
        responsive_limit_s = min(
            _STEADY_MAX_UTTERANCE_S,
            _RAMP_START_UTTERANCE_S
            + completed_chunks * _RAMP_STEP_UTTERANCE_S,
        )
        responsive_limit_s = max(
            responsive_limit_s,
            self.min_utterance_s + self.audio_source.step_duration_s,
        )
        limit_s = min(self.max_utterance_s, responsive_limit_s)
        return max(1, round(limit_s * self.audio_source.target_sample_rate))

    def _responsive_tail_guard_words(self, completed_chunks: int) -> int:
        """Publica texto progressivamente também após os primeiros cortes."""
        configured_guard = self.tail_guard_words + self.forced_split_extra_tail_words
        responsive_guard = 1 if completed_chunks == 0 else 2
        return min(configured_guard, responsive_guard)

    def _process_utterance(
        self,
        utter: np.ndarray,
        min_utt_samples: int,
        forced_split: bool,
        on_text: Callable[[str], None],
        guard_words_override: Optional[int] = None,
    ) -> float:
        """Transcreve um enunciado completo e aplica regras de commit."""
        if len(utter) < min_utt_samples:
            return 0.0

        context_prompt = " ".join(self._context_words) if self._context_words else None
        transcription_started = time.perf_counter()
        text = self.transcriber.transcribe(
            utter,
            language=self.language,
            context_prompt=context_prompt,
        )
        transcription_processing_s = time.perf_counter() - transcription_started
        if text:
            self._commit_transcribed_text(
                text, forced_split=forced_split, on_text=on_text,
                guard_words_override=guard_words_override,
            )
        return transcription_processing_s

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

    def _commit_transcribed_text(
        self, text: str, forced_split: bool, on_text: Callable[[str], None],
        guard_words_override: Optional[int] = None,
    ) -> None:
        """Aplica dedupe e tail guard antes de publicar texto."""
        words = [w for w in text.split() if w.strip()]
        if not words:
            return

        words = self._merge_with_pending_tail(words)

        if forced_split:
            guard_words = (
                self.tail_guard_words + self.forced_split_extra_tail_words
                if guard_words_override is None else max(0, guard_words_override)
            )
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

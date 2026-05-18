# Backend - Realtime Transcricao

Este modulo concentra a logica de negocio da transcricao em tempo real.

## Objetivo

- manter captura + VAD + transcricao desacoplados da interface grafica;
- permitir substituicao futura da transcricao local por chamada remota sem alterar a camada de UI.

## Estrutura

- app/audio/audio_capture.py
  - leitura de audio do microfone em passos fixos (step)
  - conversao para 16 kHz
- app/ports.py
  - contratos de transcricao e detector de fala (TranscriberPort / SpeechDetectorPort)
- app/detectors/speech_detectors.py
  - implementacoes de detector (Silero principal + energia como fallback)
- app/transcribers/local_faster_whisper.py
  - implementacao local com Faster-Whisper
- app/sessions/realtime_session.py
  - orquestracao de sessao realtime (VAD, commit, dedupe, overlap, tail guard)

## Segmentacao hibrida desta etapa

- corte natural: fechamento por pausa/silencio detectado; chunk enviado limpo;
- corte forcado: fechamento por tempo maximo de enunciado; aplica overlap + tail guard;
- fallback: se Silero nao estiver disponivel, o detector por energia continua operacional.

## Evolucao planejada

Quando o backend virar servico remoto, a ideia e manter a sessao e substituir apenas a implementacao ligada ao contrato de transcricao.

Exemplo de direcao:

- hoje: LocalFasterWhisperTranscriber
- futuro: HttpTranscriberClient ou WebSocketTranscriberClient

Com isso, a interface do frontend permanece estavel e muda somente a ponte de integracao.

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
  - contrato de transcricao (TranscriberPort)
- app/transcribers/local_faster_whisper.py
  - implementacao local com Faster-Whisper
- app/sessions/realtime_session.py
  - orquestracao de sessao realtime (VAD, commit, dedupe, overlap, tail guard)

## Evolucao planejada

Quando o backend virar servico remoto, a ideia e manter a sessao e substituir apenas a implementacao ligada ao contrato de transcricao.

Exemplo de direcao:

- hoje: LocalFasterWhisperTranscriber
- futuro: HttpTranscriberClient ou WebSocketTranscriberClient

Com isso, a interface do frontend permanece estavel e muda somente a ponte de integracao.

# Backend - Realtime Transcricao

Este modulo concentra a logica de negocio da transcricao em tempo real.

## Objetivo

- manter captura + VAD + transcricao desacoplados da interface grafica;
- permitir substituicao futura da transcricao local por chamada remota sem alterar a camada de UI.

## Estrutura

- app/audio/audio_capture.py
  - leitura do microfone ou da saida do Windows em passos fixos (step)
  - captura WASAPI loopback, downmix e conversao para 16 kHz
- app/audio/devices.py
  - catalogo de entradas, saidas e endpoints de loopback
- app/ports.py
  - contratos de fonte, transcricao e detector de fala
    (AudioSourcePort / TranscriberPort / SpeechDetectorPort)
- app/detectors/speech_detectors.py
  - implementacoes de detector (Silero principal + energia como fallback)
- app/detectors/silero_onnx.py
  - execucao em streaming do modelo Silero versionado, sem PyTorch
- app/transcribers/local_faster_whisper.py
  - implementacao local com Faster-Whisper
- app/sessions/realtime_session.py
  - orquestracao de sessao realtime (VAD, commit, dedupe, overlap, tail guard)
  - captura e VAD continuam ativos enquanto o STT processa o trecho anterior
  - medicao de tempo do STT, fator de tempo real (RTF) e espera na fila

## Segmentacao hibrida desta etapa

- corte natural: fechamento por pausa/silencio detectado; chunk enviado limpo;
- corte forcado: fechamento por tempo maximo de enunciado; aplica overlap + tail guard;
- fallback: se Silero nao estiver disponivel, o detector por energia continua operacional.

Quando o STT se aproxima ou ultrapassa a duracao do proprio audio, a sessao
informa o tempo de processamento e a espera acumulada. Isso diferencia um limite
do hardware de atrasos causados pela captura ou pela fila do pipeline.

Antes dessa separacao, a chamada bloqueante ao Faster-Whisper ocorria dentro do
mesmo loop que lia os proximos blocos. A decisao inicial simplificava a
segmentacao e a ordem do texto, mas permitia acumulo de audio sempre que a
inferencia demorava. O worker atual preserva a ordem dos trechos e associa o
inicio visual da fala ao resultado correspondente.

## Evolucao planejada

Quando o backend virar servico remoto, a ideia e manter a sessao e substituir apenas a implementacao ligada ao contrato de transcricao.

Exemplo de direcao:

- hoje: LocalFasterWhisperTranscriber
- futuro: HttpTranscriberClient ou WebSocketTranscriberClient

Com isso, a interface do frontend permanece estavel e muda somente a ponte de integracao.

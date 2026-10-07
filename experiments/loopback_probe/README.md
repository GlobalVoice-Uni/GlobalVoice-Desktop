# Prova de captura WASAPI loopback

Este diagnostico isola a captura do audio reproduzido pelo Windows. Ele permite
confirmar o endpoint e ouvir a amostra antes de atribuir uma falha ao VAD ou ao
Whisper.

Liste as saidas:

```powershell
.\.venv\Scripts\python.exe -m experiments.loopback_probe.capture_loopback --list
```

Reproduza um audio e capture cinco segundos da saida padrao:

```powershell
.\.venv\Scripts\python.exe -m experiments.loopback_probe.capture_loopback
```

O WAV e salvo em `experiments/loopback_probe/results/loopback_sample.wav`. Para
usar outra saida, copie o identificador exibido por `--list` e informe-o em
`--device-id`.

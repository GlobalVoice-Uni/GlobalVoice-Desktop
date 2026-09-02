# Auditoria do runtime

Estes experimentos nao fazem parte da interface nem da distribuicao do Global
Voice. A comparacao validou o modelo ONNX oficial do Silero 6.2 antes de ele ser
promovido ao backend, eliminando a necessidade de distribuir PyTorch, Torchaudio
e o pacote Python do Silero.

Execute primeiro com o sinal tecnico deterministico:

```powershell
.\.venv\Scripts\python.exe -m experiments.runtime_audit.compare_silero_vad
```

Por padrao, o candidato usa diretamente o ONNX de 16 kHz e opset 15 da mesma
versao Silero `6.2.0` que esta em producao. Para diagnosticar diferencas entre
exports, tambem e possivel comparar o modelo que acompanha o `faster-whisper`:

```powershell
.\.venv\Scripts\python.exe -m experiments.runtime_audit.compare_silero_vad `
  --candidate-model faster-whisper
```

Depois repita com uma gravacao real, preferencialmente contendo fala e pausas:

```powershell
.\.venv\Scripts\python.exe -m experiments.runtime_audit.compare_silero_vad `
  --audio "C:\caminho\amostra.wav"
```

A ferramenta requer uma venv de desenvolvimento que ainda tenha `silero-vad`
instalado para fornecer a referencia PyTorch. A venv limpa de build nao possui
esse pacote. Diferencas pequenas de probabilidade sao esperadas entre
representacoes do mesmo modelo, desde que nao alterem as transicoes.

O modelo e a logica de referencia do Silero sao disponibilizados sob licenca MIT.
O arquivo ONNX utilizado e distribuido pelo `faster-whisper`, tambem sob MIT.

# Linha de base do ASR atual

Este experimento mede somente o `LocalFasterWhisperTranscriber` já usado pelo
Global Voice. Ele não é importado pela interface, não inicia junto com a aplicação
e não adiciona motores alternativos ao produto.

A comparação entre diferentes motores, modelos e configurações continua separada
no repositório
[GlobalVoice-ASR-Benchmarks](https://github.com/GlobalVoice-Uni/GlobalVoice-ASR-Benchmarks).
Depois da avaliação, apenas a opção aprovada poderá ser integrada ao aplicativo.

## O que é medido

- tempo de carga do modelo;
- tempo de processamento e fator de tempo real (RTF) de cada repetição;
- uso de memória do processo e pico de VRAM alocada, quando disponíveis;
- transcrição produzida;
- taxa de erro por palavra (WER), quando um texto de referência é informado;
- ambiente, configuração, revisão do Git e hash do áudio.

O RTF é o tempo de processamento dividido pela duração do áudio. Valor menor que
`1` significa que o arquivo foi processado mais rápido que sua duração, mas não
garante sozinho a qualidade do fluxo ao vivo.

## Execução

Use sempre o mesmo WAV e o mesmo TXT de referência ao comparar resultados. Para a
primeira linha de base, prefira um par de arquivos do corpus fixo do repositório de
benchmarks.

```powershell
.\experiments\asr_baseline\run_baseline.ps1 `
  --audio "C:\caminho\audio.wav" `
  --reference "C:\caminho\referencia.txt" `
  --language pt `
  --model small `
  --device cpu `
  --runs 3
```

Troque `cpu` por `gpu` para uma segunda medição no mesmo computador. O JSON é
gravado em `results/`; resultados locais são ignorados pelo Git para evitar tratar
uma máquina isolada como conclusão do grupo.


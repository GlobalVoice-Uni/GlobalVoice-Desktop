# Entrega 3 — voz traduzida (primeira build de teste)

Este documento registra a build `0.3.0`. A rota fixa pelo VB-CABLE e o
critério de até 30 ms adicionais para a voz original estão em
[entrega-3-cabo-virtual.md](entrega-3-cabo-virtual.md), para a build `0.3.1`.

## O que entrou

- `SpeechSynthesizerPort` e `AudioSinkPort`, com Piper local e reprodução pela saída
  PortAudio selecionada. A síntese e a reprodução rodam em fila limitada, fora do
  callback de transcrição. Ao parar, a fila é descartada e a reprodução para
  entre blocos de 200 ms.
- Fonte **Microfone e reunião**: as duas capturas têm VAD e segmentação próprios,
  compartilham o modelo STT sob trava e traduzem em direções opostas pelo Argos.
  Os trechos são identificados como **Você** e **Reunião** na janela flutuante.
- Aba **Voz** nas configurações: saída da reunião capturada, envio da voz
  traduzida à chamada e retorno em voz para um segundo dispositivo. A aplicação
  rejeita uma rota que reproduziria a própria voz no dispositivo de loopback.
- Diálogo de alterações pendentes: quebra de linha após “configurações.”,
  **Salvar e fechar** em um clique, **Descartar**, e X para voltar à edição.

## Escolha de TTS e distribuição

O Piper foi selecionado para esta build de avaliação por executar localmente com
ONNX Runtime, ter API de síntese em memória e permitir vozes por idioma. Foram
incluídas as vozes `pt_BR-faber-medium`, `en_US-ljspeech-medium` e
`es_ES-sharvard-medium`, com os modelos, configurações e cartões dos modelos
na pasta interna da aplicação. Os três arquivos ONNX somam 203,5 MB; a preparação
confere SHA-256 antes da build.

O pacote Piper atual é GPL-3.0-or-later. Os cartões das vozes descrevem conjuntos
de treino diferentes: Faber usa CC0; LJSpeech informa domínio público;
Sharvard indica CC BY 3.0. A distribuição final requer uma revisão própria das
obrigações do motor, das vozes e dos dados de treino. Fontes:
[Piper Python API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md),
[licença do Piper](https://github.com/OHF-Voice/piper1-gpl/blob/main/LICENSE),
[Faber](https://huggingface.co/rhasspy/piper-voices/blob/main/pt/pt_BR/faber/medium/MODEL_CARD),
[LJSpeech](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/ljspeech/medium/MODEL_CARD) e
[Sharvard](https://huggingface.co/rhasspy/piper-voices/blob/main/es/es_ES/sharvard/medium/MODEL_CARD).

## Verificação automatizada

- Síntese real de frases curtas em português, inglês e espanhol: áudio finito,
  mono, com duração acima de 250 ms. O teste não toca os dispositivos.
- Fila: enfileirar não bloqueia a captura; cancelar descarta frases pendentes.
- Saída: usa o ID escolhido, toca em blocos e observa o sinal de parada.
- Sessão dupla: ambos os canais chegam ao frontend, com tradução em direções
  opostas; uma rota de retorno em loop é rejeitada antes de carregar modelos.
- Os 121 testes do projeto passaram na venv. A qualidade perceptual da voz,
  a latência de ponta a ponta e a chamada real ainda aguardam validação manual.
- A pasta empacotada abriu sem saída prematura; o instalador `0.3.0` compilou
  com 751,88 MiB. SHA-256:
  `4412a2393cfd4e55db4383528d40daecf080cb0f84a284b3584f5fe1a6e5b731`.
  O instalador `0.2.3` permaneceu intacto.

## Validação manual pendente

1. Instalar a nova build separada da `0.2.3`. Abrir **Configurações > Voz** e
   selecionar **Microfone e reunião**. Escolher o microfone, a saída capturada da
   reunião e uma **saída virtual diferente** em “Enviar pelo dispositivo”. Na
   chamada, usar a entrada correspondente à saída virtual.
2. Ativar “Enviar voz traduzida à chamada”, iniciar, falar em português e
   verificar a via **Você** e a voz em inglês recebida na chamada. Repetir com os
   idiomas invertidos. Conferir que **Reunião** continua transcrevendo e
   traduzindo ao mesmo tempo.
3. Se houver um segundo dispositivo de saída, ativar “Ouvir tradução da reunião”
   e verificar o áudio nos fones. Confirmar que não surge loop de recaptura.
4. Durante falas simultâneas, alternar o microfone para mudo e parar a sessão;
   conferir que a saída de voz para e o aplicativo permanece responsivo.
5. Alterar uma configuração e clicar em **Fechar**: verificar a quebra de linha,
   **Salvar e fechar** em um clique, **Descartar** e X para continuar editando.

Nesta máquina de desenvolvimento, SoundCard encontrou só o headset como saída
WASAPI, mas PortAudio também identificou saídas virtuais AudioRelay e SteelSeries.
A enumeração e a seleção dessas saídas foram corrigidas antes da build. A rota de
chamada e o retorno em um segundo dispositivo ainda exigem a validação manual.
`sounddevice.check_output_settings` aceitou saída mono em 44,1 kHz no headset,
no AudioRelay e em três saídas SteelSeries; isso verifica a abertura dos formatos,
sem reproduzir áudio.

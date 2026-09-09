# Entrega 1 — teste externo do instalador

Este roteiro valida o mesmo instalador em dois cenários de hardware: um notebook
com Ryzen e Radeon Vega integrada e outro com GPU NVIDIA dedicada. O objetivo é
confirmar instalação, seleção automática do perfil e funcionamento real da
transcrição fora da máquina de desenvolvimento.

Pacote preparado em 4 de setembro de 2026:

- arquivo: `GlobalVoice-Setup-0.1.0.exe`;
- tamanho: 520,93 MB;
- SHA-256: `BAC86CA5720D68BF7153C1197DB5D83E42D6B69FB0F6B01A5FE2B6A1D49CA4D7`.

O arquivo `.exe.sha256` distribuído junto ao instalador contém o mesmo valor. No
PowerShell, a cópia pode ser conferida com:

```powershell
Get-FileHash .\GlobalVoice-Setup-0.1.0.exe -Algorithm SHA256
```

## Perfis desta versão

| Hardware detectado | Conteúdo instalado | Execução esperada do ASR |
| --- | --- | --- |
| NVIDIA | Base + CUDA 12/cuBLAS | GPU via CTranslate2/CUDA |
| AMD ou Intel | Base | CPU otimizada pelo CTranslate2 |
| Sem GPU reconhecida | Base | CPU |

O instalador não inclui um perfil AMD ou Intel que o motor atual não consiga
usar. Os binários pré-compilados do CTranslate2 aceleram GPU por CUDA/NVIDIA; um
pacote DirectML isolado não altera esse motor. Para ampliar a cobertura, a
Entrega 1 mantém como candidato um adaptador separado baseado em um motor
multiplaca, como o `whisper.cpp` com Vulkan, antes de incorporá-lo à aplicação.

Referências:

- [Hardware suportado pelo CTranslate2](https://opennmt.net/CTranslate2/hardware_support.html)
- [Provedor DirectML do ONNX Runtime](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html)
- [Suporte Vulkan do whisper.cpp](https://github.com/ggml-org/whisper.cpp#vulkan-gpu-support)

## Antes do teste

- Usar Windows 10 ou 11 de 64 bits.
- Manter conexão com a internet na primeira transcrição, pois o modelo do
  Faster-Whisper ainda é baixado sob demanda.
- Anotar o modelo do processador, o nome da GPU e a versão do Windows.
- Se já houver uma instalação anterior, desinstalá-la antes deste teste.

## Notebook Ryzen com Vega integrada

- [x] O componente NVIDIA começa desmarcado no instalador.
- [x] A instalação e os atalhos são concluídos normalmente.
- [x] GPU permanece como preferência inicial e Silero como VAD inicial.
- [x] Ao iniciar a transcrição, o dispositivo ativo muda para `CPU · fallback`.
- [x] O texto de ajuda informa que uma GPU AMD ou Intel foi detectada, mas que o
  motor atual acelera somente em NVIDIA.
- [x] A transcrição funciona por pelo menos cinco minutos sem encerramento ou
  erro visível.
- [x] A desinstalação remove a pasta e os atalhos.

## Notebook com NVIDIA dedicada

- [x] O componente NVIDIA começa marcado automaticamente e pode ser desmarcado.
- [x] A instalação e os atalhos são concluídos normalmente.
- [x] GPU permanece como preferência inicial e Silero como VAD inicial.
- [x] Ao iniciar a transcrição, o dispositivo ativo mostra `GPU · CUDA`.
- [x] A transcrição funciona por pelo menos cinco minutos sem erro de DLL.
- [x] A desinstalação remove a pasta e os atalhos.

## Resultado da validação externa

A rodada externa foi concluída em 8 de setembro de 2026 nos dois perfis previstos.
O instalador selecionou o componente compatível, a aplicação transcreveu usando o
dispositivo esperado e a desinstalação removeu os arquivos e atalhos. Os modelos
exatos de processador e GPU, a versão do Windows e os tempos observados devem ser
acrescentados às notas da primeira versão quando forem consolidados pela equipe.

## Resultado a registrar

Para cada máquina, registrar:

- processador, GPU e versão do Windows;
- componente selecionado automaticamente pelo instalador;
- dispositivo e provedor realmente exibidos durante a transcrição;
- tempo aproximado até a primeira transcrição;
- comportamento percebido da transcrição e qualquer mensagem apresentada;
- resultado da desinstalação.

Se a máquina NVIDIA cair para CPU, registrar o texto de ajuda exibido e a versão
do driver. Se a máquina Vega aparecer como GPU ativa, o resultado deve ser
considerado incorreto nesta versão, pois o motor atual não possui um backend AMD.

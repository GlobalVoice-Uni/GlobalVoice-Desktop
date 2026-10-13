# Entrega 2 — comparação estática de tradutores

Gerado em 2026-10-13T17:18:47.374558+00:00. Dados completos: [`data/tradutores-corpus-estatico.json`](data/tradutores-corpus-estatico.json). [Saídas completas](entrega-2-saidas-comparacao-tradutores.md).

## Objetivo e método

Comparar os adaptadores atuais Argos, M2M-100 FP32 e M2M-100 INT8 em EN ↔ PT usando o mesmo corpus. Os seis áudios e textos vêm de `GlobalVoice-Testes/static_model_tests`; foram copiados byte a byte para `experiments/translation_comparison/corpus/`. Os textos são referências de transcrição, não de tradução.

O Faster-Whisper `small` transcreveu cada áudio uma vez em `cuda` com `float32`. Cada motor traduziu tanto o texto original quanto essa mesma transcrição. A tradução rodou em CPU, com dois sentidos diretos, um processo isolado por motor e `beam_size=4` nos adaptadores. Cada caso foi executado 2 vezes; a tabela usa a mediana. O tempo de carga é separado do tempo de tradução. O tempo de decodificação do MP4 não entra no tempo de ASR.

## Ambiente

- Sistema: Windows-10-10.0.19045-SP0; Python 3.12.3.
- CPU: Intel64 Family 6 Model 158 Stepping 11, GenuineIntel (4 processadores lógicos).
- GPU do ASR: NVIDIA GeForce GTX 1050, 582.66, 2048 MiB.
- Bibliotecas: ctranslate2 4.7.1, faster-whisper 1.2.1, sentencepiece 0.2.2, numpy 2.4.4.
- Memória: working set do processo isolado no Windows; pico inclui importações, carga e inferência. Os valores não representam o consumo total do sistema nem VRAM dos tradutores, que executaram em CPU.

## Corpus e ASR comum

Seis áudios de cerca de 10, 30 e 60 s, em português e inglês, foram transcritos uma vez pelo Faster-Whisper `small` em CUDA. Todos os motores receberam a mesma transcrição e o texto original correspondente. O WER mede apenas o ASR e não entrou na nota de tradução; os valores por caso estão nos [dados completos](data/tradutores-corpus-estatico.json).

## Recursos dos tradutores

| Motor | Pesos usados (MiB) | Carga (s) | Working set após carga (MiB) | Pico do processo (MiB) |
| --- | ---: | ---: | ---: | ---: |
| Argos | 153,00 | 4,25 | 708,78 | 718,68 |
| M2M FP32 | 1849,74 | 6,28 | 2413,68 | 2448,26 |
| M2M INT8 | 467,94 | 4,70 | 1035,15 | 1068,58 |

Os pesos representam os `model.bin` necessários para EN ↔ PT; tokenizadores e metadados acrescentam espaço em disco. O working set é específico do processo do benchmark e pode variar com cache e carga do Windows.

## Latência de tradução

Soma das medianas dos seis casos na primeira rodada, sem tempo de carga do motor. Cada caso teve duas medições. Os valores por caso permanecem nos [dados completos](data/tradutores-corpus-estatico.json).

| Motor | Texto original (s) | Transcrição (s) |
| --- | ---: | ---: |
| Argos | 4,08 | 4,26 |
| M2M FP32 | 66,43 | 66,68 |
| M2M INT8 | 24,27 | 24,11 |

Estas somas não representam latência de streaming. Os áudios de 10/30/60 s foram divididos em frases pelas mesmas regras em todos os motores.

## Qualidade e decisão

A impressão inicial de qualidade superior do Argos motivou a comparação automática. O corpus de áudio não contém traduções humanas de referência, por isso não recebe uma nota automática de qualidade. O FLORES-200 abaixo fornece referências humanas para EN ↔ PT; os exemplos de erro deste corpus verificam relações e termos que uma métrica de superfície pode não captar. A eventual camada de melhoria textual deve ser medida depois, no mesmo corpus.

Há erros de sentido observáveis nos textos originais desta rodada. No caso 60sEN, `her cousin` virou `seu primo` no Argos e `seu cônjuge` nas duas variantes M2M; `skyscrapers` virou `arranha-céus` no Argos e `esquiadores` no M2M. No 60sBR, `garçonete` virou `waitress` no Argos e `boy`/`boyfriend` no M2M. O Argos também apresenta desvios em outras frases; estes exemplos não são uma nota agregada. Uma camada de polimento gramatical não garante recuperar relações e entidades trocadas sem consultar o texto original.

Nas três rodadas em CPU, as saídas dos textos originais não mudaram. O FP32 manteve as mesmas trocas de `cousin` e `skyscrapers` do INT8, e também errou `garçonete` como `boy`. Não surgiu vantagem semântica observável para justificar seu peso e sua latência neste laboratório. Esses dados desaconselham levar FP32 à versão final. A decisão usa as medições automáticas; isso não é uma avaliação de qualidade geral dos modelos.

## Limitações

- Uma máquina; a tabela inicial retrata uma rodada com duas repetições por caso. As rodadas adicionais alternam a ordem. Cache, temperatura e outros processos podem alterar os tempos.
- Textos e áudio têm conteúdo correspondente, mas a tradução de ASR inclui os erros próprios da transcrição. A comparação entre motores usa a mesma transcrição em cada caso.
- A tabela inicial usa CPU para os três tradutores. A medição posterior em GPU executa Argos e INT8 isolados do ASR; na GTX 1050 de 2 GiB, manter tradução e ASR na GPU reduz a margem de VRAM.
- Este corpus não contém espanhol nem referências humanas de tradução. O FLORES-200 abaixo cobre referências EN ↔ PT; os sentidos com espanhol permanecem sem medida de qualidade nesta branch.

## Repetição da comparação

Três rodadas em CPU alternaram a ordem dos motores, com duas medições internas por caso. A tabela mostra a mediana entre rodadas da soma dos seis textos originais.

| Motor | Mediana (s) | Menor–maior (s) |
| --- | ---: | ---: |
| Argos | 4,25 | 4,08–4,41 |
| M2M FP32 | 66,43 | 65,15–72,69 |
| M2M INT8 | 25,02 | 24,27–25,68 |

As saídas dos textos originais permaneceram iguais nas três rodadas. Os [JSONs das rodadas](data/) preservam ordem, saídas e tempos por caso.

## Argos e M2M INT8 em GPU

Duas rodadas CUDA usaram os mesmos seis textos em processos isolados, sem fallback. O ASR terminou antes da tradução. Portanto estes tempos não incluem disputa simultânea de VRAM.

| Condição | Mediana entre rodadas (s) |
| --- | ---: |
| Argos CPU | 4,25 |
| Argos CUDA | 3,46 |
| M2M INT8 CUDA | 9,44 |

Nesta GTX 1050 de 2 GiB, o M2M INT8 em CUDA levou 2,72 vezes o tempo do Argos em CUDA e 2,22 vezes o tempo do Argos em CPU. A redação variou entre CPU e CUDA, mas nas três verificações automáticas de conceitos (`cousin`, `skyscrapers`, `garçonete`) o Argos acertou 3/3 em ambos os dispositivos; FP32 e INT8 acertaram 0/3 nas condições medidas. Essas verificações cobrem apenas os termos escolhidos e não substituem uma avaliação geral de qualidade. [Rodada CUDA 1](data/tradutores-corpus-gpu-rodada-01.json) · [Rodada CUDA 2](data/tradutores-corpus-gpu-rodada-02.json).

## Qualidade com referências: FLORES-200

O [FLORES-200](https://github.com/facebookresearch/flores/blob/main/flores200/README.md) é um conjunto público de frases paralelas com traduções humanas, criado para avaliar tradução automática em muitos idiomas. Usamos uma amostra fixa de 100 frases por sentido do seu `devtest`, distribuídas uniformemente pelos 1.012 índices; o arquivo de origem foi fixado por SHA-256 e a amostra está em [`data/flores200-devtest-100.json`](data/flores200-devtest-100.json). Licença CC BY-SA 4.0. Ambos os motores usaram CPU, em processos separados e com os mesmos textos. A métrica é chrF++ (`word_order=2`) do SacreBLEU 2.5.1; pontuação maior indica maior semelhança com a referência.

| Sentido | Argos chrF++ | INT8 chrF++ | Argos tempo total (s) | INT8 tempo total (s) |
| --- | ---: | ---: | ---: | ---: |
| en->pt | 66,04 | 63,31 | 18,60 | 129,45 |
| pt->en | 67,80 | 63,42 | 19,07 | 131,78 |

Assinatura da métrica: `nrefs:1|case:mixed|eff:yes|nc:6|nw:2|space:no|version:2.5.1`. Saídas individuais e tempos: [`Argos`](data/flores200-argos.json), [`M2M INT8`](data/flores200-m2m100_int8.json). Amostra e pesos fixados por hash permitem reproduzir a pontuação; chrF++ mede semelhança de superfície e pode não detectar trocas semânticas como as do corpus de áudio.

**Decisão para a versão de entrega: Argos.** Nesta máquina e nestes corpora, foi mais rápido nos dois sentidos, obteve chrF++ maior nos dois sentidos e preservou melhor os três conceitos verificados automaticamente no corpus estático. O FP32 repetiu os erros decisivos do INT8 e consumiu mais recursos. A branch de comparação guarda os três motores; a versão de entrega deve incorporar só Argos.

FLORES-200 é texto geral e não contém áudio de reuniões. O português da referência pode diferir do português brasileiro dos pacotes Argos. A qualidade dos sentidos com espanhol não foi medida porque exigiria baixar quatro pacotes Argos adicionais; não se deve extrapolar o escore EN ↔ PT para esses sentidos.

## Disputa de VRAM com o ASR

Sondagem isolada do M2M INT8 com o Faster-Whisper `small` em CUDA: o áudio 10sBR foi transcrito e o texto 30sBR foi traduzido em cada ciclo. As duas condições foram executadas em processos separados. Os números abaixo são medianas dos ciclos de cada condição.

| M2M INT8 | Carga (s) | ASR 10sBR (s) | Tradução 30sBR (s) | VRAM livre após carga (MiB) |
| --- | ---: | ---: | ---: | ---: |
| CPU | 1,62 | 1,93 | 4,05 | 367 |
| CUDA | 0,80 | 3,29 | 1,93 | 130 |

Esta sondagem mede o efeito conjunto, além da velocidade de tradução isolada. O código do aplicativo reserva VRAM para o ASR e recua silenciosamente para CPU quando a GPU é pequena ou está ocupada. O critério é conservador e precisa de validação em outras GPUs.

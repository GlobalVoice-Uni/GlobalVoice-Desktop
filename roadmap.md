# Roadmap — Global Voice (PFC 2)

> Revisado em 13 de outubro de 2026. Os próximos marcos agrupam funcionalidades
> que antes estavam espalhadas pelas Entregas 2 a 6. Cada marco termina com uma
> build testável e um registro objetivo de resultados em `docs/`.

## Objetivo

O Global Voice traduz reuniões no Windows sem depender da plataforma de chamada:

- **Reunião → usuário:** captura do áudio do sistema, transcrição e tradução em
  texto; reprodução da tradução em voz quando habilitada.
- **Usuário → reunião:** captura do microfone, transcrição, tradução e síntese de
  voz enviada a um dispositivo de áudio virtual.

O núcleo funciona localmente. O primeiro par é português ↔ inglês; espanhol já
está disponível para tradução direta em texto. A tradução usa **Argos**, escolhido
após a comparação automatizada com M2M-100 FP32 e INT8, registrada em
[`docs/entrega-2-relatorio-comparacao-tradutores.md`](docs/entrega-2-relatorio-comparacao-tradutores.md).
Os modelos são baixados durante a instalação ou em **Configurações > Idiomas**.

## Marcos concluídos

### Entrega 0 — Base e método

- [x] Preservar o protótipo do PFC 1 e organizar o código em interface, bridge e
  backend.
- [x] Criar testes automatizados, corpus e medições reproduzíveis.
- [x] Definir refatorações incrementais protegidas por regressão.

### Entrega 1 — Base instalável

- [x] Capturar microfone e transcrever com Faster-Whisper, VAD Silero e fallback
  por energia.
- [x] Usar GPU NVIDIA quando disponível e CPU como fallback silencioso.
- [x] Distribuir a aplicação em `onedir` com instalador Inno Setup e componente
  CUDA opcional.
- [x] Validar build, instalação e desinstalação em outra máquina.
- [x] Integrar a home, a toolbar e a janela flutuante já utilizadas.

Detalhes e medições permanecem em `docs/entrega-1-*.md`.

## Entrega 2 — Escuta traduzida e distribuição dos idiomas

**Estado:** fluxo principal implementado; fechamento do instalador e validação
de sessões prolongadas em andamento.

- [x] Capturar o áudio do sistema e executar `loopback → VAD → STT → Argos` em
  sessão cancelável.
- [x] Mostrar a via `Reunião` como tradução, original ou ambos; tradução é o
  padrão.
- [x] Traduzir diretamente entre português, inglês e espanhol, sem idioma
  intermediário.
- [x] Comparar Argos e M2M com corpus fixo e registrar método, resultados e
  escolha em relatório separado deste roadmap.
- [x] Selecionar idioma principal e pares na mesma página do instalador; permitir
  alterar a base, instalar e remover pares nas configurações.
- [x] Baixar modelos somente quando escolhidos, mantendo os pacotes fora do
  instalador.
- [x] Confirmar manualmente que transcrição e tradução continuam funcionando
  sem rede após a instalação dos pacotes.
- [ ] Consolidar os downloads dos pares em uma única tela do assistente e validar
  o comportamento visual em uma instalação real.
- [ ] Confirmar ícone novo no executável, janelas, atalhos e lista de aplicativos,
  inclusive após atualizar uma instalação anterior.
- [ ] Medir latência por etapa e estabilidade em sessão prolongada, em condições
  representativas do hardware do grupo.
- [ ] Fechar uma build identificada, executar a suíte e testar instalação,
  tradução offline e desinstalação em outra máquina.

**Aceite:** o áudio de uma reunião aparece traduzido no idioma escolhido, com
origem e destino configuráveis. A instalação dos pares funciona sem preparar
Python ou modelos manualmente. Limites de qualidade e latência ficam em `docs/`.

## Entrega 3 — Voz traduzida e operação bidirecional

Esta entrega reúne a antiga via de fala e a antiga etapa de operação simultânea.
O primeiro cenário completo continua sendo português ↔ inglês.

- [ ] Escolher um TTS por teste curto de qualidade, latência, licença e tamanho
  de distribuição; registrar a decisão.
- [ ] Implementar `SpeechSynthesizerPort` e `AudioSinkPort` e executar
  `microfone → VAD → STT → Argos → TTS → dispositivo virtual`.
- [ ] Enviar a voz traduzida a uma chamada de teste e mostrar a via `Você` na
  janela flutuante.
- [ ] Executar as vias `Reunião` e `Você` na mesma sessão, com filas, estados,
  controles e cancelamento independentes.
- [ ] Reproduzir a tradução recebida nos fones como opção; impedir que o áudio
  sintetizado seja recapturado e entre em loop.
- [ ] Tratar fala simultânea, troca de dispositivo e encerramento seguro de
  streams e modelos.
- [ ] Validar o dispositivo virtual, a latência ponta a ponta e o comportamento
  sob carga com teste automatizado onde possível e chamada real no fechamento.

**Aceite:** a voz do usuário chega traduzida à chamada e a tradução da reunião
continua funcionando ao mesmo tempo, sem loop sustentado ou travamento.

## Entrega 4 — Integração visual e versão final

A branch `front_eric` contém trabalho visual que ainda não está integrado. Ela
diverge da atual em backend, instalador e interface; por isso a integração será
**seletiva**, depois de estabilizar o fluxo bidirecional. A interface já presente
na branch de entrega permanece como base funcional.

- [ ] Auditar diferenças visuais de `front_eric` e portar apenas telas, estilos e
  interações compatíveis, com testes de regressão para os fluxos existentes.
- [ ] Persistir posição e tamanho das janelas e validar leitura, contraste e
  navegação por teclado.
- [ ] Congelar dependências, executar uma instalação limpa, validar atualização e
  desinstalação, inclusive nos perfis CPU e NVIDIA disponíveis.
- [ ] Verificar licença e distribuição do dispositivo virtual antes de incluí-lo
  no instalador.
- [ ] Finalizar guia de uso, privacidade, solução de problemas e diagnóstico de
  áudio/dispositivos.
- [ ] Consolidar no relatório acadêmico método, medições, limitações e uma
  demonstração principal com alternativa reproduzível por áudio gravado.

**Aceite:** outra pessoa instala, configura, usa e remove a aplicação com um guia
curto. Código, testes e resultados reproduzem a demonstração apresentada.

## O que ficou fora destes marcos

As ideias abaixo deixam de bloquear a versão de PFC 2. Só voltam ao escopo se
uma medição ou requisito concreto justificar o trabalho:

- M2M-100 como motor de produção: a comparação terminou com escolha do Argos.
- Nova comparação ampla de STT, aceleração genérica por AMD/Intel e transcrição
  remota em VM: podem ser estudos futuros, sem trocar o pipeline atual.
- Tradução incremental com Whisper-Streaming, revisão textual local, glossário
  e múltiplas hipóteses: considerar apenas se um erro medido impedir o aceite.
- Mandarim, histórico de sessões, exportação TXT/JSON/SRT e seleção avançada de
  vozes: expansões após o núcleo bidirecional.
- Substituição integral do front-end: aproveitar seletivamente o trabalho da
  branch visual e preservar os fluxos já validados.

## Validação contínua

- Executar testes automatizados em alterações relevantes e acrescentar regressão
  para defeitos corrigidos.
- Medir separadamente captura, STT, tradução, TTS e reprodução; registrar
  hardware, modelos, versões e condições dos ensaios.
- Testar em sessões prolongadas e em pelo menos duas plataformas de reunião.
- Acompanhar abertura, tamanho instalado e consumo de CPU, RAM e GPU.
- Documentar resultados positivos e negativos em `docs/`, com o relatório de
  comparação de tradutores separado deste planejamento.

## Critério de conclusão

O objetivo acadêmico é verificar a viabilidade da tradução bidirecional local.
Se os dois fluxos operarem juntos, apresentar qualidade, latência e estabilidade
medidas. Se algum componente não for viável nas condições testadas, entregar o
código e os experimentos, identificar o gargalo com medições reproduzíveis e
explicitar o alcance da validação parcial.

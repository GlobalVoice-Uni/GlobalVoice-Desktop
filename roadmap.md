# Roadmap — Global Voice (PFC 2)

> Atualizado em 7 de outubro de 2026.

## Visão do produto

O **Global Voice** é um aplicativo desktop para Windows que funciona em segundo
plano durante reuniões realizadas em plataformas como Teams, Discord, Skype,
Zoom ou Google Meet. Ele atua na camada de áudio do computador do usuário, sem
depender de integração específica com a plataforma de chamada.

O produto terá dois fluxos principais:

- **reunião → usuário:** capturar o áudio reproduzido pelo sistema, transcrever,
  traduzir e apresentar a tradução por texto e, quando habilitado, por voz;
- **usuário → reunião:** capturar o microfone, transcrever, traduzir, sintetizar
  a fala e enviá-la à chamada por um dispositivo de áudio virtual.

Na janela flutuante, o modo padrão será **mostrar somente a tradução**. Nas
configurações, o usuário poderá escolher entre:

1.  somente tradução;
2.  somente transcrição original;
3.  transcrição original e tradução.

O primeiro par de idiomas do PFC 2 será **português ↔ inglês**.

A validação principal será feita com os modelos executando localmente. A execução
remota poderá ser testada como comparação e alternativa para máquinas com poucos
recursos, sem substituir o objetivo local do projeto.

## Marco entregue — PFC 1

- [x] Aplicação desktop inicial em Python e PySide6.
- [x] Captura contínua do microfone físico.
- [x] Transcrição local com Faster-Whisper.
- [x] Exploração inicial de transcrição e tradução com Whisper.
- [x] Execução em GPU e alternativa em CPU.
- [x] VAD com Silero e fallback por energia.
- [x] Segmentação por fala e silêncio.
- [x] Tratamento de fronteiras com overlap, tail guard e deduplicação.
- [x] Interface com home, toolbar e janela flutuante.
- [x] Configurações persistentes com `QSettings`.
- [x] Separação inicial entre interface, bridge e backend.
- [x] Protótipo específico da apresentação preservado em branch histórica.

## Componentes técnicos previstos

Os nomes abaixo representam contratos de implementação e podem ser ajustados
durante a revisão técnica:

- `AudioSourcePort`: fonte de áudio genérica para microfone ou loopback;
- `TranscriberPort`: contrato já existente para o motor de transcrição;
- `TranslatorPort`: tradução de texto com idiomas de origem e destino;
- `SpeechSynthesizerPort`: geração de áudio a partir do texto traduzido;
- `AudioSinkPort`: reprodução em fones, alto-falantes ou dispositivo virtual.

Esses contratos devem permitir comparar ou substituir tecnologias sem
reescrever toda a aplicação. Também devem aceitar adapters locais ou remotos por
meio da bridge já existente.

## Entrega 0 — Preparação da base

**Execução imediata.**

- [x] Atualizar a `main` local a partir da `main` remota.
- [x] Executar e validar a aplicação atual após a atualização.
- [x] Limpar referências de branches antigas já incorporadas ou removidas,
  preservando apenas a branch histórica da apresentação.
- [x] Adotar a `main` atual como base para o novo front-end.
- [x] Evitar portar o front-end completo da branch de apresentação.
- [x] Delimitar os comportamentos pequenos e isoláveis que poderão ser avaliados
  para reaproveitamento sem trazer dependências da demonstração:
  - exibição gradual palavra a palavra;
  - quebra visual por silêncio;
  - ajustes de tamanho, leitura e comportamento da janela flutuante;
  - agrupamento visual adaptado para `Reunião` e `Você`.
- [x] Atualizar o README para apontar para este roadmap e retirar o roadmap antigo.
- [x] Criar a estrutura de testes unitários e de integração.
- [x] Definir um comando único para executar automaticamente os testes a cada
  atualização.
- [x] Identificar pontos que precisam de refatoração antes de ampliar o produto.
- [x] Evitar uma refatoração ampla enquanto não houver testes de regressão para
  proteger o comportamento já funcional.

**Critério de aceite:** a base atual continua funcionando, a documentação está
alinhada ao PFC 2 e existe uma estrutura mínima de testes automatizados.

## Entrega 1 — Base distribuível e decisões iniciais

**Duração: 2 semanas.**

**Estado:** concluída e disponibilizada como pré-versão `v0.1.0`. As pesquisas
comparativas que não bloquearam a primeira distribuição foram realocadas para as
trilhas contínuas e para as entregas em que serão aplicadas.

### Marco imediato — executável de validação

A primeira build deve existir no início da entrega para permitir avaliações dos
instrutores e do grupo sem exigir terminal ou ambiente Python. As demais provas de
conceito continuam depois desse marco.

- [x] Gerar uma build Windows `onedir` a partir da base atualmente funcional.
- [x] Abrir a aplicação pela build sem depender do Python instalado na máquina.
- [x] Selecionar automaticamente uma GPU NVIDIA compatível com o motor atual e
  usar CPU como fallback sem exibir warnings técnicos ao usuário.
- [x] Documentar o comportamento do primeiro download do modelo e os requisitos de
  aceleração por GPU.
- [x] Medir tempo de abertura e tamanho do pacote inicial.
- [x] Regenerar a build a partir de uma venv limpa e incluir o Silero VAD
  principal no pacote.
- [x] Detectar a ausência das bibliotecas CUDA antes da primeira inferência e
  mostrar CPU como dispositivo ativo em vez de interromper a sessão.
- [x] Criar um perfil NVIDIA provisório somente com cuBLAS, separado do runtime
  usado pelo Silero.
- [x] Validar manualmente uma transcrição GPU pela build com perfil NVIDIA usando
  Silero VAD e o detector por energia.
- [x] Enviar a build para pelo menos uma pessoa externa ao ambiente de
  desenvolvimento e registrar o resultado.

**Medição inicial:** pasta com 557,17 MB e janela principal disponível em 2,94 s
no ambiente de desenvolvimento. A build com Silero e PyTorch CPU ocupava
1.185,94 MB; o antigo perfil NVIDIA provisório ocupava 1.937,80 MB. O Silero foi
migrado para ONNX sem PyTorch, e o novo perfil NVIDIA validado com fala real ocupa
1.309,96 MB. A build deduplicada validada ocupa 1.149,48 MB. Após o corte do Qt e
a separação do perfil CUDA, a base ocupa 354,01 MB e a instalação NVIDIA completa
ocupa 1.105,92 MB.

**Validação externa inicial:** o instalador foi executado fora do ambiente de
desenvolvimento e manteve instalação, seleção de perfil, transcrição e
desinstalação funcionais. Os dados das máquinas e eventuais limitações serão
consolidados nas notas da primeira versão.

### Transcrição em tempo real

- [x] Adotar GPU como preferência padrão e separar a preferência do dispositivo
  realmente ativo na sessão.
- [x] Criar contratos de hardware e runtime que não dependam de um único motor ou
  fabricante de GPU.
- [x] Confirmar o Silero VAD como detector principal e manter o detector por
  energia apenas como fallback de segurança.
- [x] Validar pelo menos uma GPU NVIDIA legada, uma NVIDIA recente, uma AMD
  dedicada ou integrada e o fallback em uma máquina sem GPU suportada.
- [x] Medir o tempo atual do pipeline no hardware do grupo para criar uma **linha de
  base**: um valor de referência que permita saber objetivamente se as mudanças
  seguintes melhoraram ou pioraram o sistema.

### Front-end e distribuição

A branch do novo design será auditada e integrada de forma seletiva sobre a base
validada. Comparações práticas com outras tecnologias de interface continuam fora
desta entrega para evitar uma segunda implementação concorrente.

- [x] Auditar e fixar as dependências de execução em uma venv limpa, incluindo o
  Silero VAD, e separar os requisitos de runtime, testes e build.
- [x] Isolar o Silero em ONNX, comparar seu comportamento com a implementação
  anterior e remover PyTorch e Torchaudio do runtime.
- [x] Validar a build que elimina cópias idênticas de DLLs do CTranslate2, PyAV,
  NumPy e SciPy.
- [x] Validar a build de 1.105,87 MB sem os componentes Qt não usados pela
  interface atual.
- [x] Definir como distribuir cuBLAS somente no perfil NVIDIA sem aumentar a base
  instalada para usuários de CPU, AMD ou Intel.
- [x] Criar um instalador Inno Setup que instale a base em CPU e o perfil de GPU
  adequado ao hardware detectado, sem exigir configuração manual do usuário.
- [x] Validar manualmente o fluxo visual do instalador, os atalhos, a execução do
  aplicativo instalado e a remoção completa.
- [x] Avaliar teoricamente se PySide6 continua adequado, considerando tempo de
  abertura, consumo, integração com Windows, suporte a overlay e custo de
  reescrita, sem criar implementações concorrentes nesta entrega.
- [x] Comparar conceitualmente duas abordagens de interface e registrar a escolha:
  - duas janelas flutuantes vinculadas, uma para o texto e outra para a toolbar;
  - uma camada de sobreposição com regiões interativas e passagem de cliques
    para os aplicativos atrás dela.
- [x] Adotar para a primeira versão a distribuição `onedir` empacotada por um
  instalador Inno Setup.
- [x] Adotar refatoração incremental protegida por testes, evitando substituir
  módulos funcionais sem uma necessidade comprovada.
- [x] Auditar a branch do novo front-end, separando elementos visuais de arquivos
  legados, controles ainda sem backend e alterações incompatíveis com a base.
- [x] Integrar seletivamente a toolbar e a janela de transcrição do novo design,
  preservando o status real de GPU/CPU e o ciclo de sessão já validado.
- [x] Refazer o design base das telas, mantendo uma identidade visual simples,
  moderna e coerente com a proposta do aplicativo.
- [x] Permitir escolher entre detecção automática por VAD e apertar para falar,
  sem recarregar o motor a cada fala.

### Primeira versão para testes

- [x] Confirmar a versão `v0.1.0` e preparar notas de versão com requisitos,
  comportamento do primeiro download do modelo e limitações conhecidas.
- [x] Gerar o instalador final e seu checksum SHA-256 a partir do estado aprovado.
- [x] Fazer uma última instalação limpa e validar abertura, transcrição,
  dispositivo ativo, atalhos e desinstalação.
- [x] Publicar no GitHub uma pré-versão destinada a testes, contendo o instalador,
  o checksum e as notas de versão.

**Critério de aceite:** a base executável mantém a transcrição validada, a suíte
automatizada está aprovada e a primeira versão pode ser instalada por usuários
externos a partir de uma pré-versão do GitHub, com limitações conhecidas
documentadas.

## Entrega 2 — Via de escuta em texto

**Duração: 2 semanas.**

**Estado:** em andamento. A captura do áudio do sistema, a transcrição, a
tradução local inicial e a interface dos três modos de exibição já foram
integradas e validadas. A prioridade restante é decidir o motor de tradução,
medir o fluxo completo e estabilizar seu comportamento em sessões prolongadas.

- [x] Generalizar a fonte de áudio sem quebrar a captura atual do microfone.
- [x] Enumerar dispositivos de entrada, saída e loopback disponíveis no Windows.
- [x] Capturar uma amostra verificável do áudio do sistema via WASAPI loopback.
- [x] Implementar a captura loopback do áudio da reunião.
- [x] Integrar o motor de transcrição selecionado na Entrega 1.
- [x] Manter captura e VAD ativos durante o STT, medindo o fator de tempo real e
  a espera acumulada antes de cada transcrição.
- [x] Implementar `TranslatorPort` e o primeiro adaptador de tradução local com
  CTranslate2, SentencePiece e modelos no formato Argos.
- [x] Executar o fluxo `loopback → VAD → STT → tradução` em uma sessão cancelável.
- [x] Exibir o conteúdo da via de escuta sob o canal `Reunião`, sem exigir
  identificação automática de cada participante.
- [x] Implementar os três modos de exibição:
  - [x] somente tradução, selecionado por padrão;
  - [x] somente transcrição original;
  - [x] transcrição original e tradução.
- [x] Permitir selecionar dispositivo, idioma de origem e idioma de destino.
- [x] Oferecer no instalador os pacotes de tradução iniciais, com português como
  base, inglês selecionado por padrão e espanhol opcional.
- [x] Permitir instalar e desinstalar pacotes de tradução em
  `Configurações > Idiomas`, sem download silencioso e sem incorporá-los ao
  executável principal.
- [x] Exibir estados de carregamento, dispositivo indisponível e falha do motor ou
  provedor.

### Decisão do motor de tradução

**Referência de tamanho:** os pacotes atuais ocupam aproximadamente 156,66 MiB
para inglês ↔ português e 138,66 MiB para espanhol ↔ português. O checkpoint
oficial do M2M-100 418M em precisão original ocupa cerca de 1,94 GB; a estimativa
próxima de 500 MB se refere a uma conversão quantizada, cujo tamanho real ainda
deve ser medido no formato de distribuição do Global Voice.

- [x] Validar o primeiro fluxo offline com modelos direcionais no formato Argos.
- [x] Identificar a limitação de crescimento por pares: cada nova combinação de
  idiomas exige modelos próprios nos dois sentidos.
- [x] Rejeitar o uso do português como idioma intermediário entre outros pares,
  pois acrescenta latência e pode acumular perdas de qualidade.
- [ ] Preparar uma prova de conceito do M2M-100 418M convertido para CTranslate2 e
  quantizado, sem substituir o adaptador atual antes da comparação.
- [ ] Disponibilizar temporariamente, nas configurações de teste, os motores
  `Argos direcional`, `M2M-100 FP32` e `M2M-100 INT8`, carregando apenas o motor
  selecionado na memória.
- [ ] Gerar uma distribuição de laboratório separada da versão pública, com nome,
  diretório e configurações próprios, para não sobrescrever a instalação estável.
- [ ] Distribuir os modelos grandes como componentes opcionais ou instaladores de
  modelos separados, permitindo que a equipe faça os testes sem preparar Python,
  dependências ou comandos manualmente.
- [ ] Comparar Argos e M2M-100 nos seis sentidos entre português, inglês e
  espanhol, usando o mesmo corpus e o mesmo hardware.
- [ ] Medir tamanho em disco, memória, tempo de carregamento, latência por trecho,
  uso de CPU/GPU e qualidade da tradução.
- [ ] Avaliar especialmente concordância, paralelismo verbal, termos técnicos,
  frases incompletas e traduções diretas sem idioma intermediário.
- [ ] Registrar em `docs/entrega-2-avaliacao-tradutores.md` o corpus, método,
  versões, hardware, parâmetros, saídas, medições, avaliação humana e conclusão.
- [ ] Decidir qual motor será principal, alternativo ou descartado e somente então
  revisar os componentes de idiomas do instalador e remover código, dependências,
  modelos, testes e referências das alternativas rejeitadas.

### Estabilização e fidelidade textual

Esta frente não deve apagar hesitações, pedidos de correção ou qualquer conteúdo
que tenha sido efetivamente falado. O objetivo é reduzir instabilidade visual e
melhorar a coerência linguística sem mudar o sentido do enunciado.

- [ ] Separar cada fala em prefixo confirmado e trecho provisório, mantendo apenas
  a cauda recente como mutável.
- [ ] Exibir hipóteses provisórias com menor destaque visual e promover para texto
  confirmado apenas as palavras estáveis entre atualizações sucessivas.
- [ ] Avaliar uma estratégia inspirada no Whisper-Streaming para hipóteses
  incrementais, medindo o custo de retranscrever janelas sobrepostas com
  Faster-Whisper.
- [ ] Enviar para a tradução somente unidades confirmadas e permitir revisão, no
  máximo, do último fragmento ainda aberto.
- [ ] Investigar uma revisão linguística local e leve que compare original e
  tradução, preservando todas as informações faladas e corrigindo incoerências
  como concordância e paralelismo verbal.
- [ ] Comparar pós-processamento, tradução com contexto maior e seleção entre
  múltiplas hipóteses do tradutor antes de escolher a abordagem.
- [ ] Medir separadamente ganho de qualidade, alterações indevidas e latência
  acrescentada; permitir desativar o recurso caso ele seja adotado.

### Execução remota comparativa

Esta comparação complementa a validação em máquinas limitadas, mas não substitui
nem bloqueia a conclusão do fluxo local, que continua sendo o objetivo principal.

- [ ] Criar uma prova de conceito de transcrição remota em uma VM conectada pela
  bridge.
- [ ] Comparar transcrição local e remota com os mesmos áudios, medindo qualidade,
  tempo de processamento, latência total incluindo rede e consumo de recursos na
  máquina do usuário.
- [ ] Registrar em quais condições a execução remota supera a local e quais
  dependências, custos e riscos de privacidade ela acrescenta.

**Critério de aceite:** ao reproduzir uma chamada, vídeo ou áudio de teste, o
Global Voice captura o som do sistema e mostra por padrão a tradução no idioma do
usuário; os outros dois modos podem ser selecionados nas configurações. O motor
de tradução escolhido e as limitações de qualidade, latência e idiomas ficam
registrados com resultados reproduzíveis.

## Entrega 3 — Via de fala em áudio

**Duração: 2 semanas.**

- [ ] Comparar opções de TTS por latência, naturalidade, estabilidade, licença,
  idiomas suportados e forma de distribuição.
- [ ] Registrar a escolha inicial de TTS antes de integrá-la ao fluxo principal.
- [ ] Implementar `SpeechSynthesizerPort` e `AudioSinkPort`.
- [ ] Executar o fluxo `microfone → VAD → STT → tradução → TTS`.
- [ ] Produzir e validar uma amostra de fala com a tecnologia de TTS escolhida na
  própria entrega.
- [ ] Enviar o áudio sintetizado para o dispositivo virtual.
- [ ] Confirmar que uma plataforma de chamada reconhece essa saída como microfone.
- [ ] Exibir o conteúdo dessa via sob o canal `Você` de acordo com o modo de
  exibição selecionado.
- [ ] Reaproveitar o modo pressionar-para-falar na futura via de voz traduzida.
- [ ] Permitir cancelar uma fala pendente e silenciar imediatamente a saída virtual.
- [ ] Tratar indisponibilidade do provedor ou dispositivo sem travar a aplicação.

**Critério de aceite:** uma frase falada em português é traduzida e ouvida em
inglês dentro de uma chamada de teste ou em uma gravação feita a partir do
microfone virtual.

## Entrega 4 — Operação bidirecional

**Duração: 2 semanas.**

- [ ] Executar as vias de escuta e fala simultaneamente sem bloquear a interface.
- [ ] Separar filas, estados e cancelamento de cada via.
- [ ] Reproduzir nos fones a tradução da via de escuta quando essa opção estiver
  habilitada.
- [ ] Evitar que o TTS seja recapturado e traduzido novamente.
- [ ] Definir a política para fala simultânea, prioridade e interrupção.
- [ ] Adicionar controles independentes para escuta, microfone e vozes sintetizadas.
- [ ] Recuperar a sessão após troca ou desconexão de um dispositivo.
- [ ] Encerrar corretamente threads, streams, filas e modelos.

**Critério de aceite:** as duas vias funcionam na mesma sessão de teste sem loop
sustentado de áudio, travamento ou necessidade de reiniciar a aplicação.

## Entrega 5 — Consolidação da interface e experiência de uso

**Duração: 2 semanas.**

O novo front-end deve evoluir junto com as entregas anteriores. Esta etapa
consolida a interface completa, em vez de iniciar seu desenvolvimento somente
neste ciclo.

- [x] Consolidar o novo front-end sobre a base validada, usando a tecnologia
  escolhida na Entrega 1.
- [x] Manter uma home normal para início, configuração e encerramento da aplicação.
- [x] Implementar a janela flutuante de texto e a toolbar conforme a abordagem
  escolhida na Entrega 1.
- [x] Permitir mover, redimensionar e manter a área de texto sempre no topo.
- [ ] Persistir posição, tamanho e preferências de exibição.
- [x] Disponibilizar na toolbar os controles rápidos de iniciar/parar, idiomas,
  configurações, pressionar-para-falar e mostrar/ocultar texto.
- [x] Definir e implementar o ciclo de vida das janelas:
  - [x] fechar a janela de texto apenas oculta essa janela;
  - [x] a toolbar permite reabrir a janela de texto;
  - [x] fechar a home encerra as janelas e os processos, com confirmação quando
    existe sessão ativa ou configuração não salva.
- [x] Separar configurações por finalidade e manter os parâmetros técnicos fora
  dos controles rápidos da toolbar.
- [x] Exibir claramente idiomas, dispositivos, canais ativos e estado de cada
  pipeline.
- [x] Implementar mensagens de erro que indiquem como o usuário pode corrigir o
  problema.
- [ ] Validar contraste, tamanho de fonte e uso por teclado.

**Critério de aceite:** uma pessoa externa ao grupo consegue configurar e
controlar uma chamada usando apenas a interface e um guia curto.

## Entrega 6 — Consolidação e apresentação final

**Duração: 2 semanas.**

O empacotamento não começa nesta entrega: builds intermediárias devem ser
geradas desde a Entrega 1. Esta etapa consolida o processo já testado.

- [ ] Estabilizar a forma de empacotamento escolhida.
- [ ] Gerar uma versão identificada e congelar as dependências.
- [ ] Definir a estratégia de assinatura de código do instalador e do executável.
- [ ] Criar diagnóstico de pré-requisitos e dispositivos de áudio.
- [ ] Verificar licença e forma permitida de instalação do dispositivo virtual
  antes de incorporá-lo ao instalador.
- [ ] Testar a aplicação em uma máquina limpa.
- [ ] Finalizar guia de instalação, uso, privacidade e solução de problemas.
- [ ] Consolidar diagramas, resultados, limitações e decisões técnicas no relatório.
- [ ] Preparar roteiro de demonstração principal.
- [ ] Preparar demonstração alternativa com áudios gravados e resultados
  reproduzíveis.

**Critério de aceite:** a versão final e seus experimentos podem ser reproduzidos
fora do ambiente de desenvolvimento do grupo.

## Trilhas contínuas

Estas atividades começam na Entrega 0 e acompanham todas as demais. Elas não
correspondem a apenas duas semanas.

### Testes e regressão

- [ ] Executar testes automatizados em toda alteração relevante.
- [ ] Revalidar o atraso acumulado em sessão prolongada, com microfone e sob
  carga representativa, após integrar a tradução.
- [ ] Criar testes unitários para VAD, deduplicação, tail guard, reconciliação e
  regras de exibição.
- [ ] Usar adapters falsos nos testes para não depender de hardware ou serviços
  externos.
- [ ] Criar testes de integração com arquivos WAV conhecidos.
- [ ] Acrescentar um teste de regressão sempre que um defeito for corrigido.
- [ ] Registrar falhas conhecidas em vez de ocultá-las para a apresentação.

### Builds e desempenho

- [ ] Gerar uma build utilizável ao final de cada entrega, começando na Entrega 1.
- [ ] Acompanhar tempo de abertura, tamanho do pacote e consumo de memória.
- [ ] Testar periodicamente em outra máquina do grupo.
- [ ] Definir requisitos separados de desenvolvimento e de cada perfil de
  aceleração depois da escolha dos provedores de GPU.
- [ ] Automatizar build, instalação silenciosa, desinstalação e smoke test em CPU
  no GitHub Actions; executar os testes de GPU em máquinas com hardware real.
- [ ] Evitar deixar decisões de instalador, driver ou empacotamento para o último
  ciclo.

### Pesquisa de motores e aceleração

- [ ] Comparar provedores de aceleração para Windows: CUDA em NVIDIA,
  DirectML/WinML em NVIDIA, AMD e Intel, e ROCm nas GPUs AMD oficialmente
  suportadas.
- [ ] Pesquisar motores de STT projetados para streaming ou transcrição em tempo
  real e compará-los com o Faster-Whisper usando os mesmos áudios e hardware.
- [ ] Avaliar qualidade textual, latência, consumo de CPU/GPU, suporte a idiomas,
  licença e facilidade de distribuição.
- [ ] Decidir se o Faster-Whisper continuará como motor principal, fallback ou
  referência de comparação.
- [ ] Repetir a linha de base com a máquina livre e sob carga representativa para
  medir perda de velocidade ou qualidade por disputa de recursos.

### Validação acadêmica

- [ ] Montar um corpus português/inglês com fala limpa, ruído, sotaques e termos
  técnicos.
- [ ] Registrar hardware, versões, modelos, parâmetros e condições de cada
  experimento.
- [ ] Medir separadamente latência de captura, STT, tradução, TTS e reprodução.
- [ ] Comparar os resultados locais com a execução remota em VM, quando o
  experimento estiver disponível.
- [ ] Comparar texto de referência, transcrição e tradução produzida.
- [ ] Avaliar a tradução por revisão humana quanto a sentido, fluidez e termos
  técnicos.
- [ ] Realizar testes de ponta a ponta em pelo menos duas plataformas de reunião.
- [ ] Atualizar o relatório durante o desenvolvimento com resultados positivos e
  negativos.

## Cronograma

- As entregas completas ocorrerão em ciclos de **duas semanas**.
- O grupo fará acompanhamento semanal e poderá apresentar progresso parcial nas
  reuniões intermediárias.
- A Entrega 0 antecede os ciclos quinzenais.
- Testes, validação, documentação e builds acompanharão todas as entregas.
- O planejamento deverá manter uma margem antes da apresentação final, prevista
  para o início ou meados de dezembro.

|Ciclo     |Entrega  |Resultado principal                          |
|----------|---------|---------------------------------------------|
|Preparação|Entrega 0|Base, documentação e testes iniciais         |
|1         |Entrega 1|Base instalável e primeira pré-versão         |
|2         |Entrega 2|Áudio da reunião traduzido em texto          |
|3         |Entrega 3|Voz do usuário traduzida dentro da chamada   |
|4         |Entrega 4|Operação bidirecional                        |
|5         |Entrega 5|Interface e experiência consolidadas         |
|6         |Entrega 6|Versão, evidências e apresentação final      |


## Metas iniciais de qualidade

As metas serão recalibradas depois das medições da Entrega 1.

- Manter uma sessão contínua de 30 minutos sem falha fatal.
- Exibir o texto traduzido em até 5 segundos após o fim do enunciado em pelo
  menos 95% das amostras.
- Iniciar a voz traduzida em até 8 segundos após o fim do enunciado em pelo
  menos 95% das amostras.
- Não produzir loop sustentado pela recaptura do próprio TTS.
- Interromper ou silenciar a saída em até 1 segundo após o comando do usuário.
- Demonstrar funcionamento em pelo menos duas plataformas sem código específico
  para elas.
- Definir na Entrega 1 uma meta de tempo de abertura e acompanhá-la em todas as
  builds.

## Riscos acompanhados


|Risco                                                               |Tratamento previsto                                                            |
|--------------------------------------------------------------------|-------------------------------------------------------------------------------|
|O motor de STT não sustenta qualidade e latência em tempo real      |Comparar alternativas cedo e registrar limites com o mesmo corpus e hardware   |
|Loopback varia conforme dispositivo e driver                        |Validar dispositivos reais, permitir seleção e documentar fallback             |
|O dispositivo virtual dificulta instalação ou distribuição          |Verificar compatibilidade e licença desde a Entrega 1                          |
|O TTS é recapturado pelo loopback                                   |Separar rotas, controlar reprodução e testar realimentação continuamente       |
|As latências das etapas se acumulam                                 |Medir cada etapa e otimizar o gargalo comprovado                               |
|Uma troca ampla de front-end ou refatoração quebra o que já funciona|Prototipar, criar regressão e substituir módulos de forma controlada           |
|APIs externas afetam custo, privacidade ou disponibilidade          |Manter contratos substituíveis, timeouts e documentação do fluxo de dados      |
|O empacotamento funciona apenas no ambiente dos autores             |Produzir builds intermediárias e testar em máquinas limpas antes do ciclo final|

## Expansões após o núcleo bidirecional

- [ ] Adicionar mandarim como próximo idioma prioritário e validar com materiais
  gravados, registrando a ausência de avaliação por falante nativo caso ela não
  seja possível.
- [ ] Avaliar espanhol depois do mandarim ou quando houver capacidade adicional de
  testes.
- [ ] Exportar sessões em TXT, JSON e SRT.
- [ ] Adicionar histórico local somente com consentimento explícito.
- [ ] Permitir seleção de vozes e velocidade do TTS.
- [ ] Adicionar glossário de termos técnicos.
- [ ] Avaliar modo automático de fala após estabilizar o pressionar-para-falar.
- [ ] Substituir o dicionário demonstrativo por uma solução mais robusta e leve,
  validada nos idiomas suportados.

## Critério de conclusão do PFC 2

O objetivo do projeto é tentar validar tecnicamente a proposta do Global Voice.
O resultado acadêmico não depende de todas as funcionalidades atingirem
desempenho ideal.

### Cenário A — proposta validada

- [ ] A fala remota é capturada, transcrita e traduzida na interface.
- [ ] A fala local é transcrita, traduzida, sintetizada e recebida pela reunião.
- [ ] Os dois fluxos operam na mesma sessão sem realimentação sustentada.
- [ ] A aplicação pode ser instalada, configurada e encerrada de forma segura.
- [ ] Qualidade, latência, estabilidade e limitações são medidas e documentadas.

### Cenário B — proposta parcialmente validada ou tecnicamente inviável nas condições avaliadas

- [ ] Os componentes construídos e os experimentos realizados estão documentados.
- [ ] O ponto de inviabilidade é identificado por medições reproduzíveis.
- [ ] As alternativas testadas e seus resultados são registrados.
- [ ] As limitações de hardware, software, custo ou latência são explicitadas.
- [ ] O relatório apresenta o que funcionou, o que não funcionou e por que a
  hipótese foi parcial ou totalmente rejeitada.

Em ambos os cenários, o projeto deve entregar código, testes, método
experimental, resultados e conclusões coerentes com as evidências obtidas.

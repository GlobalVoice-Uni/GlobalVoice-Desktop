# Auditoria do front-end — Entrega 1

## Origem analisada

- branch remota: `front_eric`;
- commits analisados: `30c5632` e `a737bc2`;
- base comum com a Entrega 1: `8b99044`.

A branch foi criada antes das mudanças de compatibilidade, runtime, dependências,
build e instalador. Por isso, sua integração integral sobrescreveria correções já
validadas e não foi adotada.

## Conteúdo aproveitado

- composição compacta da toolbar em formato de cápsula;
- seletor visual de idiomas e controle único para iniciar ou parar;
- ícones vetoriais desenhados pelo Qt para configurações, chat, limpeza,
  microfone e ações da sessão;
- botão para ocultar ou reabrir a janela de transcrição sem encerrar a sessão;
- aparência da janela de texto e preparação para mensagens por canal;
- persistência da posição da janela de transcrição;
- conceito visual do botão de apertar para falar.

O conceito de apertar para falar foi conectado ao pipeline atual. A sessão mantém
o motor carregado, mas descarta os blocos capturados enquanto o botão não está
pressionado. O modo padrão continua sendo a detecção automática pelo VAD.

## Conteúdo não integrado

- diretórios `__pycache__` e arquivos `.pyc`, pois são caches locais;
- `GlobalVoice.spec`, porque contém caminhos absolutos da máquina de origem e
  duplicaria a receita oficial em `deploy/windows/globalvoice.spec`;
- `test_loopback.py`, porque introduz `pyaudiowpatch` fora da estrutura de
  experimentos e pertence à investigação de áudio da Entrega 2;
- alteração de `frontend/requirements.txt` para uma faixa aberta de PySide6,
  preservando a versão validada e fixada pelo projeto;
- controles de tradução, TTS, loopback e dispositivo virtual que ainda não
  possuem implementação no backend;
- documentação que apresentava recursos futuros como se já estivessem ativos.

## Incompatibilidades corrigidas ou evitadas

- O `controller.py` remoto estava reduzido a um trecho incompleto e removia a
  criação da thread, o início e a parada da sessão e a publicação do runtime.
- A bridge remota retirava o callback que informa se GPU ou CPU está realmente
  ativa e adicionava campos futuros ainda sem consumidores.
- A tela de configurações remota eliminava a indicação de fallback e oferecia
  provedores e dispositivos inexistentes.
- O botão de apertar para falar não possuía comportamento conectado ao backend.
- A posição salva da janela era sobrescrita sempre que as janelas flutuantes eram
  abertas.
- A exibição de texto simples aplicava escape HTML antes de inseri-lo como texto,
  o que poderia mostrar entidades como `&amp;` ao usuário.

## Estratégia de integração

A integração é seletiva sobre a base atual. `controller.py`,
`backend_bridge.py`, configurações, status de runtime e scripts de distribuição
continuam partindo da versão já validada na Entrega 1. As mudanças visuais foram
adaptadas a esses contratos e protegidas por testes de regressão antes da
validação manual.

## Decisões para a primeira versão

O PySide6 será mantido durante o PFC 2. A aplicação atual já usa seus recursos de
janelas sem moldura, permanência no topo, sinais entre threads e persistência de
configurações. A troca de framework agora exigiria reescrever esses comportamentos
antes de validar os dois fluxos principais do produto, sem evidência de que o
ganho compensaria o risco. Tempo de abertura e consumo continuarão sendo medidos
nas builds; uma migração só será retomada se essas medições indicarem um gargalo
da interface, e não do modelo de transcrição.

Para a primeira versão, foram escolhidas duas janelas flutuantes vinculadas: a
toolbar controla a sessão e a janela de texto pode ser ocultada, movida e
redimensionada separadamente. Essa abordagem já atende ao uso sobre aplicativos
de reunião e permite que somente os controles necessários capturem cliques. Uma
camada transparente cobrindo toda a tela acrescentaria tratamento específico do
Windows para passagem de cliques, múltiplos monitores e foco; ela permanece como
alternativa futura caso as duas janelas revelem uma limitação concreta.

Os chunks internos do transcritor não definem mais sozinhos um novo bloco visual.
O ASR ainda pode fechar um chunk após uma pausa curta para responder rapidamente,
mas a interface exige uma pausa contínua maior antes de exibir um novo cabeçalho
de transcrição. Assim, uma fala contínua permanece agrupada mesmo quando precisa
ser processada em vários trechos.

Os seletores PT/EN/ES foram ativados provisoriamente para trocar apenas o idioma
informado ao Faster-Whisper; eles não apresentam tradução como pronta. O botão
central inverte o par, e os seletores ficam bloqueados durante uma sessão para
não sugerir uma troca que o motor atual não aplica em tempo real. No modo
automático, o botão do microfone também passou a refletir a atividade detectada
pelo VAD e permite mutar ou reativar a captura. A toolbar armazena sua posição
separadamente da janela de texto.

# Frontend - PySide6

Aplicacao desktop para transcricao em tempo real com tela inicial, janelas
flutuantes e tela de configuracoes.

## Objetivo

- exibir a transcricao em uma janela flutuante, sem depender do terminal;
- oferecer uma tela de configuracoes com parametros persistentes;
- permitir captura com deteccao automatica de voz ou no modo apertar para falar;
- manter os controles compactos em uma toolbar sempre visivel durante a sessao;
- manter a UI desacoplada da implementacao de backend por meio de uma ponte.

O tamanho do texto pode ser ajustado e persistido com `Ctrl + roda do mouse`,
inclusive enquanto a janela ainda mostra somente a mensagem de espera. Pausas
curtas podem fechar chunks do ASR sem criar um novo bloco visual; um novo
cabeçalho aparece somente depois de uma pausa contínua maior. O estado da sessão
e o hardware ativo compartilham o mesmo indicador na toolbar: cinza em espera,
amarelo durante o carregamento e verde quando a captura está ativa.

Durante a Entrega 1, os seletores PT/EN/ES controlam somente o idioma de entrada
informado ao Faster-Whisper; eles ainda não representam tradução. O botão
central inverte o par e a escolha fica persistida para a próxima sessão. No modo
automático, o botão do microfone acende quando o VAD detecta voz e alterna o mudo
ao ser clicado. A posição da toolbar também é preservada.

## Estrutura

- src/main.py
  - ponto de entrada da aplicacao
- src/transcription_window/main_window.py
  - tela inicial (home) e orquestracao das janelas
- src/transcription_window/floating_windows.py
  - janela de transcricao, mensagens visuais e toolbar compacta
- src/transcription_window/settings_window.py
  - tela de configuracao e testes com chat
- src/transcription_window/settings_store.py
  - persistencia local dos parametros (QSettings)
- src/transcription_window/controller.py
  - controla ciclo de vida da sessao em thread de fundo
- src/transcription_window/backend_bridge.py
  - contrato de ponte e implementacao local atual

## Como trocar para servidor depois

A janela e o controller ja conversam com uma ponte (bridge).

No futuro, em vez de usar LocalBackendBridge, basta criar uma implementacao
remota com o mesmo contrato de sessao. Esse experimento esta planejado para a
Entrega 2 e devera incluir seguranca e medicao da latencia de rede.

Assim a interface grafica nao precisa ser reescrita.

## Execucao

Com a venv da raiz ativa e as dependencias instaladas:

```powershell
.\frontend\start_frontend.ps1
```

Se a intencao for usar apenas a demonstracao local da aplicacao, este e o unico comando necessario para abrir a janela.

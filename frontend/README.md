# Frontend - PySide6

Aplicacao desktop simples para demonstrar transcricao em tempo real.

## Objetivo

- exibir a transcricao em uma janela, sem depender do terminal;
- manter a UI desacoplada da implementacao de backend por meio de uma ponte.

## Estrutura

- src/main.py
  - ponto de entrada da aplicacao
- src/transcription_window/main_window.py
  - janela principal e controles
- src/transcription_window/controller.py
  - controla ciclo de vida da sessao em thread de fundo
- src/transcription_window/backend_bridge.py
  - contrato de ponte e implementacao local atual

## Como trocar para servidor depois

A janela e o controller ja conversam com uma ponte (bridge).

No futuro, em vez de usar LocalBackendBridge, basta criar uma implementacao remota (por HTTP/WebSocket) com o mesmo contrato de run/stop.

Assim a interface grafica nao precisa ser reescrita.

## Execucao

Com a venv da raiz ativa e as dependencias instaladas:

```powershell
.\frontend\start_frontend.ps1
```

Se a intencao for usar apenas a demonstracao local da aplicacao, este e o unico comando necessario para abrir a janela.

# Levantamento inicial de refatoração — Entrega 0

Este levantamento registra pontos que devem ser protegidos por testes antes de qualquer alteração estrutural. Ele não autoriza uma reescrita ampla do projeto.

## Prioridade alta

1. **Generalizar a fonte de áudio**
   - `RealtimeTranscriptionSession` depende diretamente de `MicrophoneAudioSource`.
   - A sessão deve receber um contrato comum antes da implementação de microfone e loopback simultâneos.

2. **Injetar as fábricas da bridge local**
   - `LocalBackendBridge` constrói captura, transcritor, detector e sessão diretamente.
   - Fábricas injetáveis facilitam testes, execução remota e troca de motores sem mocks sobre imports globais.

3. **Isolar imports e carregamento de componentes pesados**
   - Importar a bridge carrega módulos de interface e do Faster-Whisper mesmo quando nenhum modelo será executado.
   - Adapters e imports tardios devem ser avaliados para reduzir acoplamento e tempo de inicialização.

4. **Formalizar eventos dos dois pipelines**
   - Os callbacks atuais publicam apenas texto e status genérico de microfone.
   - A via de escuta e a via de fala precisarão identificar canal, texto original, tradução, estado e tempos separadamente.

## Prioridade média

1. Centralizar o esquema de configurações para evitar duplicação entre `SessionRequest`, `settings_store.py` e os controles da interface.
2. Separar regras de deduplicação e fronteira da orquestração de captura, mantendo seus testes de regressão.
3. Dividir `settings_window.py` em seções menores caso PySide6 seja mantido após a Entrega 1.
4. Revisar ciclo de vida e cancelamento de threads antes da execução simultânea dos dois pipelines.

## Regra de execução

Cada refatoração deve:

- resolver uma necessidade comprovada por uma entrega;
- ser feita em mudança pequena e reversível;
- manter ou ampliar a cobertura de testes;
- passar pelos testes automatizados e por um teste manual da aplicação;
- ser integrada à `main` somente depois da validação.

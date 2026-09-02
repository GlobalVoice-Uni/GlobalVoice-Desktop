# GlobalVoice Desktop

Aplicação desktop para transcrição de áudio em tempo real, em evolução para tradução simultânea bidirecional durante reuniões online.

## Visão Geral

**GlobalVoice Desktop** é uma solução desktop modular para transcrição contínua de áudio com:

- ✅ Transcrição em tempo real via microfone
- ✅ Execução local com seleção automática entre GPU compatível e CPU
- ✅ Idiomas: português, inglês e espanhol
- ✅ Arquitetura desacoplada (frontend/backend/bridge) pronta para evolução
- ✅ Interface em PySide6 com home, toolbar flutuante e painel de configuração por abas

No PFC 2, o projeto avança para capturar tanto o áudio do sistema quanto o microfone, traduzir os dois fluxos e apresentar o resultado por texto e voz. A validação principal será local, com execução remota avaliada como experimento comparativo para máquinas com menos recursos.

## Estrutura do Repositório

```
GlobalVoice-Desktop/
├── frontend/              # Aplicação PySide6 (UI e orquestração local)
│   ├── src/
│   │   ├── transcription_window/  # Pacote principal
│   │   │   ├── __init__.py
│   │   │   ├── main_window.py      # Janela principal
│   │   │   ├── floating_windows.py # Toolbar e janela flutuante de transcrição
│   │   │   ├── controller.py       # Orquestração em thread
│   │   │   ├── settings_window.py  # Configurações e teste da transcrição
│   │   │   ├── settings_store.py   # Persistência local (QSettings)
│   │   │   └── backend_bridge.py   # Contrato de integração
│   │   └── main.py
│   ├── start_frontend.ps1
│   └── requirements.txt
│
├── backend/               # Backend modular (captura + transcrição)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── ports.py                      # Protocolos (interfaces)
│   │   ├── audio/
│   │   │   └── audio_capture.py          # Captura de microfone
│   │   ├── detectors/
│   │   │   └── speech_detectors.py       # VAD e detectores de fala
│   │   ├── transcribers/
│   │   │   └── local_faster_whisper.py  # Implementação Faster-Whisper
│   │   └── sessions/
│   │       └── realtime_session.py       # Orquestração de sessão
│   └── requirements.txt
│
└── tests/                 # Testes automatizados
    ├── unit/              # Regras isoladas do backend
    └── integration/       # Integração entre bridge e backend
```

## Setup Rápido

### Pré-requisitos

- Python 3.12
- pip
- PowerShell no Windows
- Opcional: bibliotecas NVIDIA compatíveis com a versão instalada do CTranslate2

### 1. Clone e entre no repositório

```bash
git clone https://github.com/GlobalVoice-Uni/GlobalVoice-Desktop.git
cd GlobalVoice-Desktop
```

### 2. Crie e ative o ambiente virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Este projeto usa um único ambiente virtual na raiz para backend e frontend.

### 3. Instale as dependencias validadas

```powershell
python -m pip install -r requirements\runtime-windows.lock
```

O modelo Silero VAD principal ja esta versionado no projeto e e executado por
ONNX Runtime. Para apenas consultar as dependencias diretas, veja
`requirements\runtime.txt`.

### 4. Execute (PowerShell no Windows)

```powershell
cd frontend
.\start_frontend.ps1
```

Ou direto com Python:

```bash
cd frontend
python src/main.py
```

## Testes Automatizados

Com a venv da raiz ativa e as dependências instaladas:

```powershell
.\run_tests.ps1
```

O mesmo conjunto é executado automaticamente em pushes e pull requests pelo GitHub Actions.

A composicao e a validacao do ambiente estao registradas em
[`docs/entrega-1-dependencias.md`](docs/entrega-1-dependencias.md).

## Configuração de GPU

A preferência padrão é `GPU`. No motor atual, a aplicação consulta o CTranslate2
usado pelo Faster-Whisper e escolhe somente um formato de computação aceito por
uma GPU NVIDIA via CUDA. Se a placa, o driver ou as bibliotecas necessárias não
forem compatíveis, a sessão continua em CPU e apresenta apenas uma mensagem
simples na interface.

A preferência permanece visível como GPU, enquanto um indicador separado mostra
o dispositivo realmente ativo. Em caso de fallback, esse indicador muda para CPU
e seu texto de ajuda explica o motivo sem expor a exceção técnica.

No Windows, o perfil NVIDIA provisório inclui somente `cublas64_12.dll` e
`cublasLt64_12.dll`, além do cuDNN já fornecido pelo CTranslate2. Se essas
bibliotecas não estiverem instaladas no pacote, a aplicação identifica a ausência
antes da primeira inferência e usa CPU, sem apresentar uma falsa GPU ativa.

Esta implementação ainda não acelera o ASR em GPUs AMD ou Intel. Esses fabricantes
usam CPU nesta linha de base. A Entrega 1 inclui a avaliação de DirectML/WinML e
ROCm para ampliar a cobertura sem vincular a arquitetura final ao CTranslate2.

Essa decisão não depende de `torch.cuda.is_available()`: a aplicação não usa
PyTorch no runtime. A compatibilidade do ASR é determinada diretamente pelo
CTranslate2 e pelas bibliotecas do perfil de aceleração.

As versões atuais do Faster-Whisper requerem cuBLAS para CUDA 12 e cuDNN 9 para
execução em GPU. Esses requisitos serão verificados durante a evolução das builds;
eles não são necessários para o fallback em CPU.

### Performance

| Modelo | Device | Latência Média |
| ------ | ------ | ---------------- |
| tiny   | GPU    | ~100ms           |
| base   | GPU    | ~200ms           |
| small  | GPU    | ~400ms           |
| base   | CPU    | ~600ms           |

_Benchmarks detalhados em [GlobalVoice-ASR-Benchmarks](https://github.com/GlobalVoice-Uni/GlobalVoice-ASR-Benchmarks)_

## Uso Básico

1. **Inicie a aplicação**
2. **Na Home, abra as janelas flutuantes em "Iniciar"**
3. **Na toolbar, ajuste idiomas e controle a sessão**
4. **Use "Opcoes" para abrir as configurações por abas**
5. **Fale no microfone** — a transcrição aparece em tempo real
6. **Clique "Parar" quando terminar**

### O que a UI oferece atualmente

- Home para iniciar e abrir configurações
- Toolbar flutuante com iniciar/parar/limpar, dispositivo ativo, indicador de status e botão de opções
- Janela flutuante de transcrição redimensionável
- Persistência local de parâmetros e dimensões da janela via QSettings

### Parâmetros Avançados

- **Context Window**: número de chunks anteriores para contexto (melhora continuidade)
- **Max Duration**: tempo máximo de uma sessão (em segundos)
- **Silero/VAD**: parâmetros de detecção de fala e silêncio configuráveis

## Arquitetura

### Fluxo de Dados

```
[Microfone] → [AudioCapture] → [RealtimeSession] → [FasterWhisper] → [Controller] → [MainWindow/FloatingWindows]
                                 ↑                                                     ↓
                             VAD + Dedupe + Overlap                           [User sees live transcript]
```

### Pontos-Chave

- **AudioCapture** (`backend/app/audio/audio_capture.py`):

  - Captura contínua com callback
  - Reamostragem para 16 kHz
  - Detecção de pico
- **RealtimeSession** (`backend/app/sessions/realtime_session.py`):

  - VAD simples por energia
  - Segmentação por silêncio
  - Dedupe de borda e tail guard textual
  - Overlap de áudio para continuidade
- **LocalFasterWhisperTranscriber** (`backend/app/transcribers/local_faster_whisper.py`):

  - Fallback automático de GPU → CPU
  - Compute types: float16 → int8_float16 → float32
  - Suporte a contexto (context_window)
- **RealtimeController** (`frontend/src/transcription_window/controller.py`):

  - Orquestração em thread separada (não bloqueia UI)
  - Sinais Qt para atualização de UI
- **MainWindow + FloatingWindows** (`frontend/src/transcription_window/main_window.py` e `frontend/src/transcription_window/floating_windows.py`):

  - Home para orquestração das janelas flutuantes
  - Exibição em tempo real da transcrição
  - Status visual de carregamento/ativo e fechamento interligado entre janelas

## Roadmap

O planejamento do PFC 2, os marcos concluídos e os critérios de validação estão em [roadmap.md](roadmap.md).

## Desenvolvimento

### Estrutura de Responsabilidades

| Camada                        | Responsabilidade                | Linguagem                      |
| ----------------------------- | ------------------------------- | ------------------------------ |
| **Frontend**            | UI, controles, thread local     | Python + PySide6               |
| **Backend Bridge**      | Contrato entre UI e lógica     | Python (dataclasses, Protocol) |
| **Backend Session**     | Orquestração de transcrição | Python puro                    |
| **Backend Transcriber** | Modelo de IA (Faster-Whisper)   | Python + CTranslate2           |
| **Backend Audio**       | Captura e processamento         | Python + numpy/scipy           |

### Extensões Futuras

**Para adicionar um novo backend remoto**:

1. Implemente `TranscriberPort` em novo adaptador (ex: `RemoteBackendBridge`)
2. Injete em `RealtimeController` via `SessionRequest`
3. Sem mudanças em `MainWindow` necessárias

**Para integrar novo VAD**:

1. Substitua lógica VAD em `RealtimeSession.run()`
2. Mantenha interface `on_text`, `on_status` igual

## Dependências Principais

- **PySide6**: UI desktop
- **faster-whisper**: Motor de transcrição
- **torch**: Framework ML (com suporte CUDA)
- **sounddevice**: Captura de áudio
- **numpy/scipy**: Processamento de áudio

## Troubleshooting

| Problema                                         | Solução                                             |
| ------------------------------------------------ | ----------------------------------------------------- |
| "ModuleNotFoundError: No module named 'PySide6'" | `pip install -r frontend/requirements.txt`          |
| GPU indisponível                                 | O modo automático continua em CPU; ver configuração de GPU |
| "No module named 'faster_whisper'"               | `pip install -r backend/requirements.txt`           |
| Transcrição muito lenta                        | Usar modelo `tiny` ou `base`; verificar GPU ativa |
| Áudio cortado ou atrasado                       | Aumentar `context_window` ou `max_duration`       |

## Contribuindo

1. Faça fork do repositório
2. Crie uma branch (`git checkout -b feature/sua-feature`)
3. Commit com mensagem clara em português
4. Push e abra um Pull Request

## Documentação Adicional

- **Benchmarks de Modelos**: [GlobalVoice-ASR-Benchmarks](https://github.com/GlobalVoice-Uni/GlobalVoice-ASR-Benchmarks)
- **Roadmap do PFC 2**: [roadmap.md](roadmap.md)

## Licença

[Definir conforme seu projeto]

---

**Desenvolvido por GlobalVoice-Uni**
Última atualização: 18 de maio de 2026

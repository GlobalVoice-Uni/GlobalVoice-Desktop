# GlobalVoice Desktop

Aplicação desktop para transcrição de áudio em tempo real, utilizando Faster-Whisper e interface gráfica em PySide6.

## Visão Geral

**GlobalVoice Desktop** é uma solução desktop modular para transcrição contínua de áudio com:

- ✅ Transcrição em tempo real via microfone
- ✅ Execução local com fallback automático entre GPU e CPU
- ✅ Idiomas: português e inglês
- ✅ Arquitetura desacoplada (frontend/backend/bridge) pronta para evolução
- ✅ Interface intuitiva em PySide6

## Estrutura do Repositório

```
GlobalVoice-Desktop/
├── frontend/              # Aplicação PySide6 (UI e orquestração local)
│   ├── src/
│   │   ├── transcription_window/  # Pacote principal
│   │   │   ├── __init__.py
│   │   │   ├── main_window.py     # Janela principal
│   │   │   ├── controller.py      # Orquestração em thread
│   │   │   └── backend_bridge.py  # Contrato de integração
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
│   │   ├── transcribers/
│   │   │   └── local_faster_whisper.py  # Implementação Faster-Whisper
│   │   └── sessions/
│   │       └── realtime_session.py       # Orquestração de sessão
│   └── requirements.txt
│
└── tests/                 # Testes e validações
    └── [estrutura a definir]
```

## Setup Rápido

### Pré-requisitos

- Python 3.9+
- pip
- PowerShell no Windows
- Opcional: CUDA 12.1 + cuDNN para GPU

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

### 3. Configure Backend

```bash
cd backend
pip install -r requirements.txt
cd ..
```

### 4. Configure Frontend

```bash
cd frontend
pip install -r requirements.txt
cd ..
```

### 5. Execute (PowerShell no Windows)

```powershell
cd frontend
.\start_frontend.ps1
```

Ou direto com Python:

```bash
cd frontend
python src/main.py
```

## Configuração de GPU

### Se CUDA/GPU não forem detectados

```python
python -c "import torch; print(torch.version); print(torch.version.cuda); print(torch.cuda.is_available())"
```

Se retornar `False`, reinstale o PyTorch com o wheel correto para CUDA 12.1:

```bash
pip install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
```

Depois, rode a verificação novamente.

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
2. **Configure**:
   - Idioma (português ou inglês)
   - Tamanho do modelo (tiny, base, small)
   - Dispositivo (GPU/CPU automático)
3. **Clique "Iniciar"**
4. **Fale no microfone** — a transcrição aparece em tempo real
5. **Clique "Parar"** quando terminar

### Parâmetros Avançados

- **Context Window**: número de chunks anteriores para contexto (melhora continuidade)
- **Max Duration**: tempo máximo de uma sessão (em segundos)

## Arquitetura

### Fluxo de Dados

```
[Microfone] → [AudioCapture] → [RealtimeSession] → [FasterWhisper] → [Controller] → [MainWindow]
                                     ↑                                                    ↓
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
- **MainWindow** (`frontend/src/transcription_window/main_window.py`):

  - Interface PySide6
  - Exibição em tempo real da transcrição

## Roadmap

### Fase 1 (Atual)

- [✅] Backend modular com Faster-Whisper
- [✅] Frontend desktop em PySide6
- [✅] Suporte GPU com fallback automático
- [✅] Arquitetura desacoplada (bridge pronta para evolução)

### Fase 2 (Próximos Sprints)

- [ ] Integração de **Silero VAD** para melhor detecção de fala
- [ ] Testes automatizados (unit + integração)
- [ ] Suporte a exportação (SRT, JSON, TXT)

### Fase 3 (Futuro)

- [ ] Backend remoto (FastAPI)
- [ ] Autenticação e multi-usuário
- [ ] Dashboard de histórico
- [ ] Suporte a modelos customizados

## Desenvolvimento

### Estrutura de Responsabilidades

| Camada                        | Responsabilidade                | Linguagem                      |
| ----------------------------- | ------------------------------- | ------------------------------ |
| **Frontend**            | UI, controles, thread local     | Python + PySide6               |
| **Backend Bridge**      | Contrato entre UI e lógica     | Python (dataclasses, Protocol) |
| **Backend Session**     | Orquestração de transcrição | Python puro                    |
| **Backend Transcriber** | Modelo de IA (Faster-Whisper)   | Python + Torch                 |
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
| "CUDA not available"                             | Ver seção "Configuração de GPU"                   |
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
- **Roadmap Técnico**: Veja seção "Roadmap" acima

## Licença

[Definir conforme seu projeto]

---

**Desenvolvido por GlobalVoice-Uni**
Última atualização: 15 de abril de 2026

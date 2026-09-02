# Build Windows

Esta é a primeira estratégia de distribuição do PFC 2. Ela usa PyInstaller no
modo `onedir`: o executável e suas dependências permanecem em uma pasta que deve
ser distribuída inteira.

O modo foi escolhido para o primeiro marco porque evita a extração para uma pasta
temporária feita pelo modo `onefile`, reduz o trabalho antes de abrir a interface e
facilita identificar uma dependência ausente. A comparação com outras estratégias
continua na Entrega 1.

## Gerar a build

Na raiz do projeto:

```powershell
.\deploy\windows\build.ps1
```

Por padrão, o script usa as dependências da venv já validada e instala o
PyInstaller separadamente em `.build\venv`. Para preparar também as dependências
de execução fixadas no lock do Windows, use:

```powershell
.\deploy\windows\build.ps1 -InstallRuntimeDependencies
```

Essa opção deve ser usada em uma venv limpa ou controlada. Ela não é necessária
para repetir o empacotamento do ambiente que já executa a aplicação.

Para gerar a build a partir de outra venv validada sem alterar a `.venv` de
desenvolvimento:

```powershell
.\deploy\windows\build.ps1 `
  -RuntimePythonPath ".build\dependency-audit\venv\Scripts\python.exe"
```

### Perfis de runtime

Sem parâmetros adicionais, o script gera a base em CPU. Se houver uma GPU NVIDIA
mas as bibliotecas CUDA não estiverem no pacote, a aplicação muda para CPU antes
da primeira inferência e informa o fallback na interface.

Para gerar o perfil NVIDIA provisório, informe uma pasta validada que contenha
`cublas64_12.dll` e `cublasLt64_12.dll`:

```powershell
.\deploy\windows\build.ps1 `
  -RuntimePythonPath ".build\dependency-audit\venv\Scripts\python.exe" `
  -CudaRuntimePath "C:\caminho\cuda-runtime"
```

O parâmetro serve como fonte das duas DLLs. A origem definitiva deve ser uma
distribuição oficial cuja licença permita a redistribuição pelo instalador.

Durante o empacotamento, o script restringe o `PATH` ao Python e aos componentes
do Windows. Isso impede que DLLs de outras ferramentas instaladas na máquina de
desenvolvimento sejam copiadas acidentalmente para a aplicação.

Para investigar uma falha de inicialização sem alterar a build distribuída:

```powershell
.\deploy\windows\build.ps1 -DiagnosticConsole
```

O parâmetro habilita o console somente naquela geração. A build normal permanece
sem janela de terminal.

O resultado fica em:

```text
dist\GlobalVoice\GlobalVoice.exe
```

Toda a pasta `dist\GlobalVoice` deve ser enviada. Um atalho ou uma cópia isolada
do `.exe` não contém as bibliotecas necessárias.

## Primeiro uso

O modelo Faster-Whisper ainda não é incorporado ao pacote. Na primeira sessão de
transcrição, ele é baixado para o cache do usuário se ainda não estiver presente;
por isso, uma máquina limpa precisa de internet no primeiro uso. Uma build offline
e o tamanho de modelo mais adequado serão avaliados depois do teste externo.

A preferência de dispositivo padrão é GPU. Nesta build, o CTranslate2 acelera o
ASR em GPUs NVIDIA via CUDA e continua em CPU quando a aceleração não pode ser
inicializada. AMD e Intel ainda usam CPU. A interface mostra separadamente a
preferência e o dispositivo realmente ativo, sem exigir que o usuário interprete
mensagens de terminal.

O Silero VAD e o detector principal e esta presente na build reproduzivel atual.
Seu modelo ONNX e versionado no projeto e nao requer PyTorch ou Torchaudio. O
detector por energia existe apenas como fallback de seguranca.

O perfil NVIDIA provisório acrescenta somente cuBLAS e ocupa 1.309,96 MB depois
da migração do Silero para ONNX, contra 1.937,80 MB na build anterior. Esse
tamanho ainda não é uma meta final: PySide6 e as bibliotecas CUDA serão avaliados
separadamente antes do instalador.

Referências técnicas:

- [PyInstaller: opções `onedir` e `onefile`](https://pyinstaller.org/en/stable/usage.html#what-to-generate)
- [Faster-Whisper: requisitos atuais de GPU](https://github.com/SYSTRAN/faster-whisper#gpu)
- [CTranslate2: consulta dos formatos suportados](https://opennmt.net/CTranslate2/python/ctranslate2.get_supported_compute_types.html)

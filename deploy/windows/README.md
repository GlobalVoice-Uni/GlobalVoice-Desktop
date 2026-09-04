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

O perfil NVIDIA é preparado separadamente a partir do pacote oficial da NVIDIA.
O script baixa `nvidia-cublas-cu12==12.8.4.1`, verifica o SHA-256 antes de abrir o
arquivo, extrai somente as duas DLLs necessárias e preserva a licença:

```powershell
.\deploy\windows\prepare-nvidia-runtime.ps1
```

O download fica no cache local `.build\downloads`, e o perfil reproduzível é
gerado em `dist\runtime-profiles\nvidia-cuda12`. Para acrescentá-lo a uma build:

```powershell
.\deploy\windows\build.ps1 `
  -RuntimePythonPath ".build\dependency-audit\venv\Scripts\python.exe" `
  -NvidiaRuntimePath "dist\runtime-profiles\nvidia-cuda12"
```

O PyInstaller sempre gera primeiro a mesma base. Quando o perfil é informado, os
arquivos opcionais são copiados depois para
`_internal\runtime\nvidia\cuda12`. Isso evita misturar cuBLAS com as dependencias
comuns e permite que o instalador omita o perfil em máquinas CPU, AMD ou Intel.

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

## Gerar o instalador

O primeiro instalador usa o Inno Setup 7.1.0. Por padrão, o script procura o
compilador em `.build\inno-setup-7.1.0\ISCC.exe`; outra instalação pode ser
informada por `-InnoCompilerPath`.

Com a build e o perfil NVIDIA preparados:

```powershell
.\deploy\windows\build-installer.ps1 -AppVersion "0.1.0"
```

O resultado compactado fica em
`dist\installer\GlobalVoice-Setup-0.1.0.exe`. Para ajustes no instalador, o modo
rápido evita a compressão e reduz o tempo de compilação:

```powershell
.\deploy\windows\build-installer.ps1 -AppVersion "0.1.0" -Fast
```

O instalador normal solicita permissão administrativa, sugere `Arquivos de
Programas\Global Voice`, permite alterar o destino, cria um atalho no menu Iniciar
e oferece um atalho opcional na área de trabalho. Português do Brasil e inglês
estão incluídos.

Uma consulta ao Registro do Windows procura um dispositivo PCI NVIDIA da classe
de adaptadores de vídeo. Quando ele existe, o componente CUDA 12/cuBLAS é
selecionado automaticamente; quando não existe, somente a base é selecionada. A
tela de componentes permite corrigir a escolha manualmente. O instalador não
instala drivers nem o CUDA Toolkit no sistema.

O primeiro pacote completo ocupou 520,91 MB e levou aproximadamente 7 minutos
para ser compilado com LZMA2 no ambiente de desenvolvimento. O modo rápido ocupou
1.111,24 MB e levou cerca de 16 segundos. Instalação e desinstalação silenciosas
foram verificadas tanto com o perfil NVIDIA automático quanto somente com a base.

O executável do instalador ainda não possui assinatura de código. Até que uma
estratégia de assinatura seja definida, o Windows pode apresentar um aviso de
editor desconhecido em outras máquinas.

As preferências da aplicação são mantidas por usuário entre atualizações e
reinstalações. Em uma instalação limpa, GPU e Silero são as opções iniciais; o
botão `Restaurar` da tela de configurações recupera esses padrões sem exigir uma
nova instalação.

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

O Silero VAD é o detector principal e está presente na build reproduzível atual.
Seu modelo ONNX é versionado no projeto e não requer PyTorch ou Torchaudio. O
detector por energia existe apenas como fallback de segurança.

A base atual ocupa 354,01 MB. O perfil NVIDIA acrescenta 751,92 MB descompactado,
totalizando 1.105,92 MB quando instalado. O pacote oficial de origem ocupa
aproximadamente 541,25 MB compactado. As duas DLLs extraídas dele são byte a byte
idênticas às que passaram pelos testes manuais anteriores.

Referências técnicas:

- [PyInstaller: opções `onedir` e `onefile`](https://pyinstaller.org/en/stable/usage.html#what-to-generate)
- [Faster-Whisper: requisitos atuais de GPU](https://github.com/SYSTRAN/faster-whisper#gpu)
- [CTranslate2: consulta dos formatos suportados](https://opennmt.net/CTranslate2/python/ctranslate2.get_supported_compute_types.html)
- [Guia de instalação do CUDA no Windows](https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/index.html)
- [Licença do CUDA Toolkit](https://docs.nvidia.com/cuda/eula/index.html)

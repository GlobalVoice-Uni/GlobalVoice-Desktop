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
de execução declaradas nos arquivos `requirements.txt`, use:

```powershell
.\deploy\windows\build.ps1 -InstallRuntimeDependencies
```

Essa opção deve ser usada em uma venv limpa ou controlada. Ela não é necessária
para repetir o empacotamento do ambiente que já executa a aplicação.

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
transcrição, ele é baixado para o cache do usuário; por isso, essa build inicial
precisa de internet no primeiro uso. Uma build offline e o tamanho de modelo mais
adequado serão avaliados depois do teste externo.

O modo de dispositivo padrão é `auto`. A aplicação tenta uma configuração que o
CTranslate2 declara compatível com a GPU e continua em CPU quando a aceleração não
pode ser inicializada. O usuário recebe o estado pela interface, sem precisar
interpretar mensagens de terminal.

Esta primeira build reproduz o ambiente local já validado, no qual o pacote
Silero VAD ainda não está instalado. Ao selecionar Silero, a aplicação usa o VAD
por energia automaticamente e informa somente essa troca na interface. A inclusão
do Silero sem introduzir dependências desnecessárias no pacote permanece uma
decisão técnica da Entrega 1.

Referências técnicas:

- [PyInstaller: opções `onedir` e `onefile`](https://pyinstaller.org/en/stable/usage.html#what-to-generate)
- [Faster-Whisper: requisitos atuais de GPU](https://github.com/SYSTRAN/faster-whisper#gpu)
- [CTranslate2: consulta dos formatos suportados](https://opennmt.net/CTranslate2/python/ctranslate2.get_supported_compute_types.html)

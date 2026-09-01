# Auditoria de dependencias — Entrega 1

Auditoria executada no Windows com Python 3.12.3 em uma venv criada sem acesso aos
pacotes do ambiente de desenvolvimento.

## Resultado

- O Silero VAD e o detector principal da aplicacao e deve integrar toda build.
- O detector por energia permanece apenas como fallback quando o Silero nao pode
  ser inicializado.
- Faster-Whisper e CTranslate2 executam o ASR; PyTorch nao controla a GPU usada
  pela transcricao.
- `torch` e `torchaudio` foram alinhados na versao 2.11.0 CPU para atender ao
  Silero sem adicionar outro runtime CUDA.
- CTranslate2 foi declarado diretamente porque o codigo consulta sua capacidade
  de GPU, embora ele tambem seja dependencia transitiva do Faster-Whisper.
- Os limites abertos (`>=`) foram substituidos por versoes diretas fixas e por um
  lock completo para Windows.

## Validacoes executadas

- instalacao completa a partir de uma venv vazia;
- `pip check` sem requisitos quebrados;
- importacao de todos os componentes de runtime;
- carregamento real do modelo Silero e processamento de um frame de silencio;
- 30 testes unitarios e de integracao aprovados no ambiente limpo e na venv de
  desenvolvimento;
- build `onedir` gerada a partir do lock, com o modelo JIT do Silero e o runtime
  CPU do PyTorch presentes;
- processo empacotado mantido estavel durante o teste automatico de abertura.

O diretorio `site-packages` limpo ocupou aproximadamente 1,59 GB antes do
empacotamento. Os maiores componentes foram PySide6 (aproximadamente 628 MB) e
PyTorch (aproximadamente 448 MB). Esses valores justificam avaliar a interface e
a estrategia de distribuicao, mas nao autorizam remover o VAD principal.

A build completa passou a ocupar 1.185,94 MB. A primeira build, sem Silero,
ocupava 557,17 MB e nao deve ser distribuida como representacao do runtime final.

## Perfil NVIDIA provisório

O primeiro pacote reproduzível usava o runtime CPU do PyTorch e não continha
cuBLAS. O CTranslate2 detectava a GPU e carregava o modelo, mas a primeira
inferência falhava com a ausência de `cublas64_12.dll`. No ambiente de
desenvolvimento, a instalação CUDA do PyTorch fornecia essa biblioteca e escondia
a dependência.

A correção separou o runtime do ASR do runtime do Silero:

- Silero continua usando PyTorch CPU;
- uma build CPU sem cuBLAS faz fallback antes da primeira inferência;
- o perfil NVIDIA inclui apenas `cublas64_12.dll` e `cublasLt64_12.dll`;
- as duas DLLs empacotadas foram usadas em uma inferência GPU real com a venv
  limpa;
- a build NVIDIA passou a ocupar 1.937,80 MB, dos quais aproximadamente 751,86 MB
  pertencem às duas bibliotecas cuBLAS;
- a transcrição GPU pelo executável foi validada manualmente com Silero VAD e com
  o detector por energia, sem o erro de carregamento do cuBLAS.

Esse perfil permite a validação técnica, mas ainda não define a distribuição
final. A origem licenciada das DLLs, versões alternativas menores e a instalação
seletiva por hardware devem ser avaliadas antes de um release.

## Pendencias relacionadas

- substituir PyTorch por um runtime menor para o Silero, se a comparação mantiver
  a mesma qualidade e comportamento;
- definir uma fonte oficial e redistribuível para o perfil cuBLAS do instalador;
- definir os perfis de aceleracao depois de comparar CUDA, DirectML/WinML e ROCm;
- atualizar o lock somente depois que uma nova combinacao passar pela mesma
  validacao limpa.

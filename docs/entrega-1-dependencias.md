# Auditoria de dependencias — Entrega 1

Auditoria executada no Windows com Python 3.12.3 em uma venv criada sem acesso aos
pacotes do ambiente de desenvolvimento.

## Resultado

- O Silero VAD e o detector principal da aplicacao e deve integrar toda build.
- O detector por energia permanece apenas como fallback quando o Silero nao pode
  ser inicializado.
- Faster-Whisper e CTranslate2 executam o ASR; PyTorch nao controla a GPU usada
  pela transcricao.
- O Silero 6.2 foi validado por ONNX Runtime com o modelo de 16 kHz e opset 15
  versionado no projeto; PyTorch e Torchaudio deixaram de fazer parte do runtime.
- CTranslate2 foi declarado diretamente porque o codigo consulta sua capacidade
  de GPU, embora ele tambem seja dependencia transitiva do Faster-Whisper.
- Os limites abertos (`>=`) foram substituidos por versoes diretas fixas e por um
  lock completo para Windows.

## Validacoes executadas

- instalacao completa a partir de uma venv vazia;
- `pip check` sem requisitos quebrados;
- importacao de todos os componentes de runtime;
- carregamento real do modelo Silero e processamento de um frame de silencio;
- comparação quadro a quadro contra a implementação anterior em um sinal técnico
  e em fala sintetizada, sem divergências de estado ou eventos;
- 33 testes unitarios e de integracao aprovados na venv de
  desenvolvimento;
- modelo ONNX e licença do Silero incluídos nos artefatos do projeto;
- processo empacotado mantido estavel durante o teste automatico de abertura.

O diretorio `site-packages` limpo ocupava aproximadamente 1,59 GB antes da
substituicao. Sem PyTorch, Torchaudio e o pacote Python do Silero, passou a ocupar
1.041,14 MB: reducao aproximada de 548,88 MB. O VAD principal foi preservado com
o modelo ONNX oficial da mesma versão.

A build completa passou a ocupar 1.185,94 MB. A primeira build, sem Silero,
ocupava 557,17 MB e nao deve ser distribuida como representacao do runtime final.

## Perfil NVIDIA provisório

O primeiro pacote reproduzível usava o runtime CPU do PyTorch e não continha
cuBLAS. O CTranslate2 detectava a GPU e carregava o modelo, mas a primeira
inferência falhava com a ausência de `cublas64_12.dll`. No ambiente de
desenvolvimento, a instalação CUDA do PyTorch fornecia essa biblioteca e escondia
a dependência.

A correção separou o runtime do ASR do VAD:

- Silero usa ONNX Runtime somente em CPU, sem disputar o perfil CUDA do ASR;
- uma build CPU sem cuBLAS faz fallback antes da primeira inferência;
- o perfil NVIDIA inclui apenas `cublas64_12.dll` e `cublasLt64_12.dll`;
- as duas DLLs empacotadas foram usadas em uma inferência GPU real com a venv
  limpa;
- a build NVIDIA passou a ocupar 1.937,80 MB, dos quais aproximadamente 751,86 MB
  pertencem às duas bibliotecas cuBLAS;
- a transcrição GPU pelo executável foi validada manualmente com Silero VAD e com
  o detector por energia, sem o erro de carregamento do cuBLAS.

Depois da migração do Silero para ONNX, o perfil NVIDIA passou a ocupar 1.309,96
MB, redução de 627,84 MB (aproximadamente 32,4%) em relação à build anterior. A
inspeção do pacote confirmou a ausência de PyTorch e Torchaudio, a presença do
modelo ONNX e de sua licença. A transcrição com fala real foi validada manualmente
no executável usando Silero, GPU e CPU; o detector por energia também permaneceu
funcional.

Esse perfil permite a validação técnica, mas ainda não define a distribuição
final. A origem licenciada das DLLs, versões alternativas menores e a instalação
seletiva por hardware devem ser avaliadas antes de um release.

## Pendencias relacionadas

- definir uma fonte oficial e redistribuível para o perfil cuBLAS do instalador;
- definir os perfis de aceleracao depois de comparar CUDA, DirectML/WinML e ROCm;
- atualizar o lock somente depois que uma nova combinacao passar pela mesma
  validacao limpa.

# Dependencias

Os arquivos desta pasta separam as dependencias por finalidade:

- `runtime.txt`: lista curta das dependencias diretas do backend e do frontend;
- `runtime-windows.lock`: resolucao completa validada no Windows e usada para
  ambientes reproduziveis, testes automatizados e builds;
- `test.txt`: ambiente da suite. Os testes usam `unittest`, sem framework
  adicional;
- `../deploy/windows/requirements-build.txt`: ferramentas isoladas de build.

O Silero VAD faz parte do runtime principal. `torch` e `torchaudio` usam o mesmo
numero de versao e executam o VAD em CPU; a aceleracao do Faster-Whisper continua
sendo responsabilidade do CTranslate2. Isso evita instalar uma variante CUDA do
PyTorch que nao participa da transcricao.

O perfil NVIDIA provisório usa cuBLAS para CUDA 12 fora do lock Python. A build
recebe `cublas64_12.dll` e `cublasLt64_12.dll` por um caminho explícito, sem
reintroduzir o PyTorch CUDA completo. A origem redistribuível final dessas
bibliotecas ainda deve ser definida.

Os demais perfis de aceleração do ASR ainda não estão fechados. CUDA,
DirectML/WinML e ROCm terão requisitos definitivos depois dos testes de
compatibilidade e da escolha do motor da Entrega 1.

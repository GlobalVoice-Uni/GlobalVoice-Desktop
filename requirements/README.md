# Dependencias

Os arquivos desta pasta separam as dependencias por finalidade:

- `runtime.txt`: lista curta das dependencias diretas do backend e do frontend;
- `runtime-windows.lock`: resolucao completa validada no Windows e usada para
  ambientes reproduziveis, testes automatizados e builds;
- `test.txt`: ambiente da suite. Os testes usam `unittest`, sem framework
  adicional;
- `../deploy/windows/requirements-build.txt`: ferramentas isoladas de build.

O Silero VAD faz parte do runtime principal e executa em CPU pelo ONNX Runtime.
`torch` e `torchaudio` não fazem parte do ambiente de execução. A aceleração do
Faster-Whisper continua sendo responsabilidade do CTranslate2.

O perfil NVIDIA usa cuBLAS para CUDA 12 fora do lock Python. As bibliotecas são
extraídas do pacote oficial `nvidia-cublas-cu12==12.8.4.1`, com versão e hashes
fixados em `deploy/windows/runtime-profiles/nvidia-cuda12.json`. A build base não
recebe esse pacote; o perfil opcional é instalado em um diretório próprio sem
reintroduzir o PyTorch CUDA completo.

Os demais perfis de aceleração do ASR ainda não estão fechados. CUDA,
DirectML/WinML e ROCm terão requisitos definitivos depois dos testes de
compatibilidade e da escolha do motor da Entrega 1.

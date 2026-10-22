# Entrega 3 — atraso e vozes: diagnóstico de 21/10/2026

## Reprodução ao vivo pelo caminho do aplicativo

Os arquivos `30sEN.mp4` e `30sBR.mp4` foram **reproduzidos em tempo real** em dois dispositivos de saída do Windows. O áudio em inglês saiu no headset e foi capturado pelo loopback da reunião. O áudio em português saiu no VB-CABLE e foi capturado por um segundo loopback. Rodaram duas sessões simultâneas do Global Voice, com Silero VAD, Faster-Whisper compartilhado, Argos e Piper. A reprodução final das vozes foi temporizada em uma saída silenciosa para medir a fila sem misturar a voz sintetizada aos próprios áudios de teste.

| Ensaio de 30 s | Captura pronta | Trechos transcritos | STT mediano | Maior STT | Maior espera na fila de STT | Avisos de atraso |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Só reunião, com voz traduzida | 4,9 s | 11 | 0,632 s | 0,821 s | 0,092 s | 0 |
| Reunião e segunda fonte, ambas com voz | 8,3 s | 23 | 0,689 s (reunião), 0,778 s (segunda fonte) | 1,099 s | 0 s | 0 |

Ambos os ensaios permaneceram em **CUDA `float32`**, sem fallback para CPU. A reprodução e captura real dos 30 segundos não apresentaram crescimento contínuo da fila. Um ensaio preliminar de 10 segundos teve um trecho isolado com STT de 4,2 s; não se repetiu nos dois ensaios de 30 segundos. Isso merece observação no uso prolongado.

**Limite do ensaio de duas fontes:** a entrada de microfone exposta ao processo de teste não abriu neste Windows, apesar de aparecer na lista de dispositivos. Para exercitar a simultaneidade, a segunda fonte também foi capturada por loopback do VB-CABLE. Portanto, o teste cobre duas capturas contínuas, as duas sessões e os dois fluxos de voz, mas ainda precisa ser validado com o microfone físico e os aplicativos de chamada do usuário.

O teste ao vivo revelou uma falha adicional: o backend de captura WASAPI dependia da inicialização de COM na thread de captura. Antes da correção, o ensaio de reunião falhava com `0x800401F0`; depois dela, os ensaios acima concluíram. O aplicativo agora inicializa COM ao enumerar dispositivos e ao abrir o loopback na thread correspondente.

## Medição complementar em arquivos

Foram usados `30sBR.mp4` e `30sEN.mp4` do conjunto de testes estáticos, em duas fontes simultâneas, com o modelo `small`, trechos de 3,2 s e o mesmo bloqueio de acesso ao STT usado pelo aplicativo. A máquina tinha uma GTX 1050 de 2 GB. Não houve fallback: o Faster-Whisper executou em CUDA com `float32`.

| Medida | Resultado |
| --- | ---: |
| Trechos de STT | 19 |
| Tempo mediano de STT por trecho | 0,712 s |
| Maior tempo de STT | 0,822 s |
| Maior espera pelo modelo compartilhado | 0,801 s |
| Maior tempo entre trecho pronto e resultado de STT | 1,624 s |
| Pico observado de VRAM usada pela máquina | 1.685 MiB de 2.048 MiB |

Esse teste em arquivo serviu para medir a VRAM e isolar o custo do STT. Ele não substitui os ensaios de reprodução ao vivo acima. O pico de VRAM é o uso total informado pelo driver, incluindo o Windows, não a memória exclusiva do Global Voice. Os dois tipos de ensaio mostram que **2 GB foram suficientes nestes casos**, com margem pequena; não provam que bastarão para qualquer reunião. Uma placa de 4 ou 6 GB daria mais margem para o modelo e outras aplicações, mas apenas a capacidade adicional não garante menor latência quando o STT já está rodando na GPU. Arquitetura e velocidade da placa também importam.

A tradução e a síntese foram medidas separadamente do teste de STT. A primeira carga de cada voz levou cerca de 2 a 3,5 s. Depois da carga, a síntese de uma frase levou cerca de 0,23 a 0,49 s. No corpus de 30 s, as 10 frases traduzidas do usuário somaram 25,1 s de voz e as 9 frases da reunião, 20,7 s. Se todas fossem reproduzidas em sequência, a maior espera calculada para começar a falar seria 1,17 s e 0,40 s, respectivamente. **Esse corpus não reproduziu o acúmulo grande observado ao vivo.** A medição não incluiu dispositivos físicos, VAD em tempo real, reprodução real ou a conversa específica do usuário.

## Mudanças para o próximo teste real

- O fim de fala agora libera o texto pendente assim que a pausa fecha o trecho. O resto de um corte forçado também recebe transcrição após silêncio, sem exigir nova fala.
- As vozes são carregadas em segundo plano no início da sessão, antes de chegar a primeira tradução.
- A fila mantém somente a frase mais recente enquanto a atual é reproduzida. Uma frase pendente há mais de 4 s é descartada; o texto continua no histórico. O aplicativo mostra um aviso quando isso acontece. Isso limita atraso acumulado à custa de omitir uma frase falada quando a saída não acompanha a conversa.
- O aviso existente de STT lento continua indicando tempo de processamento e espera pelo modelo. Os dois avisos permitem identificar a etapa que atrasou durante uma reunião real.

## Vozes locais para escuta

Foram baixadas alternativas Piper gratuitas e locais e geradas frases iguais por idioma. Cada modelo tem cerca de 60 MiB, exceto Sharvard com 73 MiB. Os tempos de síntese foram próximos; **naturalidade e pronúncia precisam de escuta humana**. As alternativas ainda não substituem as vozes do aplicativo nesta build.

| Idioma | Atual | Alternativas para comparar |
| --- | --- | --- |
| Português | [Faber](data/voice-previews/pt-br-faber.wav) | [Cadu](data/voice-previews/pt-br-cadu.wav), [Jeff](data/voice-previews/pt-br-jeff.wav) |
| Inglês | [LJ Speech](data/voice-previews/en-ljspeech.wav) | [Lessac](data/voice-previews/en-lessac.wav) |
| Espanhol | [Sharvard](data/voice-previews/es-sharvard.wav) | [Davefx](data/voice-previews/es-davefx.wav) |

O [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) é uma alternativa multilíngue para pesquisa. Seus próprios [dados de vozes](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) apontam fraqueza em frases curtas, comuns nos trechos de uma chamada. Por isso ele não foi incluído sem medir qualidade e tempo nesse uso.

## Validação manual necessária

O instalador `0.3.4` compilou e passou em instalação, abertura e desinstalação isoladas com o componente base. Esse teste não removeu o driver VB-CABLE já instalado na máquina.

1. Em uma chamada com as duas fontes ativas, falar continuamente e alternar com pausas. Confirmar que a última frase aparece após a pausa, sem precisar falar de novo.
2. Ativar as duas vozes. Observar se surge aviso de **STT lento** ou de **voz traduzida atrasada**, e se a voz deixa de acumular atraso por muitos trechos. Informar qual aviso apareceu e depois de quanto tempo.
3. Abrir Configurações via Alt-Tab, minimizar e reabrir, e salvar. Confirmar que a janela vem à frente sem demora perceptível e que o botão Salvar não fica com borda pontilhada.
4. Ao desinstalar esta versão, confirmar que **Desinstalar também o VB-CABLE** aparece marcado. Executar a remoção apenas quando não precisar mais do driver; verificar o pedido de reinicialização e, depois dela, o desaparecimento de CABLE Input/Output.
5. Ouvir as amostras da tabela com fones e indicar a voz preferida em cada idioma, com atenção a pronúncia de frases curtas. A escolha de vozes para o instalador depende dessa avaliação.

# Vozes da apresentação — primeiro incremento

As vozes padrão foram alteradas para **Cadu** (português), **LJ Speech**
(inglês) e **DaveFX** (espanhol), conforme a escuta do grupo. Os quatro modelos
Piper de aproximadamente 60 MiB estão preparados na pasta local da build e
foram conferidos por SHA-256. A seleção aprovada foi empacotada no instalador
0.3.8.

| Idioma | Padrão | Outra opção |
| --- | --- | --- |
| Português | [Cadu](data/voice-previews/pt-br-cadu.wav), masculina | Nenhuma por ora |
| Inglês | [LJ Speech](data/voice-previews/en-ljspeech.wav), feminina | [Joe](data/voice-previews/en-joe.wav), masculina |
| Espanhol | [DaveFX](data/voice-previews/es-davefx.wav) | — |

Em uma execução local da mesma frase por idioma, após carregar os modelos,
Cadu levou **0,38 s**, Dii **0,35 s**, LJ Speech **0,52 s**, Joe **0,37 s** e
DaveFX **0,32 s** para sintetizar a frase completa. São medições pontuais de
síntese, sem reprodução nem carga simultânea de STT; não predizem o atraso de
uma chamada. Os resultados detalhados permanecem no diagnóstico local.

A [Dii original](https://huggingface.co/OpenVoiceOS/pipertts_pt-BR_dii) é uma
voz feminina em português brasileiro criada a partir de uma voz de Portugal.
Seu repositório indica **CC BY-NC-ND 4.0** e exige crédito a TigreGotico Lda.
A [conversão usada nesta amostra](https://huggingface.co/csukuangfj/vits-piper-pt_BR-dii-high)
indica **CC BY-NC-SA 4.0**. Antes de distribuir a voz, será preciso optar pelo
modelo original, conferir a atribuição e evitar misturar termos divergentes.
Ela foi reprovada na escuta e não será incluída. As vozes Cadu, LJ Speech, Joe e
DaveFX têm cartões individuais no [catálogo oficial do Piper](https://huggingface.co/rhasspy/piper-voices/tree/main).

## Decisão após a escuta

O usuário aprovou Joe, considerou Cadu aceitável e reprovou Dii. Uma amostra
exploratória da voz Dora (Kokoro) levou cerca de **13,3 s** para sintetizar
**5,1 s** de áudio nesta CPU; foi descartada. Não há busca ativa por novas
vozes. Cadu é a única voz portuguesa incluída. A configuração ganhou a escolha
entre LJ Speech e Joe quando a tradução falada sai em inglês.

## Validação pendente

Testar LJ Speech e Joe em inglês na voz destinada à chamada e na voz ouvida
localmente, conforme o sentido da tradução escolhido.

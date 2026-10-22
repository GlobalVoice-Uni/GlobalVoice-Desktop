# Global Voice 0.4.1

## Entrega

- Integra a interface atualizada, o chat, a toolbar, as configurações e as
  vozes locais escolhidas para português, inglês e espanhol.
- A Home mantém espaço entre os botões e os cartões também na janela mínima.
  Na janela ampliada, os cartões sobem sem encostar nos botões. Os botões não
  retêm um destaque de foco depois de clicar ou alternar janelas.
- O instalador grava um identificador para cada instalação. Na primeira
  abertura, o idioma principal e o primeiro par selecionado são aplicados às
  configurações e à toolbar. Alterações posteriores do usuário persistem até
  uma nova instalação.
- O Argos traduz textos longos por frases e por blocos de até 64 tokens de
  origem, para evitar cortes na tradução de transcrições extensas.
- A segmentação da transcrição começa em 1,8 s e cresce gradualmente até
  2,4 s, sem uma pausa maior no terceiro trecho. Essa mudança foi validada
  pelo usuário na build candidata 0.4.

## Verificações

- 163 testes unitários e 9 testes de integração passaram.
- Um texto de prova de 120 palavras foi traduzido pelo modelo Argos instalado,
  e o resultado chegou até a última frase.
- Instalação, abertura e desinstalação passaram com o perfil básico.
- Instalação, abertura e desinstalação passaram com o perfil NVIDIA e com
  VB-CABLE previamente instalado. O driver existente foi preservado.
- Os testes do instalador preservaram as preferências de idioma do Windows.

## Componente de terceiros

O instalador contém o VB-CABLE original da VB-Audio como componente opcional.
O assistente identifica o fabricante, informa que é donationware e aponta
`vb-cable.com` para contribuições. A [página oficial de licenciamento](https://vb-audio.com/Services/licensing.htm)
permite a distribuição com outro aplicativo sob essas condições.

## Artefato

`GlobalVoice-Setup-0.4.1.exe` (796,82 MiB). SHA-256:

`89789B093DFE4EF969F600B88A78F83F8DB0582F0AB6546C50893EA7C85CF064`

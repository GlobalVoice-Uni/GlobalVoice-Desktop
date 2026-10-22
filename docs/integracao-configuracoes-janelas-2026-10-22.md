# Integração visual — configurações e janelas

Branch de trabalho: `codex/integracao-front-end`. A build desta etapa é a 0.3.9;
a 0.3.8 validada permanece disponível. Nenhuma alteração foi enviada ao remoto.

## Implementação

- Toolbar mais curta, com seletor de idiomas compacto e texto de status junto ao
  indicador. O desenho do microfone anterior foi preservado. O botão de áudio
  recebeu traço coerente com os outros ícones; a branch publicada do colega não
  contém esse botão nem um ícone correspondente.
- Home com logo e título maiores e mais próximos, cartões menores e altura
  reservada para o logo no tamanho mínimo da janela.
- Chat com barra de rolagem arredondada e redimensionamento pelas bordas e
  cantos, sem a antiga alça no canto inferior direito.
- Configurações reorganizadas em Básico, Voz, Idiomas e Avançado. O cabeçalho
  acompanha a aba; controles técnicos têm explicações ao passar o mouse.
  O hardware escolhido mostra confirmação verde ou aviso de fallback após
  iniciar. A aba de teste foi retirada da interface.
- Home oculta ao abrir toolbar ou configurações. Ela só retorna quando ambas
  estão fechadas. A toolbar representa o chat na barra de tarefas; o chat é uma
  janela auxiliar vinculada a ela. Alterações não salvas são resolvidas antes
  de fechar a toolbar quando configurações está aberta.

## Verificação automatizada

Os 77 testes de interface, configurações e integração passaram, incluindo a
transição entre janelas, o aviso de alterações pendentes, a geometria da home
no tamanho mínimo e o redimensionamento do chat pela borda esquerda. Capturas
sem tela confirmaram o layout da home, das quatro abas e da barra de rolagem.
Essas capturas não reproduzem as fontes nem a barra de tarefas do Windows.

O instalador **0.3.9** tem 796,80 MiB e SHA-256
`2c10587478a57825cfc7af5459fd11788fb87041c8157bcd01b176a89307552c`.
No teste temporário do perfil padrão, instalou, abriu o aplicativo e
desinstalou com sucesso. O perfil NVIDIA foi incluído na compilação, mas seu
uso real e a barra de tarefas ainda exigem validação manual.

## Validação manual pendente

1. Instalar a 0.3.9 e comparar a home em tamanho mínimo e maior: logo, título,
   cartões, botões e rodapé devem permanecer inteiros, sem sobreposição.
2. Conferir o espaço entre idiomas na toolbar, o texto junto à bolinha de
   status, o ícone de microfone preservado e o botão de áudio.
3. Rolar o chat com bastante texto e redimensioná-lo pelas quatro bordas e
   pelos quatro cantos. Conferir a posição e o aspecto da barra de rolagem.
4. Abrir as quatro abas de configurações e passar o mouse nas explicações da
   aba Avançado. Alterar modelo e detector, salvar e reabrir para verificar
   que os valores persistem.
5. Abrir configurações pela home e fechá-las; a home deve voltar. Iniciar,
   abrir configurações pela toolbar e fechar a toolbar: a home deve continuar
   oculta enquanto configurações estiver aberta. Fechar configurações: a home
   deve voltar. Repetir com uma alteração não salva e testar Salvar, Descartar
   e o X do aviso.
6. Com toolbar e chat abertos, verificar na barra de tarefas do Windows uma
   entrada do Global Voice que permita voltar às janelas.

Registrar aqui os resultados após a validação na máquina do usuário.

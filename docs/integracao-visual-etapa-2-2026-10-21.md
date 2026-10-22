# Integração visual — home, chat e toolbar

Referência visual: `origin/front_eric` em `578a944`. A composição da home foi
portada; a lógica de sessão, tradução, áudio e configurações segue na implementação
atual do Global Voice.

## O que mudou

- Home com a composição da referência, ícone atual, link do repositório e versão
  lida da instalação.
- Chat atual preservado, com fundo cinza translúcido na área de texto e borda
  discreta no lugar do contorno azul.
- Toolbar com botões maiores, contornos cinza, status curto e um botão de áudio
  ao lado dos controles de chat. O botão silencia apenas a tradução ouvida nos
  fones; a voz enviada à chamada continua ativa.
- Seleção entre LJ Speech e Joe quando o idioma falado pela tradução é inglês.
  Cadu continua como única voz portuguesa e DaveFX como voz espanhola.

## Verificação automatizada

As quatro vozes locais foram conferidas por SHA-256. Os 79 testes de voz, interface
de status, configurações e integração da sessão passaram. Isso inclui salvar
as configurações durante uma sessão sem reativar o microfone silenciado.
A home, o chat e a toolbar abriram em modo de renderização sem tela, e as capturas foram conferidas
visualmente. Essa renderização não valida o desenho das fontes no Windows real.

O instalador final **0.3.8** foi compilado com 796,64 MiB e SHA-256
`bc914ccfb43c5bd7d8c7aed3cc6dfc0c1929c1e8c738a00b8c6f1a3806d913e8`.
O perfil padrão do pacote final instalou, abriu o aplicativo e desinstalou
com sucesso em diretório temporário. O perfil NVIDIA passou pela mesma
verificação no pacote anterior à correção de interface. Joe está no pacote;
Dii e Dora não estão. O arquivo do instalador 0.3.7 foi preservado.

## Validação manual

Em 22/10/2026, o usuário instalou e testou a build 0.3.8 e confirmou que as
funcionalidades desta etapa estavam de acordo. Pediu ajustes de tamanho e
alinhamento na toolbar, da home e do chat; eles foram incorporados à etapa seguinte.

1. Instalar a build 0.3.8 e conferir home, ícone, versão e link do GitHub. O
   arquivo do instalador 0.3.7 permanece disponível para retorno.
2. Iniciar e conferir chat, toolbar, novo botão de áudio e ausência do contorno
   azul nas bordas externas. A home ainda mantém o comportamento de janela da etapa anterior; o
   ciclo de vida das janelas será tratado na etapa 4.
3. Com tradução da reunião para você ativa, mutar e reativar o botão de áudio.
   O chat deve continuar recebendo texto, e a voz destinada à chamada deve
   continuar independente.
4. Selecionar LJ Speech e Joe em Configurações > Voz; verificar a voz inglesa
   na chamada quando a saída for inglês e nos fones quando a reunião for
   traduzida para inglês.
5. Silenciar o microfone na toolbar, abrir as configurações e salvar uma mudança;
   o microfone deve continuar silenciado.

Os itens abaixo correspondem ao roteiro usado na validação inicial.

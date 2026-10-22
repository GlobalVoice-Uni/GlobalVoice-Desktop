# Fechamento da interface para a versão 0.4

Branch: `codex/integracao-front-end`. Esta etapa fecha os ajustes visuais
solicitados após a validação da 0.3.9. O commit e a publicação ficam após a
validação manual da 0.4.

## Alterações

- A home distribui a altura adicional entre apresentação, botões e cartões.
  Cartões, versão e GitHub mantêm distância estável da borda inferior. O texto
  da descrição voltou ao tamanho anterior.
- Os formulários Básico, Voz e Idiomas têm controles e espaçamentos mais
  confortáveis. A linha acima das abas saiu. O aviso do hardware fica entre
  o nome do campo e o seletor, sem deslocar o seletor.
- Na aba Avançado, os ícones `?` ficam junto aos campos e exibem a explicação
  ao passar o ponteiro. A roda do mouse sobre seletores e valores rola a
  página sem modificar esses valores.
- O botão Iniciar/Parar/Aguarde mantém o tamanho e o alinhamento com Falar.
  O menu de idiomas e suas áreas de destaque ocupam toda a largura do
  seletor. Chat e toolbar usam o mesmo azul próximo ao centro da home. A
  barra de rolagem do chat ficou mais estreita, arredondada e à direita.
- Aplicação e instalador passam a exibir 0.4. O número de versão de arquivo
  do instalador usa quatro componentes exigidos pelo Windows.

## Verificação automatizada

- 161 testes unitários e 9 testes de integração passaram, incluindo geometria da home em dois
  tamanhos, posição do indicador de hardware, rolagem da aba Avançado,
  largura das opções de idioma e espaço entre os botões da toolbar.
- Capturas sem tela foram inspecionadas nos tamanhos mínimo e ampliado da
  home e nas abas Básico e Avançado. Essas capturas confirmam geometria,
  mas o renderizador sem tela não reproduz fielmente as fontes do Windows.
- A instalação temporária da primeira build 0.4, com perfil básico, abriu o
  aplicativo e a desinstalação concluiu sem erros. O instalador atualizado
  ainda depende da validação manual da instalação e desinstalação.
- A build candidata `GlobalVoice-Setup-0.4-rc1.exe` foi gerada com o perfil
  NVIDIA opcional e VB-CABLE. Tamanho: 796,83 MiB; SHA-256:
  `da6350598baff396ad9277a3a116045aa32e05bd905ee492fdc3d2bd454a918e`.
  O instalador 0.4 anterior permanece preservado. A instalação e a
  desinstalação desta candidata ficaram para o teste do usuário.

## Ajustes após a primeira build 0.4

- O botão durante o download dos idiomas agora exibe apenas `Cancelar`.
- A home preserva margem inferior de 36 px e distância constante entre o
  slogan e os botões quando a janela cresce. As caixas de status em Voz têm
  altura de 34 px, como os seletores; os cartões de Idiomas têm 560 px, como
  os campos de Básico.
- O menu de idiomas perdeu o contorno azul e limpa o destaque ao fechar por
  clique externo. A barra de rolagem do chat ficou 2 px mais fina.
- Na fala contínua, os limites de áudio dos cinco primeiros trechos são
  1,8 s, 2,0 s, 2,2 s, 2,4 s e 2,4 s. O limite segue em 2,4 s, sem salto no
  terceiro trecho. O texto de cortes forçados é liberado gradualmente; a
  proteção de sobreposição na fronteira continua ativa. Uma pausa longa
  reinicia a progressão.

## Validação manual pendente

1. Instalar a build candidata e verificar instalação e desinstalação, a cargo
   do usuário.
2. Com áudio real e fala contínua após uma pausa, observar a chegada do texto
   desde o início até depois do quinto trecho. Verificar se o terceiro não
   introduz nova espera e se a fila de transcrição não cresce com o tempo.
   Repetir após outra pausa e, se possível, com reunião e microfone ativos.

Registrar aqui os resultados observados no Windows antes do commit e da
publicação do release.

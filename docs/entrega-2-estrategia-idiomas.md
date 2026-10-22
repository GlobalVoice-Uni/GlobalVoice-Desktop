# Entrega 2 — idioma principal e pacotes Argos

## Distribuição escolhida

Uma única página do assistente reúne o idioma principal na parte superior
(PT-BR por padrão, EN ou ES) e os dois pares diretos correspondentes abaixo.
O nome de cada par começa pelo idioma adicional: com base EN, por exemplo,
"Português ↔ Inglês" e "Espanhol ↔ Inglês". O primeiro par vem marcado; o
usuário pode escolher ambos ou nenhum. A escolha do idioma da interface do
instalador é independente do idioma principal do aplicativo. Os pacotes Argos
ficam fora do executável do instalador: ao instalar, o assistente baixa somente
os pares escolhidos por HTTPS em uma única tela, mantém ambos os pares visíveis
durante as transferências sequenciais, mostra o progresso, valida os
arquivos e instala os dois sentidos. É necessária internet durante esta etapa.

| Idioma Principal | Pares oferecidos |
| --- | --- |
| Português (Brasil) | Inglês ↔ Português; Espanhol ↔ Português |
| Inglês | Português ↔ Inglês; Espanhol ↔ Inglês |
| Espanhol | Português ↔ Espanhol; Inglês ↔ Espanhol |

Os URLs do assistente fixam as versões atuais do catálogo oficial Argos. A
aplicação consulta o [catálogo oficial](https://github.com/argosopentech/argospm-index/blob/main/index.json)
quando o usuário adiciona outro par em **Configurações > Idiomas**. Lá também
é possível mudar o idioma principal; a lista acompanha a mudança e permite instalar
outros pares. A tela informa quando a base escolhida ainda não tem nenhum
par instalado; o idioma principal não precisa de pacote próprio. O par ES ↔ Português
usa o modelo oficial `pt` (português genérico), enquanto PT-BR ↔ EN usa `pb`.
Não há idioma intermediário. O ícone do executável, da janela e do instalador
passa a ser `frontend/assets/newicon.ico`.

Na instalação administrativa, os modelos ficam em
`%PROGRAMDATA%\GlobalVoice\translation` e podem ser usados por qualquer perfil.
Na instalação por usuário (`/CURRENTUSER`), ficam em
`%LOCALAPPDATA%\GlobalVoice\translation`. A aplicação também guarda nesse
último local os pares adicionados depois. Um pacote compartilhado não pode
ser removido sem privilégios de administrador; a tela o marca como **Na
instalação**. Pares adicionados pelo usuário continuam removíveis.

A escolha do idioma principal inicializa somente um perfil ainda não configurado.
Reinstalações preservam as preferências existentes. A tradução é local depois
da instalação dos modelos.

## Tamanho dos downloads

Medido por `Content-Length` dos seis arquivos do catálogo em 13/10/2026,
sem baixar os modelos. Os valores mostrados são aproximados.

| Par bidirecional | Download (MiB) |
| --- | ---: |
| EN ↔ PT-BR | 129,34 |
| ES ↔ PT | 128,76 |
| EN ↔ ES | 355,45 |

A revisão de teste `0.1.0.2` foi gerada em 13/10/2026. O instalador
compactado ocupa 543,78 MiB e seu SHA-256 é
`2B10463F125060646CD583C2EA9B32C6B3E09990C0DD2886B2A2BBEAD5D2E706`.
A suíte da venv passou com 109 testes. A compilação do Inno validou a página
única de idioma principal e pares. A instalação, a abertura e a desinstalação
automáticas passaram na versão compactada com o perfil base. Esses testes
usaram `/PAIRS=none`, portanto a exibição da página e o download real dos
pacotes continuavam pendentes de validação manual. Na validação externa, os
fluxos de idioma foram aprovados, mas o ícone antigo ainda apareceu no
aplicativo. A inspeção do executável mostrou o ícone novo embutido; a causa
provável é o cache do Windows. A revisão `0.2.2` passa a instalar um arquivo de
ícone com nome versionado para os atalhos e usa uma nova identidade de janela na
barra de tarefas. O número `0.1.0.2` foi um erro de sequência: o instalador
`0.2.1` já existia, enquanto os padrões do script de build e do Inno ainda
estavam em `0.1.0`.

A build `0.2.2` foi gerada em 13/10/2026 com versão de produto e arquivo
`0.2.2`. O instalador ocupa 543,76 MiB e tem SHA-256
`5DE8B62BE289E49E25757C0A70ACE18A83185A4E63C76543CAFAA0AA2C754EC1`.
Os 109 testes da venv passaram. A compilação validou o código da página única
de downloads. O ícone extraído do novo executável tem os mesmos pixels de 32 px
do `newicon.ico`. No smoke test da instalação por usuário com `/PAIRS=none`, o
ícone instalado tinha o mesmo SHA-256 do arquivo fonte, a aplicação abriu e a
desinstalação concluiu. O teste automatizado não baixou modelos nem verificou
visualmente o ícone na barra de tarefas; essas verificações são manuais.

## Retorno da validação manual — 14/10/2026

Na instalação usada pelo grupo, a transcrição e a tradução continuaram
funcionando após desconectar a rede. O retorno confirma o uso offline depois
da instalação dos pacotes; não contém medições de latência nem cobre todos os
pares e dispositivos. A contagem “1 de 2 pares instalados” foi retirada da
tela de idiomas. O controle passa a se chamar **Idioma Principal** no
aplicativo e no instalador. Ao fechar as configurações com alterações não
salvas, a aplicação pergunta se deve descartá-las ou continuar editando.

A revisão `0.2.3` contém esses ajustes de interface. O instalador ocupa
543,75 MiB e seu SHA-256 é
`E84CE6C60A12EAA9F6542058306A593E0FCA3FF3C6BEF6B0DB52B7AB5202B67A`.
Os 110 testes automatizados passaram. O smoke test instalou a base, abriu o
aplicativo, conferiu o ícone instalado e desinstalou sem erro. O teste de
instalação não baixou modelos; a validação offline relatada acima ocorreu na
instalação utilizada pelo grupo.

## Validação manual pendente

Na build `0.2.3`:

1. Abrir o instalador e verificar que idioma principal e pares estão na mesma página. Alternar PT-BR, EN e ES e conferir que os dois pares mudam imediatamente, com o idioma adicional primeiro e sem "(Brasil)" nos nomes dos pares.
2. Conferir o novo ícone no instalador, no executável, no menu Iniciar, no atalho da área de trabalho, na barra de tarefas, na janela e na lista de aplicativos instalados. Se houver um atalho antigo fixado na barra de tarefas, desafixá-lo e fixar o novo.
3. Se instalar **os dois pares**, conferir que ambos aparecem na mesma tela durante todo o download. As transferências continuam sequenciais nesta revisão; o funcionamento offline após instalar já foi confirmado para a instalação utilizada pelo grupo.
4. Em **Configurações > Idiomas**, confirmar o rótulo **Idioma Principal**. Com um ou dois pares instalados, não deve haver mensagem de contagem. Se a seleção não tiver nenhum par instalado, deve aparecer apenas o aviso para instalar um dos pares.
5. Alterar uma configuração e fechar a janela: **Continuar editando** mantém a janela e a mudança; **Descartar** restaura o último valor salvo. Após salvar, fechar não pede confirmação.

O teste de fumaça automatizado do instalador usa `/PAIRS=none` para verificar
a estrutura sem baixar modelos grandes.

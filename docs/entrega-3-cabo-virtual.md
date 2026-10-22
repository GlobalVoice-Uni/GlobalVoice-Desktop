# Entrega 3 — rota da chamada pelo cabo virtual

## Decisão para a build de avaliação

O Windows não oferece uma entrada de microfone genérica em que o GlobalVoice
possa injetar áudio no microfone físico. Esta build inclui o **VB-CABLE da
VB-Audio** como componente opcional do instalador do GlobalVoice. O driver não
é código do GlobalVoice: o pacote original é obtido do fornecedor durante a
compilação, verificado por SHA-256 e assinatura, e incluído sem alterar seus
arquivos. Após os downloads dos idiomas, o instalador do GlobalVoice executa
o setup original da VB-Audio em modo oculto, verifica o serviço instalado e
mostra sua própria etapa de reinicialização. A instalação pede administrador.
O usuário não precisa baixar outro aplicativo separadamente.

A chamada deve selecionar **CABLE Output** uma vez. O GlobalVoice escreve em
**CABLE Input**. Quando a opção de enviar voz traduzida está ligada, a saída
contém o TTS da tradução. Quando está desligada e uma sessão com microfone está
ativa, o aplicativo encaminha a voz original diretamente do callback de
captura, antes do STT/VAD. Mudo e apertar para falar também controlam essa rota.
Com o GlobalVoice fechado, o cabo não recebe áudio; para falar nessa situação,
a chamada precisa usar novamente o microfone físico.

Na tela **Voz**, a saída de áudio para ouvir a tradução da reunião inclui a
saída padrão do Windows. Quando ela é também a saída capturada por loopback,
o GlobalVoice pausa essa captura durante a reprodução da própria voz
sintetizada e por 350 ms após ela terminar, para evitar realimentação. Trechos
da fala alheia que coincidirem com a reprodução podem não ser transcritos;
essa limitação precisa ser avaliada no teste de chamada.

O callback do encaminhamento mantém no máximo 20 ms de amostras pendentes e
descarta as antigas para evitar atraso crescente. Para esta máquina, o
microfone padrão do PortAudio via MME informa latência mínima de entrada de
90 ms; o mesmo microfone via WASAPI informa 3 ms. Por isso o encaminhamento
seleciona o alias WASAPI do microfone padrão. **Esses números são valores
informados pelos dispositivos, não uma medição do atraso adicional completo.**

## Critério de aceite: até 30 ms adicionais

O caminho microfone → GlobalVoice → VB-CABLE → entrada da chamada precisa ser
medido no computador de teste. A ferramenta
`diagnostics/measure_virtual_cable_latency.py` grava em memória, durante oito
segundos, o microfone físico e o CABLE Output ao mesmo tempo. Algumas palmas
perto do microfone produzem transientes para correlação. A ferramenta imprime
o atraso entre as duas capturas e uma pontuação de correlação; abaixo de 0,15,
o resultado é inconclusivo. Ela não cria arquivo de áudio.

Execute no repositório, com a venv e uma sessão do GlobalVoice iniciada com
**Enviar voz traduzida à chamada** desmarcado:

```powershell
.\.venv\Scripts\python.exe -m diagnostics.measure_virtual_cable_latency
```

**Resultado real:** pendente. O VB-CABLE foi instalado para o teste manual da
`0.3.2`, mas o atraso completo ainda não foi medido. A rota só estará validada se o teste mostrar
até 30 ms, com correlação suficiente e sem cortes audíveis. Se o valor exceder
o limite, a rota deve ser revista antes de ser escolhida para a versão de entrega.

## Validação manual da build 0.3.2

1. Instale `GlobalVoice-Setup-0.3.2.exe`. Na página de componentes, deixe
   **VB-CABLE da VB-Audio** marcado. Confirme que, após os idiomas, aparece a
   etapa **Instalando microfone virtual** sem janela separada da VB-Audio.
   No fim, escolha **Reiniciar agora** ou **Reiniciar depois** e reinicie antes
   de testar a voz. Se o VB-CABLE já estiver instalado, essa etapa e o pedido
   de reinício serão ignorados; valide o fluxo completo em uma máquina sem o
   driver ou em uma VM.
2. Abra **Configurações > Voz** e confira **CABLE Output (VB-Audio) disponível**
   e **Saída de Áudio** no headset padrão do Windows.
   Na aplicação de chamada, escolha **CABLE Output** como microfone.
3. Inicie uma sessão com **Microfone** ou **Microfone e reunião**, com **Enviar
   voz traduzida à chamada** desligado. Confira que a chamada recebe a voz
   original, inclusive após usar mudo e apertar para falar. Execute o comando
   de medição acima e registre atraso e correlação; o aceite é até 30 ms.
4. Ligue **Enviar voz traduzida à chamada**, reinicie a sessão e confira que
   a chamada recebe o TTS traduzido. Verifique que a voz original não sai ao
   mesmo tempo.
5. Use **Áudio da reunião** ou **Microfone e reunião**, ative **Ouvir tradução
   da reunião** e confirme que a voz traduzida sai no headset escolhido. Observe
   se há eco ou se frases da reunião somem durante a voz sintetizada.

Se a medição for inconclusiva ou a chamada receber cortes, anote o dispositivo
de microfone físico e a taxa de amostragem apresentados pelo Windows para
reproduzirmos o problema.

## Licença e distribuição

O VB-CABLE é fechado e donationware. A [página oficial de licenciamento](https://vb-audio.com/Services/licensing.htm)
permite distribuir o pacote com outro aplicativo sob condições de identificação
e participação, e indica licença paga para alguns usos profissionais. O
`readme.txt` do pacote pede acordo com o autor para integrar o VB-CABLE ao
procedimento de instalação de outro software, enquanto a página pública de
licenciamento permite a distribuição conjunta com crédito e donationware.
Essa divergência precisa ser esclarecida com a VB-Audio antes de distribuir
uma versão de produção. O modo oculto usa `-i -h`, empregado em integrações
externas, mas não documentado no manual do fabricante; por isso a instalação
real requer validação manual. A [página oficial do produto](https://vb-audio.com/Cable/)
explica os endpoints e a exigência de reinicialização.

Pacote conferido: `VBCABLE_Driver_Pack45.zip`, SHA-256
`b950e39f01af1d04ea623c8f6d8eb9b6ea5c477c637295fabf20631c85116bfb`.
O executável `VBCABLE_Setup_x64.exe` desse pacote apresentou assinatura
Authenticode válida na análise local.

## Verificação automatizada

Os testes cobrem descoberta do par correto de endpoints, preferência WASAPI,
recusa de pacote alterado, proteção contra caminhos fora do diretório ao
extrair, descarte de áudio antigo, mudo, escolha automática de CABLE Input no
bridge e recuperação de um atraso sintético conhecido pela ferramenta de
medição. Isso verifica a lógica; não substitui a medição de latência e o teste
de chamada real.

Na venv do projeto, **132 testes passaram** na build anterior. O instalador `0.3.1` foi compilado
com o pacote VB-CABLE incluído (752,51 MiB, SHA-256
`ae18b552e0f1224aff47ab071d3d6f1913e86ea833c4e44340ae320fa34fad26`).
Um teste de instalação com o componente `base`, sem o driver, instalou, abriu
e desinstalou o aplicativo com êxito. A instalação efetiva do VB-CABLE, a
reinicialização, a chamada real e a medição de latência aguardam validação
manual.

Na build `0.3.2`, **135 testes automatizados passaram**. A compilação incluiu
o novo indicador visual dos checkboxes e o instalador final tem 752,53 MiB,
SHA-256 `17bc7ce41f410a94df00748a1388423a55c6b2ce9476c92baae4c90f4902afd`.
Na máquina de desenvolvimento, a tela Voz selecionou o headset padrão pelo
endpoint WASAPI. Um teste local instalou, abriu e desinstalou o componente
base da `0.3.2` com êxito. Naquele momento, a instalação do VB-CABLE e as
rotas de voz ainda aguardavam o teste manual descrito a seguir.

## Retorno manual da build 0.3.2 e correções da 0.3.3

O teste manual da `0.3.2` confirmou que a voz ouvida no fone está limpa. A voz
recebida pela chamada através do microfone virtual ficou muito poluída e com
som alterado. As opções **Enviar voz traduzida à chamada** e **Ouvir tradução
da reunião** também continuaram produzindo voz após serem desmarcadas.

A causa comprovada das duas opções é a leitura das preferências do Windows:
`"false"` era tratado como verdadeiro por ser uma string não vazia. A `0.3.3`
converte explicitamente os valores booleanos; quando a opção está desligada,
nenhum sintetizador nem fila de voz é criado para essa rota. A tradução em
texto continua conforme o modo de exibição escolhido.

Na saída para o VB-CABLE, a `0.3.3` duplica a voz nos dois canais estéreo do
endpoint e aplica margem de 6 dB antes de escrevê-la. A saída do Piper para
uma frase de teste chegou a 1,0 de pico antes desse ajuste. O manual da
[VB-Audio](https://vb-audio.com/Cable/VBCABLE_ReferenceManual.pdf) indica que
os endpoints são estéreo a 48 kHz por padrão. Isso corrige o formato enviado
e reduz a chance de saturação, mas a causa exata do áudio poluído na chamada
depende de novo teste manual; o aplicativo de chamada também processa seu
microfone.

No instalador `0.3.3`, o componente aparece como **VB-CABLE (Microfone Virtual
para Voz Sintetizada)** e começa marcado mesmo quando o driver já está
presente. Nesse caso, a reinstalação do driver é dispensada.

**Validação manual da 0.3.3:** instale a build e confira o texto e a seleção
do componente. Em Configurações > Voz, desmarque as duas opções, salve e inicie
uma nova sessão com microfone e reunião: a voz traduzida não deve sair em
nenhuma das rotas, enquanto o texto continua disponível. Depois ative apenas
**Enviar voz traduzida à chamada**, reinicie a sessão e compare a voz recebida
na chamada com a voz limpa do fone. Por fim, ative apenas **Ouvir tradução da
reunião** e confirme que ela sai somente no fone. Registre separadamente se
há cortes, distorção ou processamento de ruído na chamada. O atraso adicional
da voz original permanece sujeito à medição de até 30 ms.

**Verificação automatizada da 0.3.3:** 138 testes passaram na venv do projeto,
incluindo leitura das duas opções desmarcadas, ausência de TTS nessas rotas e
formato estéreo com margem de amplitude para o cabo virtual. O instalador
compilou com o pacote oficial do VB-CABLE verificado e assinatura válida;
tem 752,58 MiB e SHA-256
`84ee5a6094a288385ddce344cc4ab5c252fa103deaa111c8e4c6a6019157c860`.
Um teste automatizado instalou, abriu e desinstalou o componente base da
`0.3.3` com êxito. O instalador `0.3.2` e seu executável foram preservados
para comparação. O teste de chamada e a instalação real do driver nesta
versão seguem pendentes de validação manual.

## Correção da instalação na 0.3.5

O teste manual da `0.3.4` encontrou uma regressão: depois de remover o
VB-CABLE, marcar o componente no instalador apenas copiava os arquivos. Mesmo
após reiniciar, o microfone virtual não aparecia. Os registros de duas
instalações em 21/10/2026 mostram `Need to restart Windows? No`. A chave de
serviço `VBAudioVACMME` ainda existia após a remoção e enganava a verificação
do instalador. Não havia instância do dispositivo em `...\VBAudioVACMME\Enum`.

Na `0.3.5`, a presença do dispositivo é verificada pelo número de instâncias
PnP, não pela existência isolada da chave de serviço. Se a instalação for
executada, a tela final exige uma escolha clara entre reiniciar agora e
reiniciar depois; o aplicativo não abre automaticamente antes do reinício.
A tela Configurações > Voz diferencia **reinício pendente**, **driver sem
endpoint disponível** e **não instalado**. Nos dois últimos estados, o botão
instala ou repara o VB-CABLE. Ele usa o pacote incluído; se esse componente
não foi selecionado antes, baixa o ZIP oficial e confere seu SHA-256.

**Validação manual pendente:** instalar a `0.3.5` com VB-CABLE marcado no PC
sem o driver. Confirmar que a etapa de instalação do microfone virtual ocorre
depois dos idiomas e que a tela final pede reinício. Escolher **Reiniciar
depois**, abrir Configurações > Voz e verificar o aviso de reinício pendente.
Após reiniciar, verificar que **CABLE Output** está disponível e que a voz
traduzida chega à chamada. Se o dispositivo não aparecer, testar o botão
**Instalar/Reparar VB-CABLE** e registrar a mensagem apresentada. Testar
também a instalação pelo botão quando o componente VB-CABLE não foi escolhido
no instalador.

No desinstalador da mesma versão, a descrição quebra a linha após
"microfone virtual", a opção passa a se chamar **Desinstalar driver
VB-CABLE** e o foco inicial vai para **Continuar**, evitando o contorno
pontilhado na caixa de seleção. Conferir esses três pontos antes de confirmar
a remoção; a caixa deve continuar marcada por padrão.

**Verificação automatizada da 0.3.5:** 138 testes unitários passaram na venv,
incluindo a distinção entre dispositivo ausente e reinício pendente. O
instalador compilou e preservou a `0.3.4`; o arquivo da `0.3.5` tem 752,47
MiB e SHA-256
`a902c9e65e13aa1e1e2da4204b340e3a6a7cf8d2cc902f47df175afc51210cf6`.
A instalação real do driver e a tela de reinício continuam pendentes do teste
manual descrito acima.

## Correção da instalação e do roteamento na 0.3.6

O registro da instalação de 21/10/2026 mostrou que a falha `500 Internal
Server Error` veio do download do modelo Argos `en_pb`, no endereço informado
pelo catálogo. Ela ocorreu antes da etapa do VB-CABLE. O instalador já havia
copiado a aplicação e, após a exceção, abriu a tela de conclusão e executou o
programa. Não há evidência de falha do driver nessa tentativa porque sua etapa
nem começou.

A 0.3.6 usa o espelho oficial de modelos do Argos no instalador. Os downloads
ocorrem antes da cópia dos arquivos: se um par falhar, a página de preparação
mostra um aviso legível e permite tentar de novo ou desmarcar o par. No
aplicativo, o gerenciador de idiomas tenta esse espelho antes do endereço do
catálogo. Falhas posteriores de instalação dos idiomas ou do VB-CABLE são
registradas como instalação incompleta na tela final, impedem a abertura
automática do aplicativo e geram código de saída diferente de zero.

O indicador de reinício do VB-CABLE agora tem prioridade mesmo quando o Windows
já enumera o cabo antes de reiniciar. O botão **Instalar/Reparar** fica ao lado
de um estado curto em Configurações > Voz. A tela mostra qual saída padrão do
Windows está sendo capturada para a reunião. Se ela for **CABLE Input**, o
aplicativo explica como trocar a saída padrão para o headset ou alto-falante;
**Saída de Áudio** nas configurações continua sendo apenas o retorno da voz
traduzida. Avisos de erro da aplicação deixam de bloquear as outras janelas.

**Verificação automatizada:** 141 testes unitários e 9 de integração passaram
na venv. O script do instalador compilou com Inno Setup 7.1.0. Uma instalação
silenciosa isolada do componente base instalou, abriu e desinstalou a aplicação
com êxito. O instalador 0.3.6 tem 752,51 MiB e SHA-256
`82d0e5c2983c2179730427d58c56be7953ef51e76fa1c4310e691050bcffc41f`.
A instalação real dos idiomas e do VB-CABLE, a tela final de reinício e a
interação das janelas seguem para validação manual.

**Validação manual da 0.3.6:** selecione português principal, inglês e
VB-CABLE no instalador. Confirme que a tela de idiomas baixa o par antes da
cópia do aplicativo, que a etapa do VB-CABLE vem por último e que a conclusão
pede reinício quando o driver é instalado. Sem reiniciar, feche e abra o
Global Voice e confira que Configurações > Voz continua mostrando **Reinicie o
PC**. Após reiniciar, verifique **CABLE Output disponível**. Se o VB-CABLE
estiver realmente ausente, confira o botão **Instalar** na mesma linha do
estado. No modo Microfone e reunião, deixe seu headset como saída padrão do
Windows e confirme que a sessão inicia; depois selecione CABLE Input como
saída padrão do Windows e confira a orientação específica, mesmo se a **Saída
de Áudio** da voz traduzida continuar no headset. Abra um aviso de erro,
minimize-o e feche chat/toolbar: essas janelas devem responder normalmente.
Para verificar a falha de download, desconecte a rede antes de clicar em
**Instalar** com um par selecionado: o assistente deve ficar na preparação,
mostrar um aviso claro e não concluir a instalação. Reconecte a rede e tente
novamente na mesma tela.

## Ajuste de disponibilidade e cancelamento na 0.3.7

Em 21/10/2026, o Windows havia iniciado às 15:32 e o VB-CABLE foi instalado
pelo aplicativo às 16:03. Assim, o marcador de reinício ainda era válido quando
o instalador 0.3.6 foi executado com o driver já presente. A atualização não
reinstalou o driver, mas o aplicativo bloqueou a voz da chamada só pelo
marcador. Fora da sandbox de desenvolvimento, as duas pontas do cabo abriram
com sucesso sem reproduzir nem gravar áudio.

A 0.3.7 só exige reinício enquanto o marcador estiver pendente **e** a rota
virtual ainda não puder ser aberta. Se as duas pontas já funcionarem, a voz
na chamada fica disponível mesmo após uma atualização. A verificação abre e
fecha os endpoints sem iniciar captura ou reprodução. No desinstalador,
**Desinstalar driver VB-CABLE** começa desmarcado para preservar um driver que
já existia antes do Global Voice.

O botão nativo de cancelar o download já existia. Ele foi alinhado à área
inferior dos botões do assistente e a interrupção pelo usuário agora mostra
**Download cancelado**, em vez de ser tratada como falha do servidor. Cancelar
volta à página de preparação, onde é possível tentar de novo, mudar os pares
ou sair; nenhum arquivo da instalação é aplicado nessa tentativa.

**Verificação automatizada:** 142 testes unitários e 9 de integração
passaram. A build do aplicativo e o instalador 0.3.7 compilaram. O teste de
instalação isolada com o componente VB-CABLE marcado e já presente no Windows
instalou, abriu e removeu o aplicativo sem reinstalar o driver nem registrar
novo reinício; o dispositivo permaneceu registrado após a desinstalação. O
instalador tem 752,55 MiB e SHA-256
`7a6e41e27355330e2c6e9a613412bd7fda5989c71b76e54380293fd998808adf`.
O aspecto visual do botão e o cancelamento durante um download real seguem
pendentes da validação manual.

**Validação manual da 0.3.7:** com VB-CABLE já funcional, atualize o Global
Voice com o componente marcado e confirme que a voz para a chamada pode ser
ativada sem reiniciar. Durante um download de idioma, confira o botão
**Cancelar download** alinhado aos outros botões, clique nele e verifique a
mensagem de cancelamento na página de preparação. Por fim, abra o
desinstalador apenas até a escolha do driver e confira que a caixa começa
desmarcada; cancele a desinstalação se quiser manter o aplicativo.

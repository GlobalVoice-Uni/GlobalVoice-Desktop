# Integração de vozes e interface — plano de execução

Base funcional: `entrega-2-escuta-texto`. Referência visual: `origin/front_eric`
em `578a944` (a branch local `front_eric` está um commit atrás). A referência
visual contém código anterior aos recursos atuais de áudio, idiomas, instalador
e avisos; serão portadas apenas as partes de interface necessárias.

O atraso observado no uso simultâneo de transcrição e voz será documentado como
limitação medida do protótipo acadêmico. Este trabalho não presume que outra voz
ou a integração visual vá eliminá-lo.

## Etapas

1. **Vozes.** Aplicar Cadu como única voz em português, LJ Speech e Joe como
   opções em inglês e DaveFX em espanhol. Dii foi reprovada na escuta; Dora
   foi descartada pelo custo de síntese. A busca por outras vozes fica para
   depois da integração. Validar a seleção inglesa e as duas saídas de áudio.
2. **Home, chat e toolbar.** Portar a home da referência com o ícone atual,
   versão única do projeto e link funcional. Manter o chat funcional atual,
   ajustar fundo e retirar contornos azuis. Portar o visual da toolbar com um
   botão de áudio integrado, sem os pontos de arrasto, o botão de chat duplicado,
   o separador e o indicador de segundos. Preservar todos os controles atuais.
3. **Configurações.** Manter o código funcional e aplicar o visual seletivamente.
   Reorganizar em Básico, Voz, Idiomas e Avançado, com cabeçalho por aba,
   explicações nos controles avançados, seleção de hardware com aviso de
   fallback e rótulos revisados. Preservar tamanho mínimo, dropdown, hover,
   instalação de idiomas/driver e aviso de alterações não salvas.
4. **Janelas e fechamento.** Esconder a home enquanto houver toolbar/chat ou
   configurações. Restaurá-la somente quando todas essas janelas forem fechadas.
   Manter o aviso de alterações pendentes ao fechar configurações. Agrupar
   chat/toolbar em uma entrada de barra de tarefas e validar Alt+Tab, foco e
   fechamento com diálogo modal aberto.

Cada etapa passa por testes automatizados pertinentes antes de pedir a validação
manual correspondente. Após a validação manual da etapa 2, abrir a branch de
integração antes dos commits. Comitar em português somente após validar as
mudanças. Não enviar commits ao remoto sem autorização.

## Decisões de escopo

- O código de `front_eric` para backend, captura, configurações antigas e
  arquivos compilados não será mesclado diretamente; ele substituiria fluxos
  já funcionais.
- A home da referência contém versão fixa `0.1.0`; a versão será lida da mesma
  fonte usada na build para não divergir do instalador.
- O catálogo oficial Piper oferece apenas vozes masculinas em pt-BR. Por ora,
  Cadu é a única opção em português. A busca por outra voz foi adiada pelo usuário.

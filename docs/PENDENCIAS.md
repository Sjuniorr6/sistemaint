# Pendências

Ordenadas por quando mordem. Item fechado sai daqui; item cujo escopo mudou é reescrito.

## requisicao — requisição com vários modelos (ItemRequisicao)

- **N1 — ramo "Isca FAST / Estoque Antenista" da criação provavelmente quebrado
  (anterior a esta mudança).** `Requisicoes.antenista` é texto, mas
  `estoque_antenista.nome` é FK para `Antenista`: o `get_or_create(nome=<texto>)` deve
  levantar erro e a tela cai em "Ocorreu um erro ao processar a requisição". E
  "Estoque Antenista" nem está nas opções de motivo. Gatilho: criar requisição com
  motivo Isca FAST e antenista. A movimentação agora é por modelo, mas o defeito de
  origem continua.
- **N2 — só a quantidade dos modelos é editável.** Na edição da requisição
  (`requisicao_update`) a quantidade de cada modelo e a lista de IDs são editáveis e o
  resumo é recalculado; trocar o tipo de produto, a customização ou o valor unitário de
  um modelo, ou incluir/remover modelos, ainda exige o admin. Nas edições pela
  Configuração e pelo Setor Técnico os modelos seguem só leitura.
- **N2 — expedição parcial só para requisição de um modelo.** Com vários modelos, o
  kanban recusa a parcial (a conta de sobra e cobrança é de um produto). Gatilho:
  expedir parte de uma requisição mista.
- **N3 — `configuracao_update2.html` sem view.** Não foi migrado para os itens.

## registrodemanutencao — entrada com vários tipos de produto (ItemEntrada)

- **N2 — `manutencaolist` cria entrada sem itens.** O app `manutencaolist` (rota
  `manutencaolist/manutencaocreate`, sem link em menu) reaproveita o `FormulariosForm`
  mas não passa pelo service `criar_entrada`. Se alguém usar a rota, a entrada nasce sem
  tipo de produto. Gatilho: acesso direto pela URL. Saída: apontar a rota para a
  `FormulariosCreateView` do `registrodemanutencao` ou remover o app.
- **N3 — templates de produto sem uso.** `setor_config.html` e `laudos_list.html` leem
  `tipo_produto` da entrada, mas nenhuma view os renderiza; `config_detail.html` é de
  requisição. Não foram migrados para os itens.
- **N2 — só os nºs dos tipos de produto são editáveis.** Na edição da entrada os nºs de
  cada tipo de produto podem ser corrigidos (quantidade recalculada); trocar tipo de
  produto/customização/contrato ou incluir/remover tipos ainda exige o admin. Nº novo só
  aparece no select do laudo depois de salvar. Na edição pela Configuração (requisicao)
  os itens seguem só leitura.

## iscas — devolução, pedido por tipo e valores

- **N1 — rodar as migrações 0014, 0015 e 0016 do `iscas` contra dump restaurado de
  produção antes do deploy.** A 0015 preenche `ItemSolicitacao.tipo` a partir do
  modelo; no banco local havia pedido com dois modelos do mesmo tipo (#16), o caso
  que só aparece com dado real. Gatilho: o próximo deploy.
- **N2 — spec desatualizada sobre ISC-RN-05.** A regra passou de "descartável
  entregue é terminal" para "descartável entregue só sai do cliente por devolução"
  (defeito → substituição). O código (`services/custodia._eh_terminal`) já reflete;
  a spec do app iscas, não. Gatilho: a próxima pessoa que ler a spec para mexer em
  custódia.

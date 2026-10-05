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
- **N2 — modelos não editáveis após a criação.** Na edição (comercial, configuração,
  técnico) modelo/quantidade/customização são só leitura; valor unitário/total seguem
  editáveis. Corrigir um modelo exige o admin (inline "Item requisicao").
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
- **N2 — itens não editáveis após a criação.** Decisão de escopo: na edição (laboratório
  e configuração) os tipos de produto são somente leitura. Corrigir um nº digitado
  errado exige o admin (inline "Item entrada").

# Pendências

Ordenadas por quando mordem. Item fechado sai daqui; item cujo escopo mudou é reescrito.

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

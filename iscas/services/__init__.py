"""Camada de Services do Iscas Fast — toda regra de negócio vive aqui.

Views e forms orquestram, nunca implementam regra. Services recebem dados já
validados e o `usuario` autor como parâmetro explícito; nunca leem `request`.

O ponto de escrita único do livro-razão é
`iscas.services.custodia.registrar_movimentacao()` — nenhum outro módulo cria
`Movimentacao` / `MovimentacaoUnidade` (ISC-ADR-02).
"""

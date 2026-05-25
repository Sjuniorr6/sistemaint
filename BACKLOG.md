# Backlog — SCA (Sistema de Controle Administrativo)
**Grupo Golden Sat — Sistema INT**

> Última atualização: 2026-05-20

---

## 🗺️ Ordem de execução
M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9 → M10

---

## ✅ MÓDULO 1 — Base do sistema
> Concluído em 2026-05-13

- [x] Criar o app `controle_administrativo`
- [x] Configurar `apps.py` com `verbose_name`
- [x] Registrar em `INSTALLED_APPS`
- [x] Criar `urls.py`, `services.py`, `selectors.py`
- [x] Registrar URL `/controle-administrativo/` no roteador central
- [x] Commit: `feat(sca): scaffold inicial do app controle_administrativo`

---

## ✅ MÓDULO 2 — Models e banco de dados
> Concluído em 2026-05-13

- [x] Escrever todos os models em `models.py`
- [x] `FuncionarioAdministrativo`
- [x] `CategoriaTarefaAdministrativa`
- [x] `TarefaModeloAdministrativa`
- [x] `ExecucaoTarefaAdministrativa`
- [x] `BlocoSemanal`
- [x] `ItemBlocoSemanal`
- [x] Registrar todos no `admin.py`
- [x] Rodar `makemigrations`
- [x] Revisar o arquivo de migration gerado
- [x] Rodar `migrate`
- [x] Confirmar que o servidor sobe sem erros
- [x] Commit: `feat(sca): models e migrations`

---

## ✅ MÓDULO 3 — Painel principal (semana atual)
> concluído em 2026-05-15

- [x] View do painel com a semana atual
- [x] Layout: coluna lateral + 5 colunas de dias
- [x] Cada dia dividido em manhã e tarde
- [x] Card de tarefa com título + status visual
- [x] Checkbox feito/não feito por tarefa
- [x] Modal ao clicar na tarefa (responsável, comentário, datas)
- [x] Barra de progresso geral no topo
- [x] Dia atual destacado com acento dourado
- [x] Divisão de tarefas André e Rafa na linha inferior
- [x] Visual: identidade do INT
- [x] Botão adicionar tarefa em cada dia/período
- [x] Botão excluir tarefa nos cards
- [x] Commit: `feat(sca): painel principal com layout, modal e progresso`, 
- [x] Commit: `docs: atualiza BACKLOG — Módulo 3 quase completo, Módulo 4 iniciando`

---

## ✅ MÓDULO 4 — Blocos especiais
> Concluído em 2026-05-19

- [x] Bloco "Importantes / Não Esquecer" com adicionar/excluir itens
- [x] Bloco "Diário" com adicionar/excluir itens
- [x] Bloco "Outros / Observação" com adicionar/excluir itens
- [x] Checkbox por item nos blocos
- [x] Itens editáveis por semana (modal com conteúdo, responsável, prazo, fixo)
- [x] Botão para adicionar novo item em cada bloco
- [x] Comentários por item do bloco
- [x] Conteúdo isolado por semana
- [x] Botão de adicionar/excluir tarefas na divisão do André *(ficou pendente)*
- [x] Botão de adicionar/excluir tarefas na divisão da Rafa *(ficou pendente)*
- [x] Commit: `feat(sca): blocos especiais com modal, comentarios e fuso horario`
- [x] Commit: `feat(sca): divisao de tarefas semanal por funcionario`

---

## ✅ MÓDULO 5 — Permissões e segurança
> Concluído em 2026-05-19

- [x] `@login_required` em todas as views
- [x] Perfil `operador` — Rafa e André — edita semana atual
- [x] Perfil `gestor` — Jefferson — somente leitura
- [x] Operador não edita semanas passadas
- [x] Commit: `feat(sca): permissões e segurança`

---

## ✅ MÓDULO 6 — Geração automática de semanas
> Concluído em 2026-05-20

- [x] Serviço que detecta início de nova semana
- [x] Gera execuções para todas as tarefas ativas
- [x] Tarefas não concluídas viram `atrasada`
- [x] Lógica idempotente — sem duplicação
- [x] Commit: `feat(sca): geracao automatica de semanas e marcacao de atrasadas`
---

## ✅ MÓDULO 7 — Histórico de semanas
> Concluído em 2026-05-20

- [x] Tela de histórico com seletor de semana
- [x] Visualização somente leitura
- [x] Navegação entre semanas com setas
- [x] Data por extenso no header
- [x] Indicador de percentual de conclusão
- [ ] Filtro por funcionário *(movido para Módulo 10)*
- [x] Commit: `feat(sca): historico de semanas com navegacao e data por extenso`

---

## ✅ MÓDULO 8 — Exportação Excel
> Concluído em 2026-05-20

- [x] Exportar semana selecionada para `.xlsx`
- [x] Aba Rafa + Aba André no mesmo arquivo
- [x] Colunas: tarefa, dia, período, status, comentário
- [x] Disponível na semana atual e no histórico
- [x] Visual profissional — fundo branco, cores por status
- [ ] Exportação via Celery em background *(movido para Módulo 10)*
- [x] Commit: `feat(sca): exportacao excel com visual profissional`

---

## ⏳ MÓDULO 9 — Gestão de tarefas (CRUD)
> Movido para pós-feedback — avaliar após uso em produção

- [ ] Avaliar necessidade real após uso em produção
- [ ] Tela para criar/editar tarefas recorrentes sem usar o admin Django
- [ ] Definir perfil de acesso do gestor no sistema
- [ ] Commit: `feat(sca): gestão de tarefas`

---

## ⏳ MÓDULO 10 — Melhorias pós-feedback

- [ ] Modo dark/light com alternância por botão
- [ ] Itens fixos que carregam entre semanas
- [ ] Filtros no painel por responsável
- [ ] Indicadores individuais por funcionário
- [ ] Ajustes do uso real
- [ ] Filtro por funcionário no histórico
- [ ] Exportação Excel via Celery (tarefa em background)
- [ ] Gestão de tarefas recorrentes (CRUD) para o gestor
- [ ] Definição do papel do gestor no sistema
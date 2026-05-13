# Backlog — SCA (Sistema de Controle Administrativo)
**Grupo Golden Sat — Sistema INT**

> Última atualização: 2026-05-13

---

## 🗺️ Ordem de execução
M1 → M2 → M3 → M7 → M4 → M5 → M6 → M8 → M9

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

## 🔄 MÓDULO 2 — Models e banco de dados
> Em andamento

- [ ] Escrever todos os models em `models.py`
  - [ ] `FuncionarioAdministrativo`
  - [ ] `CategoriaTarefaAdministrativa`
  - [ ] `TarefaModeloAdministrativa`
  - [ ] `ExecucaoTarefaAdministrativa`
  - [ ] `BlocoSemanal`
  - [ ] `ItemBlocoSemanal`
- [ ] Registrar todos no `admin.py`
- [ ] Rodar `makemigrations`
- [ ] Revisar o arquivo de migration gerado
- [ ] Rodar `migrate`
- [ ] Confirmar que o servidor sobe sem erros
- [ ] Commit: `feat(sca): models e migrations`

---

## ⏳ MÓDULO 3 — Painel principal (semana atual)

- [ ] View do painel com a semana atual
- [ ] Layout: coluna lateral + 5 colunas de dias
- [ ] Cada dia dividido em manhã e tarde
- [ ] Card de tarefa com título + status visual
- [ ] Checkbox feito/não feito por tarefa
- [ ] Modal ao clicar na tarefa (responsável, comentário, datas)
- [ ] Barra de progresso geral no topo
- [ ] Dia atual destacado com acento dourado
- [ ] Divisão de tarefas André e Rafa na linha inferior
- [ ] Modo dark/light com alternância por botão
- [ ] Visual: identidade do INT
- [ ] Commit: `feat(sca): painel principal da semana`

---

## ⏳ MÓDULO 4 — Blocos especiais

- [ ] Bloco "Importantes / Não Esquecer"
- [ ] Bloco "Diário"
- [ ] Bloco "Outros / Observação"
- [ ] Itens editáveis por semana
- [ ] Checkbox por item
- [ ] Botão para adicionar novo item
- [ ] Conteúdo isolado por semana
- [ ] Commit: `feat(sca): blocos especiais`

---

## ⏳ MÓDULO 5 — Permissões e segurança

- [ ] `@login_required` em todas as views
- [ ] Perfil `operador` — Rafa e André — edita semana atual
- [ ] Perfil `gestor` — Jefferson — somente leitura
- [ ] Operador não edita semanas passadas
- [ ] Commit: `feat(sca): permissões e segurança`

---

## ⏳ MÓDULO 6 — Geração automática de semanas

- [ ] Serviço que detecta início de nova semana
- [ ] Gera execuções para todas as tarefas ativas
- [ ] Tarefas não concluídas viram `atrasada`
- [ ] Lógica idempotente — sem duplicação
- [ ] Commit: `feat(sca): geração automática de semanas`

---

## ⏳ MÓDULO 7 — Histórico de semanas

- [ ] Tela de histórico com seletor de semana
- [ ] Visualização somente leitura
- [ ] Filtro por funcionário
- [ ] Indicador de percentual de conclusão
- [ ] Commit: `feat(sca): histórico de semanas`

---

## ⏳ MÓDULO 8 — Exportação Excel

- [ ] Exportar semana selecionada para `.xlsx`
- [ ] Aba Rafa + Aba André no mesmo arquivo
- [ ] Colunas: tarefa, dia, período, status, comentário
- [ ] Disponível na semana atual e no histórico
- [ ] Commit: `feat(sca): exportação excel`

---

## ⏳ MÓDULO 9 — Gestão de tarefas (CRUD)

- [ ] Tela para criar nova tarefa recorrente
- [ ] Editar tarefa existente
- [ ] Desativar tarefa
- [ ] Acessível apenas para gestor ou admin
- [ ] Commit: `feat(sca): gestão de tarefas`

---

## ⏳ MÓDULO 10 — Melhorias pós-feedback

- [ ] Itens fixos que carregam entre semanas
- [ ] Filtros no painel por responsável
- [ ] Indicadores individuais por funcionário
- [ ] Ajustes do uso real
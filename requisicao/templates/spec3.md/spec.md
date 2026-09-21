# Spec — Corrigir arraste travado do card de requisição (Kanban de Gestão)

## 1. Objetivo
Tornar o arraste (drag-and-drop) dos cards de requisição no Kanban de Gestão
fluido e imediato: iniciar o arraste a partir de **qualquer área do card** e
**sem precisar segurar** por tempo perceptível no desktop, mantendo os controles
internos (botões, links, inputs) clicáveis normalmente.

## 2. Contexto (bug atual)
No Kanban de Gestão, arrastar um card está difícil: é preciso segurar por muito
tempo e o arraste só funciona quando se clica na **parte superior** do card.
Impacto direto no fluxo do setor de Configuração, que move cards de
"Em Progresso" → "Auditoria".

## 3. Arquivo alvo (ÚNICO)
- `requisicao/templates/kanban_gestao.html`

Toda a mudança fica na inicialização do SortableJS (`new Sortable(coluna, {...})`)
e, se necessário, num pequeno ajuste de CSS/marcação **dentro desse mesmo arquivo**.

## 4. Causa raiz (confirmada no código)
Na config atual do Sortable:

```js
new Sortable(coluna, {
    ...
    handle: '.kanban-card',
    forceFallback: true,
    delay: 200,                 // <- exige segurar antes de arrastar
    delayOnTouchOnly: false,    // <- aplica o delay também no mouse (desktop)
    ...
});
```

1. **Demora ao arrastar:** `delay: 200` com `delayOnTouchOnly: false` força um
   press-and-hold de 200ms em todos os dispositivos, inclusive no mouse.
2. **Só a parte de cima arrasta:** `handle: '.kanban-card'` sem `filter`. O corpo
   do card contém elementos interativos (botões / form / inputs / links) que
   capturam o `mousedown` e impedem o início do arraste. Sobra apenas a região
   superior "limpa" para iniciar o drag.

## 5. Mudanças esperadas

### 5.1 Remover a demora no desktop
Ajustar a config do Sortable:
- `delay: 0` (arraste imediato no mouse). Se quiser manter proteção contra
  arraste acidental **no toque**, use `delay: 80` **em conjunto** com
  `delayOnTouchOnly: true`.
- `delayOnTouchOnly: true` (nenhum delay no mouse; delay, se houver, só no toque).
- Opcional: `touchStartThreshold: 5` para tolerância de movimento no toque.

### 5.2 Permitir iniciar o arraste em qualquer ponto do card
Manter `handle: '.kanban-card'` e adicionar um `filter` que exclua **apenas** os
controles interativos, com `preventOnFilter: false` para que o clique nesses
controles continue funcionando (não vira drag, mas também não é bloqueado):

```js
filter: 'button, a, input, select, textarea, label, .no-drag',
preventOnFilter: false,
```

> Antes de aplicar, **inspecione o markup do card** (`.kanban-card`) neste
> template e confirme quais elementos interativos existem. Ajuste o seletor do
> `filter` para cobrir exatamente esses elementos. Se algum bloco não-interativo
> ainda estiver "engolindo" o arraste, marque-o para ser ignorado com a classe
> `.no-drag` (que já está no filter) — **sem** adicionar `.no-drag` nos elementos
> que devem iniciar o arraste.

### 5.3 (Alternativa, se 5.2 não bastar) Handle explícito
Se a UX ficar ambígua, criar uma alça de arraste dedicada (ex.: o cabeçalho do
card `.card-header-row` ou um ícone "grip") e trocar `handle: '.kanban-card'` por
`handle: '.card-drag-handle'`. Preferir a abordagem 5.2 primeiro (menos marcação).

## 6. Critérios de aceite (Given / When / Then)

- **CA1 — Sem demora (mouse)**
  - Given estou no Kanban de Gestão em desktop
  - When pressiono um card e movo o mouse
  - Then o arraste inicia imediatamente, sem período perceptível de "segurar".

- **CA2 — Arraste de qualquer área**
  - Given um card com conteúdo no corpo (não só no topo)
  - When inicio o arraste a partir do meio/base do card, fora de um controle
  - Then o card entra em arraste normalmente.

- **CA3 — Controles continuam clicáveis**
  - Given um card com botões/links/inputs
  - When clico diretamente em um desses controles
  - Then a ação do controle é executada e **nenhum** arraste é iniciado.

- **CA4 — Regra de permissão preservada (Configuração)**
  - Given usuário do setor de Configuração (`isConfig` e não `isGestao`)
  - When arrasto um card de "Em Progresso" para "Auditoria"
  - Then o movimento é aceito; qualquer outro movimento continua bloqueado com a
    mensagem existente, exatamente como hoje (nenhuma regra de `onEnd` alterada).

- **CA5 — Fluxos existentes intactos**
  - Given os fluxos atuais de `onEnd` (permissões, "a_fazer → em_progresso" com
    atribuição, auto-scroll)
  - When faço os movimentos correspondentes
  - Then o comportamento é idêntico ao anterior (só a iniciação do drag mudou).

## 7. O que NÃO alterar
- A lógica de `onEnd` (permissões, atribuição, `showNotification`, revert do DOM).
- As regras de status/permissão (`isGestao` / `isConfig`, em_progresso → auditoria).
- Os outros Kanbans: `kanban_TI`, `kanban_marketing`, `kanban_inteligencia`
  (têm implementação de drag própria e independente — **não tocar**).
- CSS global, views, urls, models ou qualquer arquivo fora de `kanban_gestao.html`.

## 8. Verificação (TDD pragmático)
Drag real do SortableJS não é testável de forma limpa em unit test, então:
- Priorizar o **checklist manual** (seção 9) como critério de pronto.
- Se já houver suíte de testes de template/rota para este Kanban, garantir que
  continua verde (nenhuma regressão). **Não** criar teste frágil que dependa de
  simular o gesto de arraste do navegador.

## 9. Checklist de implementação
```
[ ] Inspecionar o markup de .kanban-card e listar os controles interativos internos
[ ] Ajustar delay: 0 (ou 80 + delayOnTouchOnly:true) na config do Sortable
[ ] Definir delayOnTouchOnly: true
[ ] Adicionar filter dos controles interativos + preventOnFilter: false
[ ] Corrigir o comentário enganoso ("Delay de 1 segundo" — hoje é 200ms)
[ ] Testar (desktop): arraste inicia imediato, sem segurar          -> CA1
[ ] Testar: arraste inicia do meio/base do card                     -> CA2
[ ] Testar: clique em botão/link/input executa ação, sem arrastar   -> CA3
[ ] Testar (Configuração): em_progresso → auditoria funciona        -> CA4
[ ] Testar: movimento inválido segue bloqueado com a mensagem atual -> CA4
[ ] Testar: a_fazer → em_progresso ainda pede atribuição            -> CA5
[ ] Confirmar que nenhum outro Kanban/arquivo foi alterado
```
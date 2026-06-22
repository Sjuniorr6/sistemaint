# Kanban TI – SPEC: Notificação de Novo Ticket em Tempo Real

> **Especificação técnica para implementação por IA (Claude)**

| Campo   | Valor                          |
|---------|--------------------------------|
| Versão  | 1.0                            |
| Status  | Pronto para Implementação      |
| Autor   | Grupo GoldenSat                |
| Escopo  | `kanban_TI` apenas             |

---

## ⚠️ Restrição crítica

Alterar **somente** o `kanban_TI`.
Não alterar: outros Kanbans, sistema de tickets, CSS global, outros apps.

---

## 1. Comportamento Esperado

Quando qualquer usuário criar um ticket destinado ao T.I:

- Uma notificação **aparece no canto lateral direito** da tela do `kanban_TI`
- Exibe o título do ticket, quem abriu e há quanto tempo
- **Some automaticamente após 6 segundos**
- O usuário pode fechar manualmente antes disso clicando no X
- Se chegarem múltiplos tickets em sequência, as notificações se empilham

```
                              ┌─────────────────────────────┐
                              │  🎫  Novo ticket             │
                              │  Problema no sistema de NF  │
                              │  Aberto por João · agora    │
                              │                          [X] │
                              └─────────────────────────────┘
                              ┌─────────────────────────────┐
                              │  🎫  Novo ticket             │
                              │  Acesso bloqueado ERP       │
                              │  Aberto por Maria · agora   │
                              │                          [X] │
                              └─────────────────────────────┘
```

---

## 2. Implementação — HTMX Polling + Toast Bootstrap

A estratégia usa **polling leve** (a cada 5s) para verificar se há tickets novos desde a última verificação, sem precisar de WebSocket ou SSE.

### 2.1 Controle de "último ticket visto"

```javascript
// Armazenar o ID do último ticket que o usuário já viu
// Inicializado com o timestamp atual para não mostrar tickets antigos
let _ultimoTicketVisto = Date.now();
```

### 2.2 Endpoint de verificação

```python
# kanban_TI/views.py

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

@login_required
def tickets_novos(request):
    """
    Retorna tickets criados após o timestamp informado.
    Chamado pelo JS a cada 5s — endpoint leve.
    """
    desde_ts = request.GET.get('desde')

    try:
        desde = timezone.datetime.fromtimestamp(
            int(desde_ts) / 1000,
            tz=timezone.get_current_timezone()
        )
    except (TypeError, ValueError):
        desde = timezone.now() - timedelta(seconds=10)

    tickets = Ticket.objects.filter(
        destinado='TI',
        created_at__gt=desde,
        is_active=True
    ).select_related('criado_por').order_by('created_at')

    return JsonResponse({
        'tickets': [
            {
                'id':         str(t.pk),
                'titulo':     t.titulo,
                'criado_por': t.criado_por.get_full_name() or t.criado_por.username
                              if t.criado_por else 'Desconhecido',
                'created_at': t.created_at.isoformat(),
            }
            for t in tickets
        ]
    })
```

### 2.3 Registrar URL

```python
# kanban_TI/urls.py
# Adicionar apenas esta rota

path('tickets/novos/', views.tickets_novos, name='kanban_ti_tickets_novos'),
```

---

## 3. Container de Notificações no Template

Adicionar no template do `kanban_TI`, **uma vez**, antes de fechar `</body>`:

```html
<!-- Container de toasts — fixo no canto inferior direito -->
<div id="toast-container"
     class="toast-container position-fixed bottom-0 end-0 p-3"
     style="z-index: 9999;">
    <!-- Toasts injetados dinamicamente pelo JS -->
</div>
```

---

## 4. JavaScript de Polling e Exibição

```javascript
<script>
(function () {

    // Timestamp de início da sessão — não mostrar tickets anteriores
    let _desde = Date.now();

    // Intervalo de verificação em ms
    const INTERVALO = 5000;

    // Duração do toast em ms (some automaticamente)
    const DURACAO_TOAST = 6000;

    // ── Polling ───────────────────────────────────────────────────────────
    function verificarTicketsNovos() {
        fetch(`{% url 'kanban_ti_tickets_novos' %}?desde=${_desde}`)
            .then(r => r.json())
            .then(data => {
                if (data.tickets && data.tickets.length > 0) {
                    data.tickets.forEach(ticket => exibirToast(ticket));
                    // Atualizar timestamp para não mostrar os mesmos novamente
                    _desde = Date.now();
                }
            })
            .catch(() => {});  // silencioso em caso de falha de rede
    }

    // ── Criar e exibir o toast ────────────────────────────────────────────
    function exibirToast(ticket) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toastEl = document.createElement('div');
        toastEl.className = 'toast align-items-center border-0 shadow-lg';
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.style.cssText = `
            background: #1a2332;
            color: #fff;
            min-width: 300px;
            max-width: 340px;
            border-left: 4px solid #F5C400 !important;
        `;

        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body py-3 px-3" style="flex:1;">
                    <div class="d-flex align-items-center gap-2 mb-1">
                        <i class="bi bi-ticket-perforated-fill"
                           style="color:#F5C400; font-size:1rem;"></i>
                        <span class="fw-semibold" style="font-size:0.82rem; color:#F5C400;">
                            Novo ticket
                        </span>
                    </div>
                    <div class="fw-bold mb-1" style="font-size:0.88rem; color:#fff;">
                        ${_escaparHtml(ticket.titulo)}
                    </div>
                    <div style="font-size:0.75rem; color:#9ca3af;">
                        Aberto por <strong style="color:#d1d5db;">
                            ${_escaparHtml(ticket.criado_por)}
                        </strong> · agora
                    </div>
                </div>
                <button type="button"
                        class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast"
                        style="font-size:0.7rem; opacity:0.6;">
                </button>
            </div>
            <!-- Barra de progresso do tempo restante -->
            <div class="toast-progress" style="
                height: 3px;
                background: #F5C400;
                border-radius: 0 0 4px 0;
                animation: toast-shrink ${DURACAO_TOAST}ms linear forwards;
            "></div>
        `;

        container.appendChild(toastEl);

        // Inicializar e mostrar via Bootstrap Toast
        const bsToast = new bootstrap.Toast(toastEl, {
            autohide: true,
            delay:    DURACAO_TOAST,
        });
        bsToast.show();

        // Remover do DOM após esconder para não acumular
        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    }

    // ── Escape HTML para segurança ────────────────────────────────────────
    function _escaparHtml(texto) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(texto || ''));
        return div.innerHTML;
    }

    // ── Iniciar polling ───────────────────────────────────────────────────
    setInterval(verificarTicketsNovos, INTERVALO);

    // Verificar imediatamente ao carregar (após 1s para não sobrecarregar o init)
    setTimeout(verificarTicketsNovos, 1000);

}());
</script>
```

---

## 5. CSS da Animação de Progresso

Adicionar no CSS do `kanban_TI`:

```css
/* Barra de progresso do toast — mostra o tempo restante */
@keyframes toast-shrink {
    from { width: 100%; }
    to   { width: 0%;   }
}

/* Animação de entrada do toast */
.toast {
    animation: toast-slide-in 0.3s ease;
}

@keyframes toast-slide-in {
    from {
        transform: translateX(120%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}
```

---

## 6. Pausar Polling Quando Aba Está Inativa

Evitar requisições desnecessárias quando o usuário não está olhando para a tela:

```javascript
// Adicionar junto ao bloco de polling

document.addEventListener('visibilitychange', function () {
    if (!document.hidden) {
        // Aba voltou ao foco — atualizar timestamp para não mostrar
        // tickets que chegaram enquanto estava em segundo plano
        _desde = Date.now();
    }
});
```

---

## 7. O que NÃO alterar

- Sistema de criação de tickets
- Outros Kanbans
- CSS global
- Qualquer outro template fora do `kanban_TI`

---

## 8. Checklist de implementação

```
[ ] Criar view tickets_novos no kanban_TI/views.py
[ ] Registrar URL kanban-ti/tickets/novos/ no urls.py
[ ] Adicionar <div id="toast-container"> no template kanban_TI antes de </body>
[ ] Adicionar o bloco <script> com polling e exibirToast()
[ ] Adicionar CSS @keyframes toast-shrink e toast-slide-in no CSS do kanban_TI
[ ] Adicionar listener de visibilitychange para pausar quando aba inativa
[ ] Testar: abrir kanban_TI em dois navegadores
[ ]   → Criar ticket no navegador A
[ ]   → Em até 5s toast aparece no navegador B no canto inferior direito
[ ] Testar: toast some automaticamente após 6s
[ ] Testar: clicar no X fecha o toast imediatamente
[ ] Testar: criar 2 tickets seguidos → 2 toasts empilhados
[ ] Testar: barra de progresso âmbar diminui até zero e toast some
[ ] Confirmar que nenhum outro template foi alterado
```
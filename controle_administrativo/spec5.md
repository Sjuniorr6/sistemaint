# SPEC — Controle Administrativo: Item Fixo Quinzenal (Recorrência a Cada 2 Semanas)

| Campo | Valor |
|-------|-------|
| **Projeto** | GS INT |
| **Versão** | 1.0.0 |
| **Status** | Draft — bloqueada até resolução das QA-XX |
| **Autor** | _(preencher)_ |
| **Spec relacionada** | `SPEC-progresso-atividades-quinzenais.md` (compartilha a definição de quinzena — RN-02 daquela spec / QA-01) |
| **Stack** | Python · Django · PostgreSQL · HTMX · Alpine.js · Bootstrap 5 · Celery + Redis · AWS EC2 |
| **Padrões** | Clean Architecture · BaseModel (UUID) · SDD · TDD |
| **Tema** | Navy `#1a2332` · Amber `#F5C400` (GoldenSat) |

### Escopo

No **bloco quinzenal** da aba `controle_administrativo`, o modal de **criação/edição** de item exibe hoje a caixa de seleção:

> ☐ **"Item fixo — carregar para a semana seguinte"**

que, quando marcada, faz o item reaparecer **toda semana** — comportamento herdado do bloco semanal e **incorreto** para o contexto quinzenal. Esta spec:

1. **Renomeia** o rótulo para **"Fixar o item quinzenalmente"** (criação e edição).
2. **Corrige a lógica de recorrência**: item fixo do bloco quinzenal reaparece **a cada quinzena** (2 semanas), nunca semanalmente.
3. Define o **tratamento dos itens já fixados** pela lógica antiga (transição de dados).

### Guarda de escopo — instruções para o agente implementador

- **NÃO** alterar o comportamento do checkbox de item fixo no **bloco semanal** — lá "carregar para a semana seguinte" continua correto e intocado.
- **NÃO** alterar o cálculo da barra de progresso (coberto pela spec relacionada) — apenas garantir que ambos usem a **mesma** função `quinzena_vigente()`.
- **NÃO** apagar itens ou histórico de recorrências antigas; a transição (RN-07) apenas ajusta o comportamento **futuro**.
- Migration permitida **apenas** se a QA-02 decidir pela renomeação do campo no banco; caso contrário, zero migrations.
- Os nomes de models, campos, tasks e templates abaixo são **hipóteses plausíveis**: **reconciliar com o código real** antes de qualquer teste ou linha de produção (QA-01). Onde divergir, manter o nome real e anotar na PR.
- Se houver URL nova, verificar allowlist do middleware de contenção por perfil (padrão GS) antes do deploy.

---

## 1. Contexto / Problema

O bloco quinzenal reutilizou o componente de modal do bloco semanal. Com isso, o checkbox de item fixo veio com **rótulo** e **lógica** semanais:

- **Rótulo errado**: "carregar para a semana seguinte" não descreve o comportamento desejado no contexto quinzenal e confunde o usuário.
- **Lógica errada**: o item fixo é recarregado **a cada semana**, então um item quinzenal fixo aparece **2× mais** do que deveria — duplicando trabalho percebido, poluindo o modal e (após a spec relacionada) **inflando o denominador** da barra de progresso.

### 1.1 Hipóteses de diagnóstico (confirmar no código real)

| # | Hipótese | Como confirmar |
|---|----------|----------------|
| **H1** | O form do modal quinzenal importa o mesmo `Form`/template do bloco semanal, herdando o `label` do campo `fixo`. | Localizar o form/template do modal e verificar reuso. |
| **H2** | Existe rotina de "carry-over" (Celery Beat semanal ou management command) que clona/reativa itens com `fixo=True` **toda semana**, sem distinguir a periodicidade do bloco. | Procurar task/command com filtro `fixo=True` e agenda semanal no `CELERY_BEAT_SCHEDULE`. |
| **H3** | Alternativa à H2: não há clonagem — a "recarga" é **virtual**, calculada na leitura (itens fixos sempre aplicáveis ao período corrente). | Verificar se o queryset do bloco deriva aplicabilidade por período. |

> H2 vs. H3 muda a implementação (§6). A spec cobre os dois caminhos; a QA-01 fixa qual vale.

---

## 2. Regras de Negócio

**RN-01 — Rótulo do checkbox.**
Nos modais de **criação** e **edição** do bloco quinzenal, o checkbox passa a exibir:
**"Fixar o item quinzenalmente"**, com help text: _"O item voltará a aparecer automaticamente a cada quinzena."_ Nenhuma menção a "semana" permanece no bloco quinzenal.

**RN-02 — Recorrência quinzenal.**
Item com `fixo=True` no bloco quinzenal reaparece **uma vez por quinzena**, na **virada de quinzena** — mesma definição de quinzena da spec relacionada (calendário fixo: A = dias 1–15, B = dia 16 ao fim do mês; viradas nos dias **1** e **16**). _Se a QA-01 daquela spec resolver por outro modelo (ex.: janela móvel de 14 dias), esta RN herda a decisão — as duas specs **nunca** podem divergir na definição de quinzena (ver QA-03)._

**RN-03 — Idempotência da recarga.**
A recarga por quinzena é idempotente: rodar a rotina duas vezes na mesma quinzena **não** duplica o item. Chave natural: `(item_origem, periodo_referencia)`.

**RN-04 — Desmarcar interrompe o futuro, preserva o passado.**
Desmarcar o checkbox impede recargas nas **próximas** quinzenas; instâncias/recorrências já geradas permanecem intactas (histórico e progresso não são reescritos).

**RN-05 — Marcar no meio da quinzena.**
Item fixado no meio de uma quinzena já **vale para a quinzena corrente** (ele já está visível — foi criado/editado nela) e a primeira **recarga automática** ocorre na virada seguinte.

**RN-06 — Bloco semanal intocado.**
O checkbox e a recorrência do bloco **semanal** permanecem exatamente como estão ("carregar para a semana seguinte", recarga semanal).

**RN-07 — Transição dos itens já fixados (lógica antiga).**
Itens do bloco quinzenal com `fixo=True` criados sob a lógica semanal **não são alterados nem duplicados retroativamente**: a partir do deploy, simplesmente passam a recarregar por quinzena. Cópias semanais já geradas em excesso **permanecem** (não apagar automaticamente); a QA-04 decide se haverá limpeza manual assistida.

**RN-08 — Fonte única da definição de quinzena.**
`quinzena_vigente()` (service da spec relacionada) é o **único** lugar que define a quinzena. A rotina de recarga, o form e a barra de progresso importam dela — nenhuma reimplementação local.

---

## 3. Fluxo Completo

```
┌───────────────────────────────────────────────────────────────┐
│  Modal do bloco quinzenal (criar / editar item)               │
│                                                               │
│  ☐ Fixar o item quinzenalmente        ◄── RN-01 (novo rótulo) │
│     "O item voltará a aparecer                                │
│      automaticamente a cada quinzena."                        │
└──────────────┬────────────────────────────────────────────────┘
               │ POST (fixo=True)
               ▼
┌────────────────────────────────────┐
│ Item salvo · visível na quinzena   │
│ corrente (RN-05)                   │
└──────────────┬─────────────────────┘
               │
               │  virada de quinzena (dia 1 · dia 16)
               ▼
┌───────────────────────────────────────────────────────┐
│ Recarga quinzenal (Celery Beat OU aplicabilidade      │
│ virtual — conforme H2/H3, QA-01)                      │
│  • filtra bloco QUINZENAL com fixo=True (RN-02)       │
│  • idempotente por (item, periodo_referencia) (RN-03) │
│  • bloco SEMANAL: rotina própria, intocada (RN-06)    │
└──────────────┬────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────┐        ┌──────────────────┐
│ Item reaparece no bloco quinzenal  │───────►│ Barra de         │
│ como pendente da nova quinzena     │        │ progresso conta  │
│                                    │        │ 1×/quinzena      │
└────────────────────────────────────┘        │ (spec relaciona.)│
                                              └──────────────────┘
   fixo=False (desmarcado na edição)
   └─► sem recarga nas próximas quinzenas; histórico preservado (RN-04)
```

---

## 4. Impacto por Camada (Clean Architecture)

| Camada | Componente | Impacto |
|--------|-----------|---------|
| **Domínio** | Campo `fixo` do item | Sem mudança de tipo; **semântica** por bloco (semanal recarrega/semana, quinzenal/quinzena) |
| **Domínio** | `quinzena_vigente()` | Reuso — nenhuma reimplementação (RN-08) |
| **Aplicação (services)** | `recarregar_itens_fixos_quinzenais` | **Novo** (caminho H2) ou ajuste do queryset de aplicabilidade (caminho H3) |
| **Aplicação (tasks)** | Task de carry-over existente | **Alterado**: deixa de recarregar itens do bloco quinzenal (RN-06 preserva a semanal) |
| **Infra (Celery Beat)** | Agenda | **Nova entrada**: dias 1 e 16, 00:05 (caminho H2) |
| **Interface (forms)** | `ItemQuinzenalForm` | **Alterado**: label + help_text (RN-01) |
| **Templates** | Modal do bloco quinzenal | **Alterado**: rótulo/help text; sem mudança estrutural |
| **Banco** | — | Zero migrations (salvo decisão QA-02 de renomear campo) |

---

## 5. Form e Template (RN-01)

```python
# apps/controle_administrativo/forms.py  (trecho — HIPÓTESE de nomes, QA-01)
from django import forms

from apps.controle_administrativo.models import ItemAdministrativo


class ItemQuinzenalForm(forms.ModelForm):
    """
    Form do modal do bloco quinzenal. Se hoje o bloco reutiliza o form do
    semanal (H1), ESTA CLASSE passa a existir separada — o form semanal
    permanece intocado (RN-06).
    """

    class Meta:
        model = ItemAdministrativo
        fields = ("titulo", "descricao", "fixo")
        labels = {
            "fixo": "Fixar o item quinzenalmente",          # RN-01
        }
        help_texts = {
            "fixo": "O item voltará a aparecer automaticamente a cada quinzena.",
        }
        widgets = {
            "fixo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
```

```html
{# controle_administrativo/partials/modal_item_quinzenal.html — trecho do campo #}
<div class="form-check mt-3">
  {{ form.fixo }}
  <label class="form-check-label fw-semibold" for="{{ form.fixo.id_for_label }}"
         style="font-family: 'Inter', sans-serif; color: #1a2332;">
    {{ form.fixo.label }}
  </label>
  <div class="form-text small">{{ form.fixo.help_text }}</div>
</div>
```

> O mesmo partial serve criação e edição — o rótulo novo aparece nos dois modos
> automaticamente. Verificar no template real se o label está **hardcoded** no HTML
> (em vez de vir do form): se estiver, substituir o texto e migrar para `{{ form.fixo.label }}`
> para a fonte ficar única.

---

## 6. Lógica de Recorrência

### 6.1 Caminho H2 — recarga materializada (Celery Beat)

```python
# apps/controle_administrativo/services/recarga_quinzenal.py
"""
Recarga de itens fixos do bloco quinzenal (RN-02, RN-03, RN-05).
Roda na virada de quinzena; idempotente por (origem, periodo_referencia).
"""
from datetime import date

from apps.controle_administrativo.models import ItemAdministrativo, Bloco
from apps.controle_administrativo.services.progresso import quinzena_vigente


def recarregar_itens_fixos_quinzenais(hoje: date) -> int:
    """
    Materializa, para a quinzena vigente, uma instância pendente de cada
    item fixo do bloco quinzenal que ainda não a possui. Retorna o total criado.
    """
    ref = quinzena_vigente(hoje)                                # RN-08
    fixos = ItemAdministrativo.objects.filter(
        bloco=Bloco.QUINZENAL, fixo=True, ativo=True,           # RN-02 / RN-06
    )
    criados = 0
    for item in fixos:
        _, criado = item.recorrencias.get_or_create(            # RN-03
            periodo_referencia=ref,
            defaults={"pendente": True},
        )
        criados += int(criado)
    return criados
```

```python
# apps/controle_administrativo/tasks.py  (trecho)
from celery import shared_task
from django.utils import timezone

from apps.controle_administrativo.services.recarga_quinzenal import (
    recarregar_itens_fixos_quinzenais,
)


@shared_task(name="controle_administrativo.recarga_quinzenal")
def task_recarga_quinzenal() -> int:
    return recarregar_itens_fixos_quinzenais(timezone.localdate())
```

```python
# core/settings.py — CELERY_BEAT_SCHEDULE  (trecho; "core" = pasta do settings real)
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # ... entradas existentes (ex.: fatura mensal no dia 5) ...
    "recarga-itens-fixos-quinzenais": {
        "task": "controle_administrativo.recarga_quinzenal",
        "schedule": crontab(day_of_month="1,16", hour=0, minute=5),   # RN-02
    },
}
```

**Ajuste obrigatório na rotina semanal existente (H2):** o carry-over semanal deve
passar a filtrar `bloco=Bloco.SEMANAL` explicitamente, deixando de tocar itens do
bloco quinzenal. Diff mínimo — um filtro a mais; nada além disso muda (RN-06).

> Lembrete operacional (padrão GS): task nova exige apenas **restart do worker/beat**
> no EC2 — sem terminais novos; `--pool=solo` não existe em Linux.

### 6.2 Caminho H3 — aplicabilidade virtual (sem clonagem)

Se o código real **não** materializa cópias (H3), a correção é só no queryset do bloco:

```python
# Itens exibidos no bloco quinzenal para a quinzena vigente:
ref = quinzena_vigente(hoje)
itens = ItemAdministrativo.objects.filter(bloco=Bloco.QUINZENAL, ativo=True).filter(
    Q(fixo=True) | Q(recorrencias__periodo_referencia=ref)
).distinct()
# "pendente" deriva da ausência de conclusão em `ref` (mesma chave da barra).
```

Neste caminho **não há task nem Beat** — a virada de quinzena é implícita na mudança
de `ref`. Preferir H3 se o código permitir: menos partes móveis, zero jobs.

---

## 7. Testes (TDD)

| # | Cenário | Esperado |
|---|---------|----------|
| **T-01** | Renderizar modal de **criação** do bloco quinzenal | Label = "Fixar o item quinzenalmente"; help text presente; nenhuma ocorrência de "semana" (RN-01) |
| **T-02** | Renderizar modal de **edição** do bloco quinzenal | Idem T-01 (RN-01) |
| **T-03** | Renderizar modal do bloco **semanal** | Label continua "Item fixo — carregar para a semana seguinte" (RN-06) |
| **T-04** | Item fixo quinzenal; recarga no dia 16 | 1 instância nova para `...-B` (RN-02) |
| **T-05** | Rodar a recarga 2× na mesma quinzena | Nenhuma duplicata (RN-03) |
| **T-06** | Recarga em dia **sem** virada (ex.: dia 10) executada manualmente | `get_or_create` não cria nada além do período vigente (RN-03) |
| **T-07** | Item fixado no dia 10 (meio da quinzena A) | Visível na quinzena A; primeira recarga automática só em `...-B` (RN-05) |
| **T-08** | Desmarcar `fixo` no dia 14; virada no dia 16 | Sem instância nova em `...-B`; instâncias antigas intactas (RN-04) |
| **T-09** | Item fixo **semanal** na virada de quinzena | Rotina quinzenal **não** o toca (RN-06) |
| **T-10** | Item quinzenal fixado sob a lógica antiga (pré-deploy) | Sem recarga semanal pós-deploy; recarrega só na virada de quinzena (RN-07) |
| **T-11** | Duas quinzenas consecutivas (freeze 15 → 16 → 1º do mês seguinte) | Exatamente 1 instância por quinzena: `A`, `B`, `A` do mês novo (RN-02) |
| **T-12** | Fonte única | `recarga_quinzenal` importa `quinzena_vigente` do service de progresso — sem cópia local (RN-08, revisão de PR) |
| **T-13** | Guarda de escopo | Zero migrations (salvo QA-02); bloco semanal sem diffs além do filtro de bloco |

Implementação dos principais:

```python
# apps/controle_administrativo/tests/test_item_fixo_quinzenal.py
from datetime import date

from django.test import TestCase
from freezegun import freeze_time

from apps.controle_administrativo.models import Bloco, ItemAdministrativo
from apps.controle_administrativo.services.recarga_quinzenal import (
    recarregar_itens_fixos_quinzenais,
)


class RotuloCheckboxTest(TestCase):
    def test_t01_label_novo_no_modal_quinzenal(self):
        from apps.controle_administrativo.forms import ItemQuinzenalForm
        form = ItemQuinzenalForm()
        self.assertEqual(form.fields["fixo"].label, "Fixar o item quinzenalmente")
        self.assertNotIn("semana", form.fields["fixo"].label.lower())

    def test_t03_label_semanal_intocado(self):
        from apps.controle_administrativo.forms import ItemSemanalForm
        form = ItemSemanalForm()
        self.assertIn("semana seguinte", form.fields["fixo"].label)


class RecargaQuinzenalTest(TestCase):
    def setUp(self):
        self.fixo = ItemAdministrativo.objects.create(
            titulo="Inventário", bloco=Bloco.QUINZENAL, fixo=True
        )
        self.nao_fixo = ItemAdministrativo.objects.create(
            titulo="Auditoria pontual", bloco=Bloco.QUINZENAL, fixo=False
        )
        self.fixo_semanal = ItemAdministrativo.objects.create(
            titulo="Relatório", bloco=Bloco.SEMANAL, fixo=True
        )

    def test_t04_t05_recarga_idempotente_na_virada(self):
        criados_1 = recarregar_itens_fixos_quinzenais(date(2026, 7, 16))
        criados_2 = recarregar_itens_fixos_quinzenais(date(2026, 7, 16))
        self.assertEqual((criados_1, criados_2), (1, 0))                # RN-03
        self.assertEqual(
            self.fixo.recorrencias.filter(periodo_referencia="2026-07-B").count(), 1
        )

    def test_t08_desmarcado_nao_recarrega(self):
        self.fixo.fixo = False
        self.fixo.save()
        criados = recarregar_itens_fixos_quinzenais(date(2026, 7, 16))
        self.assertEqual(criados, 0)                                    # RN-04

    def test_t09_semanal_fora_da_rotina_quinzenal(self):
        recarregar_itens_fixos_quinzenais(date(2026, 7, 16))
        self.assertFalse(
            self.fixo_semanal.recorrencias.filter(
                periodo_referencia="2026-07-B"
            ).exists()
        )                                                               # RN-06

    def test_t11_uma_instancia_por_quinzena(self):
        for dia in (date(2026, 7, 1), date(2026, 7, 16), date(2026, 8, 1)):
            recarregar_itens_fixos_quinzenais(dia)
        refs = list(
            self.fixo.recorrencias.order_by("periodo_referencia")
            .values_list("periodo_referencia", flat=True)
        )
        self.assertEqual(refs, ["2026-07-A", "2026-07-B", "2026-08-A"]) # RN-02
```

---

## 8. Checklist de Verificação Visual

1. Abrir o modal de **criação** no bloco quinzenal → checkbox lê "Fixar o item quinzenalmente" com o help text abaixo, tipografia Inter, cor do label navy `#1a2332`.
2. Abrir o modal de **edição** de um item existente → mesmo rótulo; estado do checkbox reflete o valor salvo.
3. Abrir o modal do bloco **semanal** → rótulo antigo preservado, sem contaminação.
4. Fixar um item quinzenal, simular virada (dia 16 / dia 1): item reaparece **uma vez** como pendente; nas semanas intermediárias, **nada** novo aparece.
5. Desmarcar e simular virada: item não retorna; instâncias antigas continuam listadas no histórico.
6. Conferir que a barra de progresso (spec relacionada) conta o item fixo **1× por quinzena** — sem inflar com cópias semanais.
7. Layout do modal: espaçamentos múltiplos de 4px; checkbox alinhado ao padrão Bootstrap 5 (`form-check`); nenhum deslocamento visual causado pelo help text.

---

## 9. Questões em Aberto (bloqueiam implementação)

| # | Questão | Recomendação |
|---|---------|--------------|
| **QA-01** | **Reconciliação com o código real**: nomes de models/campos (`ItemAdministrativo`, `bloco`, `fixo`, `recorrencias`), e qual hipótese vale — H2 (carry-over materializado por task) ou H3 (aplicabilidade virtual)? | Reconciliar antes do primeiro teste; **preferir H3** se o código permitir (menos partes móveis, zero Beat novo). |
| **QA-02** | O campo booleano no banco chama algo como `carregar_proxima_semana`? Renomear via `RenameField` (migration) ou manter o nome e trocar só label/semântica? | Se o nome atual for semanal-específico, **renomear para `fixo`** em migration única e isolada — nome mentiroso no banco cobra juros; se já for genérico (`fixo`), zero migrations. |
| **QA-03** | **Coerência da quinzena**: a QA-01 da spec relacionada (calendário fixo 1–15/16-fim vs. janela de 14 dias) precisa ser resolvida **antes** desta spec — o usuário descreveu "a cada 15 dias ou seja 2 semanas", que mistura os dois modelos (15 dias ≠ 14 dias). | Resolver uma vez, valer para as duas specs. Calendário fixo continua sendo a recomendação (viradas previsíveis nos dias 1 e 16; cron trivial). |
| **QA-04** | **Limpeza das cópias em excesso** geradas pela lógica semanal antiga no bloco quinzenal: manter como estão (RN-07) ou oferecer limpeza assistida (command de deduplicação com dry-run)? | Manter + command opcional com `--dry-run` para o Admin GS rodar uma única vez; nunca automático. |
| **QA-05** | A recarga (H2) é **por usuário** ou **global**? Deve seguir a mesma resposta da QA-04 da spec relacionada (progresso por usuário vs. equipe). | Herdar a decisão da spec relacionada — as duas chaves precisam casar. |
| **QA-06** | Horário/fuso do Beat: `crontab(day_of_month="1,16")` roda no fuso do Celery (`CELERY_TIMEZONE`). Confirmar que está alinhado a `settings.TIME_ZONE` (America/Sao_Paulo). | Fixar `CELERY_TIMEZONE = TIME_ZONE` se ainda não estiver; virada errada de fuso geraria recarga no dia errado. |

---

## 10. Checklist de Implementação

- [ ] QA-01 a QA-06 resolvidas e registradas (atualizar versão se houver mudança de regra)
- [ ] Reconciliar nomes reais de models/campos/tasks/templates (QA-01)
- [ ] Decidir H2 vs. H3 e riscar o caminho não usado desta spec (manter registro da decisão)
- [ ] Escrever T-01..T-13 (vermelhos)
- [ ] Separar `ItemQuinzenalForm` do form semanal (se hoje for compartilhado — H1)
- [ ] Novo label + help text no form; remover texto hardcoded do template, se houver
- [ ] Implementar recarga quinzenal (service + task + Beat **ou** queryset virtual)
- [ ] Adicionar filtro `bloco=SEMANAL` na rotina semanal existente (RN-06)
- [ ] Migration de `RenameField` **somente** se QA-02 aprovar; caso contrário, zero migrations
- [ ] Restart do worker + beat no EC2 (se caminho H2)
- [ ] Testes verdes; checklist visual (§8) executado em desktop e mobile
- [ ] Validar em staging uma virada de quinzena simulada (freezegun/ajuste de relógio)
- [ ] PR com referência a esta spec + anotações de reconciliação
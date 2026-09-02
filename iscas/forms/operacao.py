"""Forms de solicitação, atribuição e busca por proximidade."""
from django import forms
from django.db.models import Q

from iscas.enums import StatusSolicitacao, TipoMovimentacao, UF_CHOICES
from iscas.models.cadastro import Agente, Cliente, ModeloEquipamento
from iscas.models.config import ConfiguracaoIscas
from iscas.models.operacao import Solicitacao
from iscas.selectors import agentes_que_atendem, unidades_uteis_por_modelo


class SolicitacaoForm(forms.ModelForm):
    """Abertura da solicitação (ISC-RF-22).

    Ao escolher o cliente, a tela SUGERE contato e endereço a partir do
    cadastro — quando ele tem endereço, o que deixou de ser obrigatório. Os
    valores são editáveis e ficam gravados NA SOLICITAÇÃO: entrega em obra ou
    filial não sobrescreve o endereço principal do cliente, e o histórico
    registra para onde a entrega foi de fato. O nome do cliente é a exceção —
    vem sempre da FK, para não haver duas versões da identidade.

    O endereço de entrega é onde a busca por proximidade mede a distância, por
    isso ele carrega a própria coordenada (`entrega_latitude`/`longitude`),
    resolvida pelo pin do mapa ou pela geocodificação do que foi digitado.
    """

    #: Preenchidos pelo mapa do formulário — mesma mecânica do cadastro.
    entrega_latitude_ajustada = forms.DecimalField(
        required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput()
    )
    entrega_longitude_ajustada = forms.DecimalField(
        required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput()
    )
    #: "1" quando a posição veio do arrasto/clique, não da prévia automática.
    entrega_pin_movido = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Solicitacao
        fields = [
            "cliente",
            "documento",
            "email",
            "contato_nome",
            "telefone",
            "comercial_responsavel",
            "entrega_logradouro",
            "entrega_numero",
            "entrega_complemento",
            "entrega_bairro",
            "entrega_cidade",
            "entrega_uf",
            "entrega_cep",
            "prazo_desejado",
            "observacao",
        ]
        widgets = {
            "cliente": forms.Select(attrs={"class": "form-select"}),
            "documento": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "contato_nome": forms.TextInput(attrs={"class": "form-control"}),
            "telefone": forms.TextInput(attrs={"class": "form-control"}),
            "comercial_responsavel": forms.TextInput(attrs={"class": "form-control"}),
            "entrega_logradouro": forms.TextInput(attrs={"class": "form-control"}),
            "entrega_numero": forms.TextInput(attrs={"class": "form-control"}),
            "entrega_complemento": forms.TextInput(attrs={"class": "form-control"}),
            "entrega_bairro": forms.TextInput(attrs={"class": "form-control"}),
            "entrega_cidade": forms.TextInput(attrs={"class": "form-control"}),
            "entrega_uf": forms.Select(
                choices=[("", "—"), *UF_CHOICES], attrs={"class": "form-select"}
            ),
            "entrega_cep": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "00000-000"}
            ),
            "prazo_desejado": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
            "observacao": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = Cliente.objects.order_by("nome_razao_social")
        # Endereço de entrega é obrigatório AQUI, e só aqui: sem ele o agente
        # não sabe onde entregar. É justamente por a solicitação exigir que o
        # cadastro do cliente pode deixar de exigir.
        for campo in ("entrega_logradouro", "entrega_cidade", "entrega_uf"):
            self.fields[campo].required = True

    def pin_de_entrega(self):
        """Coordenada posicionada à mão no mapa da entrega, ou None.

        Só conta como manual quando o operador de fato moveu o pin: a prévia
        automática também preenche os campos ocultos, e tratá-la como manual
        congelaria a coordenada.
        """
        if not self.is_valid():
            return None
        if self.cleaned_data.get("entrega_pin_movido") != "1":
            return None
        latitude = self.cleaned_data.get("entrega_latitude_ajustada")
        longitude = self.cleaned_data.get("entrega_longitude_ajustada")
        if latitude is None or longitude is None:
            return None
        return latitude, longitude


class AtribuicaoForm(forms.Form):
    """Escolha do agente que vai atender a solicitação (ISC-RF-23).

    Primeiro passo de dois. Aqui só se decide QUEM leva; o QUE ele leva é o
    `EscolhaUnidadesForm`, que precisa saber o agente para listar as unidades
    dele. Modelo e quantidade digitados saíram de cena: quantidade não diz qual
    isca saiu do estoque do agente, e sem isso o rastreio por unidade — a razão
    de existir do app (ISC-RN-03) — fica cego.
    """

    agente = forms.ModelChoiceField(
        queryset=Agente.objects.none(), label="Agente",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="Selecione um agente…",
    )

    def __init__(self, *args, solicitacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.solicitacao = solicitacao
        if solicitacao is None:
            # Sem solicitação não há o que atender: o queryset vazio herdado da
            # declaração já recusa qualquer escolha.
            return

        # Só agentes que têm alguma unidade disponível de algum modelo ainda em
        # falta. Agente desativado não entra (ISC-RN-18) — o selector filtra.
        self.fields["agente"].queryset = agentes_que_atendem(solicitacao)

    def clean_agente(self):
        """Reafirma a regra do queryset com mensagem de negócio.

        O `ModelChoiceField` já recusaria o agente fora do queryset, mas com o
        genérico "Faça uma escolha válida". Quem opera precisa saber POR QUE o
        agente não serve.
        """
        agente = self.cleaned_data["agente"]
        if self.solicitacao is not None and not unidades_uteis_por_modelo(
            agente=agente, solicitacao=self.solicitacao
        ):
            raise forms.ValidationError(
                f"{agente} não tem nenhuma unidade disponível dos modelos que "
                "faltam nesta solicitação."
            )
        return agente


class EscolhaUnidadesForm(forms.Form):
    """Quais unidades do agente vão para o cliente (ISC-RF-25).

    Um campo de múltipla escolha POR MODELO em falta, cada um listando as
    unidades daquele agente naquele modelo. Dois ganhos sobre a quantidade
    digitada:

    1. **Rastreio.** A reserva grava a unidade exata, então o histórico
       responde "onde está esta isca" (ISC-RN-03) em vez de "saíram três".
    2. **Um agente, vários modelos.** Se o pedido tem dois modelos e o agente
       tem os dois, os dois são escolhidos numa atribuição só — antes era
       preciso vincular o mesmo agente duas vezes (ISC-RN-10).

    Campos são montados dinamicamente porque os modelos em falta variam por
    solicitação; o nome é `unidades_<modelo_id>`.
    """

    PREFIXO = "unidades_"

    def __init__(self, *args, agente=None, solicitacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.agente = agente
        self.solicitacao = solicitacao
        self.limites = {}

        if agente is None or solicitacao is None:
            return

        for modelo, falta, disponiveis in unidades_uteis_por_modelo(
            agente=agente, solicitacao=solicitacao
        ):
            # O teto é o menor entre o que falta no pedido e o que o agente
            # tem: pedir mais que o pedido fura o contrato, mais que o estoque
            # fura o saldo.
            teto = min(falta, disponiveis.count())
            self.limites[modelo.pk] = {"modelo": modelo, "falta": falta, "teto": teto}
            self.fields[f"{self.PREFIXO}{modelo.pk}"] = forms.ModelMultipleChoiceField(
                queryset=disponiveis,
                required=False,
                label=modelo.nome,
                # Checkbox e não `<select multiple>`: escolher oito unidades
                # com Ctrl+clique é armadilha — um clique solto limpa tudo.
                widget=forms.CheckboxSelectMultiple,
            )

    def campos_por_modelo(self):
        """Pares (campo do form, dados do limite) para o template iterar."""
        for modelo_id, limite in self.limites.items():
            yield self[f"{self.PREFIXO}{modelo_id}"], limite

    def clean(self):
        """Recusa escolha vazia e excesso sobre o que ainda cabe no pedido.

        A regra final é do service (`_validar_contra_o_pedido`, ponto único);
        aqui ela vira erro de campo para o operador ver o limite antes de
        submeter, em vez de levar a exceção genérica depois.
        """
        dados = super().clean()
        total = 0

        for modelo_id, limite in self.limites.items():
            escolhidas = dados.get(f"{self.PREFIXO}{modelo_id}") or []
            quantidade = len(escolhidas)
            total += quantidade
            if quantidade > limite["falta"]:
                self.add_error(
                    f"{self.PREFIXO}{modelo_id}",
                    f"Faltam apenas {limite['falta']} de {limite['modelo']} "
                    f"nesta solicitação; foram escolhidas {quantidade}.",
                )

        if total == 0:
            raise forms.ValidationError(
                "Escolha ao menos uma unidade para reservar com o agente."
            )
        return dados

    def itens(self):
        """`[(modelo, quantidade)]` do que foi escolhido — entrada do service."""
        return [
            (limite["modelo"], len(self.cleaned_data[f"{self.PREFIXO}{modelo_id}"]))
            for modelo_id, limite in self.limites.items()
            if self.cleaned_data.get(f"{self.PREFIXO}{modelo_id}")
        ]

    def unidades_por_modelo(self):
        """`{modelo_id: [Unidade]}` — as unidades exatas a reservar."""
        return {
            modelo_id: list(self.cleaned_data[f"{self.PREFIXO}{modelo_id}"])
            for modelo_id in self.limites
            if self.cleaned_data.get(f"{self.PREFIXO}{modelo_id}")
        }


class ConfirmarEntregaForm(forms.Form):
    """Confirmação de entrega (ISC-RF-27)."""

    entregue_em = forms.DateTimeField(
        required=False, label="Data e hora efetivas",
        widget=forms.DateTimeInput(
            attrs={"class": "form-control", "type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        help_text="Deixe em branco para usar o momento atual.",
    )
    recebido_por = forms.CharField(
        required=False, max_length=150, label="Quem recebeu",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )


class MotivoForm(forms.Form):
    """Motivo de cancelamento (ISC-RN-09)."""

    motivo = forms.CharField(
        label="Motivo",
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Obrigatório."}
        ),
    )

    def clean_motivo(self):
        texto = (self.cleaned_data["motivo"] or "").strip()
        if len(texto) < 3:
            raise forms.ValidationError("Descreva o motivo do cancelamento.")
        return texto


class BuscaProximidadeForm(forms.Form):
    """Busca de agentes próximos, ancorada numa solicitação (ISC-RF-17/18).

    Escolhe-se O QUE atender e a que distância. Cliente, modelos e quantidades
    saem do próprio pedido — pedi-los de novo era redigitar o que o sistema já
    sabe, e permitia descrever uma combinação (cliente de um pedido, modelo de
    outro) que não corresponde a solicitação nenhuma.

    `latitude`/`longitude` continuam aqui, ocultos: clicar no mapa segue sendo
    uma busca válida a partir de um ponto arbitrário, sem pedido associado.
    """

    solicitacao = forms.ModelChoiceField(
        queryset=Solicitacao.objects.none(), required=False,
        label="Solicitação a atender",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="Selecione uma solicitação…",
    )
    latitude = forms.DecimalField(
        required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput()
    )
    longitude = forms.DecimalField(
        required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput()
    )
    raio_km = forms.IntegerField(
        min_value=1, max_value=1000, label="Distância máxima (km)",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Só o que ainda precisa de agente e tem de onde medir distância.
        # Solicitação coberta não entra: não há o que buscar para ela.
        # Tem de onde medir a distância: coordenada da entrega, ou — para os
        # pedidos abertos antes de a entrega ter coordenada própria — a do
        # cadastro do cliente. O `Q` espelha `Solicitacao.coordenada_de_busca`.
        self.fields["solicitacao"].queryset = (
            Solicitacao.objects.filter(
                Q(entrega_latitude__isnull=False)
                | Q(cliente__latitude__isnull=False),
                status__in=(
                    StatusSolicitacao.ABERTA,
                    StatusSolicitacao.ATRIBUIDA,
                    StatusSolicitacao.EM_ROTA,
                ),
            )
            .select_related("cliente")
            .order_by("-aberta_em")
        )
        if not self.is_bound:
            self.fields["raio_km"].initial = ConfiguracaoIscas.carregar().raio_padrao_km

    def clean(self):
        dados = super().clean()
        if dados.get("solicitacao"):
            return dados
        if dados.get("latitude") is None or dados.get("longitude") is None:
            raise forms.ValidationError(
                "Escolha uma solicitação, ou clique no mapa para definir o "
                "ponto de referência."
            )
        return dados


class ExtratoFiltroForm(forms.Form):
    """Filtros do extrato de movimentações (ISC-RF-34)."""

    inicio = forms.DateField(
        required=False, label="De",
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
        ),
    )
    fim = forms.DateField(
        required=False, label="Até",
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
        ),
    )
    agente = forms.ModelChoiceField(
        queryset=Agente.objects.none(), required=False, label="Agente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.none(), required=False, label="Cliente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    modelo = forms.ModelChoiceField(
        queryset=ModeloEquipamento.objects.none(), required=False, label="Modelo",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    tipo = forms.ChoiceField(
        required=False, choices=[("", "Todos"), *TipoMovimentacao.choices],
        label="Tipo", widget=forms.Select(attrs={"class": "form-select"}),
    )
    identificador = forms.CharField(
        required=False, label="Identificador da unidade",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `todos` e não `objects`: o extrato é histórico, e um agente
        # desativado continua tendo movimentações que precisam ser filtráveis.
        self.fields["agente"].queryset = Agente.todos.order_by("nome")
        self.fields["cliente"].queryset = Cliente.todos.order_by("nome_razao_social")
        self.fields["modelo"].queryset = ModeloEquipamento.todos.order_by("nome")

    def clean(self):
        dados = super().clean()
        if dados.get("inicio") and dados.get("fim") and dados["inicio"] > dados["fim"]:
            raise forms.ValidationError("A data inicial é posterior à final.")
        return dados

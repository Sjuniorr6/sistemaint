"""Forms de abertura e dos modais de ação do app Chamados.

Os forms são o portão que valida a entrada antes de chamar o service; as regras
de fluxo (transição, posse) NÃO se repetem aqui — moram em services.py. Os
dropdowns de responsável listam só o grupo certo (RF-05, RF-21)."""
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator

from acompanhamento.models import Clientes
from produto.models import Produto
from chamados.enums import GRUPO_INTELIGENCIA, Categoria, CustoEquipamento, MeioContato

User = get_user_model()


def _usuarios_do_grupo(nome_grupo):
    """Queryset de usuários ativos de um grupo, ordenado por username (dropdowns)."""
    return User.objects.filter(
        is_active=True, groups__name=nome_grupo
    ).order_by("username").distinct()


class MultiTextWidget(forms.TextInput):
    """Widget que aceita VÁRIOS inputs de mesmo nome e os junta numa string.

    O chamado pode ter mais de um equipamento; o template renderiza N inputs com
    o mesmo `name`. Aqui lemos todos via getlist(), descartamos vazios e juntamos
    por ", ". Assim o resto do form/serviço continua tratando um único texto.
    """

    def value_from_datadict(self, data, files, name):
        if hasattr(data, "getlist"):
            valores = data.getlist(name)
        else:  # dict simples (ex.: initial em teste): trata como valor único
            valor = data.get(name)
            valores = valor if isinstance(valor, (list, tuple)) else [valor]
        limpos = [v.strip() for v in valores if v and v.strip()]
        return ", ".join(limpos)


class MultiEquipamentoField(forms.CharField):
    """CharField cujo valor vem de múltiplos inputs (via MultiTextWidget)."""

    widget = MultiTextWidget


class AberturaChamadoForm(forms.Form):
    """Abertura do chamado (RF-01, RF-06).

    O fluxo normal grava ABERTO. Marcando `encaminhar`, exige procedimento,
    tratativa e um responsável da Inteligência (RN-08) — validado em clean().
    """

    # cliente puxa do cadastro do sistema (acompanhamento.Clientes) num select2
    # com busca — não é mais texto livre. Ordenado por nome para a lista longa.
    cliente = forms.ModelChoiceField(
        queryset=Clientes.objects.order_by("nome"),
        widget=forms.Select(attrs={"class": "form-select select2"}),
        empty_label="Selecione o cliente",
    )
    categoria = forms.ChoiceField(
        choices=Categoria.choices,
        widget=forms.Select(attrs={"class": "form-select select2"}),
    )
    # Aceita múltiplos equipamentos: o template renderiza vários inputs de mesmo
    # name e o widget os junta em "EQ-1, EQ-2". max_length casa com o model (500).
    numero_equipamento = MultiEquipamentoField(
        max_length=500,
        widget=MultiTextWidget(attrs={"class": "form-control"}),
    )
    # modelo_equipamento puxa do cadastro de produtos (produto.Produto), a mesma
    # fonte do "Tipo produto" da entrada de manutenção, num select2 com busca.
    modelo_equipamento = forms.ModelChoiceField(
        queryset=Produto.objects.order_by("nome"),
        label="Modelo do equipamento",
        widget=forms.Select(attrs={"class": "form-select select2"}),
        empty_label="Selecione o modelo",
    )
    problema_relatado = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    # `responsavel` (Quality) NÃO é campo do form: é sempre o usuário logado
    # (definido na view a partir de request.user). Assim ninguém consegue forjar
    # outro responsável via POST — a view ignora qualquer valor enviado.

    # — Contato feito por (quem acionou o Quality) —
    # Nome e meio são obrigatórios; telefone/email complementam (opcionais).
    contato_nome = forms.CharField(
        max_length=120,
        label="Nome",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contato_telefone = forms.CharField(
        max_length=30,
        required=False,
        label="Telefone",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    contato_email = forms.EmailField(
        max_length=254,
        required=False,
        label="Email",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    contato_meio = forms.ChoiceField(
        choices=MeioContato.choices,
        label="Meio de comunicação",
        widget=forms.Select(attrs={"class": "form-select select2"}),
    )

    # — Fluxo "abrir já encaminhado" (RN-08) —
    encaminhar = forms.BooleanField(
        required=False,
        label="Abrir já encaminhado para a Inteligência",
        # x-model liga o checkbox ao estado Alpine `encaminhar`: marcar/desmarcar
        # mostra/esconde os campos de encaminhamento na hora, sem submit.
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "x-model": "encaminhar"}
        ),
    )
    procedimento_realizado = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    tratativa = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    responsavel_inteligencia = forms.ModelChoiceField(
        required=False,
        queryset=_usuarios_do_grupo(GRUPO_INTELIGENCIA),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Responsável (Inteligência)",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("encaminhar"):
            # UX antecipada do RN-08 (o service reforça a mesma regra).
            if not cleaned.get("procedimento_realizado"):
                self.add_error("procedimento_realizado", "Obrigatório ao abrir encaminhado.")
            if not cleaned.get("tratativa"):
                self.add_error("tratativa", "Obrigatório ao abrir encaminhado.")
            if not cleaned.get("responsavel_inteligencia"):
                self.add_error("responsavel_inteligencia", "Obrigatório ao abrir encaminhado.")
        return cleaned


class EncaminharForm(forms.Form):
    """Modal Encaminhar (RF-13, RN-09)."""

    procedimento_realizado = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )
    tratativa = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )
    responsavel_inteligencia = forms.ModelChoiceField(
        queryset=_usuarios_do_grupo(GRUPO_INTELIGENCIA),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Responsável (Inteligência)",
    )


class EncaminharExpedicaoForm(forms.Form):
    """Modal Encaminhar para Expedição (Inteligência → fila da Expedição).

    Sem responsável: a posse em EXPEDICAO é do grupo inteiro (fila compartilhada).
    Exige o procedimento e a tratativa, como o encaminhamento à Inteligência.
    """

    procedimento_realizado = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )
    tratativa = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )


class FaturarForm(forms.Form):
    """Modal "Faturado" (Financeiro → encerra o chamado).

    Um valor e uma NF para o chamado inteiro, registrados ao encerrar.
    """

    valor_faturamento = forms.DecimalField(
        label="Valor do faturamento",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.01", "placeholder": "0,00"}
        ),
    )
    nota_fiscal = forms.CharField(
        label="Nota fiscal (NF)",
        max_length=60,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Número da NF"}
        ),
    )


class ContatoExpedicaoForm(forms.Form):
    """Modal "Tratativas de Contato" (Expedição → cliente).

    Uma tentativa por registro: nome e tratativa são obrigatórios; telefone e
    código de rastreio complementam (o rastreio só existe depois da postagem).
    """

    nome_contato = forms.CharField(
        max_length=120,
        label="Pessoa contatada",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    telefone = forms.CharField(
        max_length=30,
        required=False,
        label="Telefone",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    tratativa = forms.CharField(
        label="Tratativa",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Ex.: sem sucesso / cliente vai enviar dia 20…",
            }
        ),
    )
    codigo_rastreio = forms.CharField(
        max_length=60,
        required=False,
        label="Código de rastreio",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Se já postado"}
        ),
    )


class ManutencaoChoiceField(forms.ModelChoiceField):
    """ModelChoiceField que rotula a manutenção como "#ID · Empresa"."""

    def label_from_instance(self, obj):
        empresa = getattr(obj.nome, "nome", "") if obj.nome_id else ""
        return f"#{obj.id} · {empresa}" if empresa else f"#{obj.id}"


class EncaminharComercialForm(forms.Form):
    """Modal Encaminhar para Comercial (Laboratório → fila do Comercial).

    A tratativa é POR EQUIPAMENTO: o form é construído dinamicamente com um campo
    de texto para cada equipamento do chamado (numero_equipamento é multi-valor).
    Além das tratativas, o laboratório vincula a MANUTENÇÃO (entrada de
    equipamento) correspondente ao chamado — obrigatório.
    Sem responsável (posse do grupo inteiro, fila compartilhada).
    """

    def __init__(self, *args, equipamentos=None, **kwargs):
        super().__init__(*args, **kwargs)
        # `equipamentos`: lista de números (ex.: ["EQ-1", "EQ-2"]). Guardamos a
        # ordem para reconstruir os pares (numero, tratativa) no cleaned_data.
        self.equipamentos = list(equipamentos or [])
        for i, numero in enumerate(self.equipamentos):
            self.fields[f"tratativa_{i}"] = forms.CharField(
                label=numero,
                widget=forms.Textarea(
                    attrs={
                        "class": "form-control",
                        "rows": 2,
                        "placeholder": f"Tratativa de {numero}…",
                    }
                ),
            )

        # Vínculo com a manutenção (entrada de equipamento) — obrigatório. Fica
        # por último no form para renderizar abaixo das tratativas no modal.
        from chamados.selectors import manutencoes_para_vinculo

        self.fields["manutencao"] = ManutencaoChoiceField(
            queryset=manutencoes_para_vinculo(),
            label="Manutenção vinculada",
            empty_label="Selecione a manutenção",
            widget=forms.Select(attrs={"class": "form-select select2"}),
        )

    def tratativas_por_equipamento(self):
        """Pares {numero, tratativa} a partir do cleaned_data (após is_valid)."""
        return [
            {"numero": numero, "tratativa": self.cleaned_data.get(f"tratativa_{i}", "")}
            for i, numero in enumerate(self.equipamentos)
        ]

    def campos_tratativa(self):
        """Só os campos de tratativa (para o template renderizar por equipamento)."""
        return [self[f"tratativa_{i}"] for i, _ in enumerate(self.equipamentos)]


class FinalizarComercialForm(forms.Form):
    """Modal Finalizar (Comercial → RESOLVIDO), POR EQUIPAMENTO.

    Para cada equipamento do chamado, o Comercial informa a tratativa e seleciona
    o custo (com/sem). Construído dinamicamente como o form do laboratório.
    """

    def __init__(self, *args, equipamentos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.equipamentos = list(equipamentos or [])
        for i, numero in enumerate(self.equipamentos):
            self.fields[f"tratativa_{i}"] = forms.CharField(
                label=numero,
                widget=forms.Textarea(
                    attrs={
                        "class": "form-control",
                        "rows": 2,
                        "placeholder": f"Tratativa de {numero}…",
                    }
                ),
            )
            self.fields[f"custo_{i}"] = forms.ChoiceField(
                label=f"Custo de {numero}",
                choices=CustoEquipamento.choices,
                widget=forms.Select(
                    attrs={
                        "class": "form-select ch-custo",
                        # Alpine observa estes selects para revelar o campo do
                        # termo quando algum equipamento fica COM CUSTO.
                        "@change": "recalcular()",
                        "x-ref": f"custo{i}",
                    }
                ),
            )

        # Termo de substituição: exigido quando houver equipamento COM CUSTO.
        # `required=False` aqui porque a obrigatoriedade é condicional (clean()).
        self.fields["termo_substituicao"] = forms.FileField(
            required=False,
            label="Termo de substituição (PDF)",
            validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
            widget=forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "application/pdf,.pdf"}
            ),
        )

    def clean(self):
        cleaned = super().clean()
        # Regra: ao menos um equipamento COM CUSTO ⇒ termo obrigatório.
        tem_custo = any(
            cleaned.get(f"custo_{i}") == CustoEquipamento.COM_CUSTO
            for i, _ in enumerate(self.equipamentos)
        )
        if tem_custo and not cleaned.get("termo_substituicao"):
            self.add_error(
                "termo_substituicao",
                "Anexe o termo de substituição (PDF): há equipamento com custo.",
            )
        return cleaned

    def finalizacao_por_equipamento(self):
        """Trios {numero, tratativa, custo} do cleaned_data (após is_valid)."""
        return [
            {
                "numero": numero,
                "tratativa": self.cleaned_data.get(f"tratativa_{i}", ""),
                "custo": self.cleaned_data.get(f"custo_{i}", ""),
            }
            for i, numero in enumerate(self.equipamentos)
        ]

    def linhas_equipamento(self):
        """Agrupa os campos por equipamento p/ o template renderizar em pares:
        [{numero, tratativa: BoundField, custo: BoundField}, ...]."""
        return [
            {
                "numero": numero,
                "tratativa": self[f"tratativa_{i}"],
                "custo": self[f"custo_{i}"],
            }
            for i, numero in enumerate(self.equipamentos)
        ]


class FinalizarForm(forms.Form):
    """Modal Finalizar/Resolver (RF-12, RF-16, RN-10)."""

    procedimento_realizado = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )


class MotivoForm(forms.Form):
    """Modal Bloquear/Reabrir (RF-14, RF-15, RN-11, RN-12)."""

    motivo = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )

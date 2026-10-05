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
from chamados.enums import (
    GRUPO_INTELIGENCIA,
    Categoria,
    CustoEquipamento,
    DestinoEquipamento,
    MeioContato,
    Setor,
)

User = get_user_model()


def _usuarios_do_grupo(nome_grupo):
    """Queryset de usuários ativos de um grupo, ordenado por username (dropdowns)."""
    return User.objects.filter(
        is_active=True, groups__name=nome_grupo
    ).order_by("username").distinct()


class EquipamentosWidget(forms.Widget):
    """Lê os blocos "modelo + números" da abertura.

    A tela renderiza um bloco por modelo: `grupo` (id do bloco, repetido),
    `grupo_<id>_modelo`, `grupo_<id>_customizacao`, `grupo_<id>_tipo_contrato`
    (selects) e `grupo_<id>_numero` (N inputs). Devolve uma lista de dicts crus;
    bloco totalmente vazio é descartado.
    """

    def value_from_datadict(self, data, files, name):
        def lista(chave):
            if hasattr(data, "getlist"):
                return data.getlist(chave)
            valor = data.get(chave)
            if valor is None:
                return []
            return list(valor) if isinstance(valor, (list, tuple)) else [valor]

        grupos = []
        for gid in dict.fromkeys(lista("grupo")):  # ordem da tela, sem repetir
            grupo = {
                campo: str(data.get(f"grupo_{gid}_{campo}") or "").strip()
                for campo in ("modelo", "customizacao", "tipo_contrato")
            }
            grupo["numeros"] = [
                n.strip() for n in lista(f"grupo_{gid}_numero") if n and n.strip()
            ]
            if any(grupo.values()):
                grupos.append(grupo)
        return grupos


class EquipamentosField(forms.Field):
    """Equipamentos do chamado agrupados por modelo.

    Entra a lista de blocos e sai [(número, Produto, customização, contrato)] —
    um modelo por nº, o formato que o service de abertura grava. Customização e
    contrato são obrigatórios em cada bloco e usam o vocabulário da entrada de
    equipamento (a Expedição recebe a entrada já com eles).
    """

    widget = EquipamentosWidget

    def __init__(self, *, queryset, **kwargs):
        self.queryset = queryset
        super().__init__(**kwargs)

    def clean(self, value):
        from registrodemanutencao.models import registrodemanutencao as entrada

        grupos = value or []
        if not grupos:
            raise forms.ValidationError("Informe ao menos um equipamento.")
        customizacoes = {v for v, _ in entrada.custom}
        contratos = {v for v, _ in entrada.contrato_tipo}
        # Uma query só para todos os modelos (sem lookup por bloco).
        ids = {g["modelo"] for g in grupos if g["modelo"].isdigit()}
        produtos = {str(p.pk): p for p in self.queryset.filter(pk__in=ids)}
        erros = []
        numeros_vistos = set()
        for g in grupos:
            modelo_id, numeros = g["modelo"], g["numeros"]
            rotulo = produtos.get(modelo_id) or "sem modelo"
            if not modelo_id:
                erros.append(f"Selecione o modelo dos equipamentos {', '.join(numeros)}.")
            elif modelo_id not in produtos:
                erros.append("Modelo de equipamento inválido.")
            elif not numeros:
                erros.append(f"Informe ao menos um nº para o modelo {rotulo}.")
            if g["customizacao"] not in customizacoes:
                erros.append(f"Selecione a customização do modelo {rotulo}.")
            if g["tipo_contrato"] not in contratos:
                erros.append(f"Selecione o tipo de contrato do modelo {rotulo}.")
            for numero in numeros:
                if len(numero) > 60:
                    erros.append(f"Nº {numero[:20]}…: máximo de 60 caracteres.")
                elif numero in numeros_vistos:
                    erros.append(f"Nº {numero} informado mais de uma vez.")
                numeros_vistos.add(numero)
        if erros:
            raise forms.ValidationError(list(dict.fromkeys(erros)))
        return [
            (numero, produtos[g["modelo"]], g["customizacao"], g["tipo_contrato"])
            for g in grupos
            for numero in g["numeros"]
        ]


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
    # Um ou mais equipamentos, cada um com o SEU modelo (ex.: isca 4G + isca 2G).
    # Modelos vêm do cadastro de produtos (produto.Produto), a mesma fonte do
    # "Tipo produto" da entrada de manutenção.
    equipamentos = EquipamentosField(
        queryset=Produto.objects.order_by("nome"), label="Equipamentos"
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

    def grupos_equipamento(self):
        """Blocos para o template: o que foi postado (ao reexibir com erro) ou
        um bloco vazio."""
        vazio = {"modelo": "", "customizacao": "", "tipo_contrato": "", "numeros": [""]}
        grupos = self["equipamentos"].value() if self.is_bound else None
        return [
            {**g, "numeros": g["numeros"] or [""]} for g in (grupos or [])
        ] or [vazio]

    def opcoes_equipamento(self):
        """Opções de customização e contrato (as mesmas da entrada de equipamento)."""
        from registrodemanutencao.models import registrodemanutencao as entrada

        return {
            "customizacoes": [c for c in entrada.custom if c[0]],
            "contratos": entrada.contrato_tipo,
        }

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


class EncaminharEnvioForm(forms.Form):
    """Modal "Encaminhar para expedição" (Configuração → envio ao cliente)."""

    tratativa = forms.CharField(
        label="O que foi configurado",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )


class RegistrarEnvioForm(forms.Form):
    """Modal "Registrar envio" (Expedição → Financeiro)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from requisicao.models import Requisicoes

        # Mesmas opções de envio da requisição.
        self.fields["metodo_envio"] = forms.ChoiceField(
            label="Método de envio",
            choices=[("", "Selecione")] + list(Requisicoes.tipo_envio),
            widget=forms.Select(attrs={"class": "form-select"}),
        )
        # A ordem dos campos no modal: método, data, rastreio.
        self.order_fields(["metodo_envio", "data_envio", "codigo_rastreio_envio"])

    data_envio = forms.DateField(
        label="Data de envio",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    codigo_rastreio_envio = forms.CharField(
        label="Código de rastreio",
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
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
    """Modal "Realizar tratativa" (Comercial), POR EQUIPAMENTO.

    Para cada equipamento do chamado, o Comercial informa a tratativa, o custo
    (com/sem) e o destino (substituição/devolução). Construído dinamicamente
    como o form do laboratório.
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
            self.fields[f"destino_{i}"] = forms.ChoiceField(
                label=f"Destino de {numero}",
                choices=[("", "Selecione")] + list(DestinoEquipamento.choices),
                widget=forms.Select(attrs={"class": "form-select"}),
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
                "destino": self.cleaned_data.get(f"destino_{i}", ""),
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
                "destino": self[f"destino_{i}"],
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


class FiltroFilaForm(forms.Form):
    """Alfândega do querystring da fila (filtro por setor + período).

    TOLERANTE, no mesmo espírito do FiltroAcionamentosForm: campo ausente ou
    valor inválido significa "sem filtro", nunca erro — por isso tudo é
    `required=False` e a view trata form inválido como nenhum filtro.

    `setor` diz por qual marco da linha do tempo o período recorta: escolhido,
    o corte é a entrada naquele setor; vazio, é a abertura do chamado.
    """

    setor = forms.ChoiceField(
        required=False,
        choices=[("", "Abertura do chamado")] + list(Setor.choices),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    # ISO = o que o <input type="date"> envia; dd/mm/aaaa = URL digitada à mão.
    data_de = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(
            attrs={"class": "form-control form-control-sm", "type": "date"}
        ),
    )
    data_ate = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(
            attrs={"class": "form-control form-control-sm", "type": "date"}
        ),
    )

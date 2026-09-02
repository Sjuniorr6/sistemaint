"""Forms de cadastro: Agente, Cliente, Depósito e Modelo."""
from django import forms

from iscas.crypto import cpf_valido, normalizar_cpf
from iscas.enums import UF_CHOICES
from iscas.models.cadastro import Agente, Cliente, Deposito, ModeloEquipamento

#: Campos de endereço, compartilhados pelos três cadastros geolocalizados.
CAMPOS_ENDERECO = [
    "logradouro", "numero", "complemento", "bairro", "cidade", "uf", "cep",
]


def _widgets_bootstrap(campos, extras=None):
    """Classes do Bootstrap 5.3, que é o que o GSInt usa."""
    widgets = {
        campo: forms.TextInput(attrs={"class": "form-control"}) for campo in campos
    }
    widgets.update(extras or {})
    return widgets


class _EnderecoFormMixin(forms.Form):
    """Endereço + pin ajustável no próprio formulário.

    Herda de `forms.Form` — e não é um mixin solto — porque só a metaclass do
    Django coleta os campos declarados abaixo. Como classe simples, os três
    campos ocultos seriam silenciosamente ignorados.

    Duas responsabilidades:

    1. Detectar se o endereço mudou, para decidir se regeocodifica. Sem isso,
       todo save dispararia uma chamada ao Nominatim — inclusive ao editar só
       o telefone.
    2. Receber a coordenada do pin que o operador arrastou no mapa de
       conferência. Quando ele arrasta, a posição vale mais que a
       geocodificação automática (ISC-RF-03) e o save marca `geo_origem=MANUAL`.
    """

    #: Preenchidos por JS quando o operador arrasta o pin no mapa do form.
    latitude_ajustada = forms.DecimalField(
        required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput()
    )
    longitude_ajustada = forms.DecimalField(
        required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput()
    )
    #: "1" quando a posição veio do arrasto, e não da geocodificação da prévia.
    pin_movido = forms.CharField(required=False, widget=forms.HiddenInput())

    #: Campos de endereço exigidos por este formulário. Agente e depósito
    #: exigem os três — sem endereço eles saem da busca por proximidade, que é
    #: a razão de existir do cadastro deles. Cliente sobrescreve com lista
    #: vazia: a entrega vai para onde a solicitação disser, e exigir um
    #: endereço que ninguém usa só produz dado inventado.
    ENDERECO_OBRIGATORIO = ("logradouro", "cidade", "uf")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in CAMPOS_ENDERECO:
            if campo in self.fields:
                self.fields[campo].required = campo in self.ENDERECO_OBRIGATORIO

    def endereco_mudou(self) -> bool:
        if not self.instance.pk:
            return True
        return any(campo in self.changed_data for campo in CAMPOS_ENDERECO)

    def pin_ajustado(self):
        """Coordenada arrastada à mão, ou None.

        Só considera ajuste manual quando o operador de fato moveu o pin: a
        prévia do mapa também preenche os campos ocultos, e tratá-la como
        manual congelaria a coordenada, impedindo a regeocodificação futura.
        """
        if not self.is_valid():
            return None
        if self.cleaned_data.get("pin_movido") != "1":
            return None
        latitude = self.cleaned_data.get("latitude_ajustada")
        longitude = self.cleaned_data.get("longitude_ajustada")
        if latitude is None or longitude is None:
            return None
        return latitude, longitude


class AgenteForm(_EnderecoFormMixin, forms.ModelForm):
    """Cadastro de agente (ISC-RF-01).

    O CPF não é campo do model (fica cifrado em `cpf_cifrado` + `cpf_hash`),
    então entra como campo declarado e é atribuído pela property no save.
    """

    cpf = forms.CharField(
        max_length=14,
        label="CPF",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "000.000.000-00"}
        ),
    )

    class Meta:
        model = Agente
        fields = ["nome", "telefone", "email", *CAMPOS_ENDERECO, "observacao"]
        widgets = _widgets_bootstrap(
            ["nome", "telefone", *CAMPOS_ENDERECO],
            {
                "email": forms.EmailInput(attrs={"class": "form-control"}),
                "uf": forms.Select(
                    choices=[("", "—"), *UF_CHOICES], attrs={"class": "form-select"}
                ),
                "observacao": forms.Textarea(
                    attrs={"class": "form-control", "rows": 2}
                ),
            },
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["cpf"].initial = self.instance.cpf

    def clean_cpf(self):
        cpf = normalizar_cpf(self.cleaned_data["cpf"])
        if not cpf_valido(cpf):
            raise forms.ValidationError("CPF inválido.")

        # Unicidade via hash, sem decifrar a base (ISC-ADR-14).
        from iscas.crypto import hash_cpf

        existente = Agente.todos.filter(cpf_hash=hash_cpf(cpf))
        if self.instance.pk:
            existente = existente.exclude(pk=self.instance.pk)
        if existente.exists():
            raise forms.ValidationError("Já existe um agente com este CPF.")
        return cpf

    def save(self, commit=True):
        agente = super().save(commit=False)
        agente.cpf = self.cleaned_data["cpf"]  # property: cifra e faz o hash
        if commit:
            agente.save()
        return agente


class ClienteForm(_EnderecoFormMixin, forms.ModelForm):
    """Cadastro de cliente (ISC-RF-04).

    Endereço é OPCIONAL aqui, diferente de agente e depósito. O cliente pode
    querer a isca entregue em outro lugar — obra, filial, endereço do veículo —
    e nesses casos o endereço de cadastro não existe ou não serve. Quem define
    para onde a entrega vai é a solicitação, que tem o próprio endereço e a
    própria coordenada.
    """

    #: Nenhum: ver a docstring. O endereço, quando preenchido, continua sendo
    #: geocodificado e usado como sugestão na abertura da solicitação.
    ENDERECO_OBRIGATORIO = ()

    class Meta:
        model = Cliente
        fields = [
            "nome_razao_social", "documento", "tipo_documento",
            "contato_nome", "telefone", "email", "comercial_responsavel",
            *CAMPOS_ENDERECO, "observacao",
        ]
        widgets = _widgets_bootstrap(
            ["nome_razao_social", "documento", "contato_nome", "telefone",
             "comercial_responsavel", *CAMPOS_ENDERECO],
            {
                "tipo_documento": forms.Select(attrs={"class": "form-select"}),
                "email": forms.EmailInput(attrs={"class": "form-control"}),
                "uf": forms.Select(
                    choices=[("", "—"), *UF_CHOICES], attrs={"class": "form-select"}
                ),
                "observacao": forms.Textarea(
                    attrs={"class": "form-control", "rows": 2}
                ),
            },
        )


class DepositoForm(_EnderecoFormMixin, forms.ModelForm):
    """Ponto de estoque da empresa (matriz, filial, almoxarifado).

    É de onde o equipamento novo entra e de onde sai para os agentes. Tem
    endereço geocodificado como agente e cliente — não para busca por
    proximidade, mas para o operador saber de qual unidade física está falando
    quando houver mais de uma.
    """

    class Meta:
        model = Deposito
        fields = ["nome", *CAMPOS_ENDERECO]
        widgets = _widgets_bootstrap(
            ["nome", *CAMPOS_ENDERECO],
            {
                "uf": forms.Select(
                    choices=[("", "—"), *UF_CHOICES], attrs={"class": "form-select"}
                )
            },
        )


class ModeloForm(forms.ModelForm):
    """Cadastro de modelo (ISC-RF-05).

    O bloqueio da troca de tipo (ISC-RN-04) fica no `clean()` do model e no
    service; aqui o campo é apenas desabilitado, para o operador entender por
    quê antes de tentar.
    """

    class Meta:
        model = ModeloEquipamento
        fields = ["nome", "codigo", "fabricante", "descricao", "tipo"]
        widgets = _widgets_bootstrap(
            ["nome", "codigo", "fabricante"],
            {
                "tipo": forms.Select(attrs={"class": "form-select"}),
                "descricao": forms.Textarea(
                    attrs={"class": "form-control", "rows": 3}
                ),
            },
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.tem_movimentacao():
            self.fields["tipo"].disabled = True
            self.fields["tipo"].help_text = (
                "Este modelo já tem unidades movimentadas; o tipo não pode mudar "
                "(ISC-RN-04)."
            )

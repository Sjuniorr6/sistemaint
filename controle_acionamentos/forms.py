# controle_acionamentos/forms.py
from django import forms

from controle_acionamentos.models import Acionamento, Agente, Cliente, FranquiaAgente


class AcionamentoForm(forms.ModelForm):
    """Form de criação de Acionamento (US-05).

    Só os campos que o operador digita. Os 5 calculados são editable=False
    no model e ficam fora por construção — quem os preenche é o save().

    Não duplico RN-04/05/06 aqui: ao rodar is_valid(), o ModelForm chama
    full_clean() do model, que dispara o Acionamento.clean(). O form é o
    portão que garante o full_clean antes do save (fecha o marco 7).
    """

    class Meta:
        model = Acionamento
        fields = [
            "cliente",
            "nome_servico",
            "valor_acionamento",
            "franquia_km",
            "franquia_horas",
            "valor_km_excedente",
            "valor_hora_excedente",
            "origem",
            "destino",
            "responsavel_agente",
            "agente",
            "placa_agente",
            "motorista",
            "placa_motorista",
            "numero_motorista",
            "data_hora_solicitado",
            "data_hora_inicio",
            "data_hora_final",
            "km_inicio",
            "km_final",
            "pedagio",
            "franquia_agente",
        ]
        widgets = {
            "cliente": forms.Select(attrs={"class": "form-select"}),
            "nome_servico": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: Escolta Moto"}
            ),
            "valor_acionamento": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            # min=1 espelha o MinValueValidator(1) do model (pendente do tech lead).
            "franquia_km": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "franquia_horas": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "valor_km_excedente": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "valor_hora_excedente": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "origem": forms.TextInput(attrs={"class": "form-control"}),
            "destino": forms.TextInput(attrs={"class": "form-control"}),
            "responsavel_agente": forms.Select(attrs={"class": "form-select"}),
            "agente": forms.Select(attrs={"class": "form-select"}),
            "placa_agente": forms.TextInput(attrs={"class": "form-control"}),
            "motorista": forms.TextInput(attrs={"class": "form-control"}),
            "placa_motorista": forms.TextInput(attrs={"class": "form-control"}),
            "numero_motorista": forms.TextInput(attrs={"class": "form-control"}),
            "data_hora_solicitado": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "data_hora_inicio": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "data_hora_final": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "km_inicio": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "km_final": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "pedagio": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "franquia_agente": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O <input type="datetime-local"> envia "AAAA-MM-DDTHH:MM". O `format`
        # do widget controla só a exibição; o parsing do POST depende de
        # input_formats. Sem isto, datas válidas seriam rejeitadas.
        for campo in ("data_hora_solicitado", "data_hora_inicio", "data_hora_final"):
            self.fields[campo].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"]


class PedagioUpdateForm(forms.Form):
    """Valida a entrada do endpoint inline de pedágio (DD-014/M3); min_value=0 implementa AC-07.3."""

    pedagio = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2)


class VincularFranquiaLoteForm(forms.Form):
    """DD-015/M4 (subtask 5) — valida a entrada do vínculo em lote:
    seleção de acionamentos, franquia e flag de sobrescrita (AC-06.5)."""

    acionamentos = forms.ModelMultipleChoiceField(
        queryset=Acionamento.objects.all()
    )
    franquia = forms.ModelChoiceField(queryset=FranquiaAgente.objects.all())
    sobrescrever = forms.BooleanField(required=False)


class FiltroAcionamentosForm(forms.Form):
    """DD-015/M4 (AC-06.1) — valida o querystring da listagem. Filtro TOLERANTE:
    valor inválido ou ausente significa "sem filtro", nunca erro. Por isso o
    campo é required=False; a view trata form inválido como cliente=None.

    DD-016/M5 (AC-08.1) — o form é a alfândega da querystring: cada campo novo
    de filtro entra aqui mantendo a filosofia tolerante (inválido/ausente = sem
    filtro), e a view repassa o valor limpo ao selector."""

    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    agente = forms.ModelChoiceField(
        queryset=Agente.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    # ISO = o que o <input type="date"> envia; dd/mm/aaaa = URL digitada à brasileira.
    data_de = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    data_ate = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "Todos"), ("com", "Com franquia"), ("sem", "Sem franquia")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def clean_status(self):
        """Traduz tela→domínio: "com"→True, "sem"→False, vazio→None."""
        valor = self.cleaned_data.get("status")
        if valor == "com":
            return True
        if valor == "sem":
            return False
        return None


class AgenteForm(forms.ModelForm):
    """DD-050/ST2 — form de criação/edição de Agente.

    Estas telas SUBSTITUEM o admin: o operador cadastra aqui inclusive os dados
    de pagamento (bancários) e os clientes vinculados (M2M). A validação (nome
    obrigatório, CPF válido e normalizado, CNH válida se preenchida) mora no
    Agente.clean() — o ModelForm o dispara no is_valid(); NÃO se duplica aqui.
    O M2M clientes_vinculados persiste sozinho no form.save() (sem commit=False).
    """

    class Meta:
        model = Agente
        fields = [
            "nome",
            "cpf",
            "cnh",
            "chave_pix",
            "banco",
            "tipo_conta",
            "agencia",
            "conta",
            "clientes_vinculados",
        ]
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: Carlos Silva"}
            ),
            "cpf": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "000.000.000-00"}
            ),
            "cnh": forms.TextInput(attrs={"class": "form-control"}),
            "chave_pix": forms.TextInput(attrs={"class": "form-control"}),
            "banco": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_conta": forms.Select(attrs={"class": "form-select"}),
            "agencia": forms.TextInput(attrs={"class": "form-control"}),
            "conta": forms.TextInput(attrs={"class": "form-control"}),
            # CheckboxSelectMultiple posta a MESMA lista (name="clientes_vinculados")
            # que o SelectMultiple — contrato de POST intacto. Sem attrs de classe:
            # o estilo vem do CSS do escopo (.acn-multicheck no tema.css).
            "clientes_vinculados": forms.CheckboxSelectMultiple(),
        }


class ClienteForm(forms.ModelForm):
    """DD-050/ST1 — form de criação/edição de Cliente.

    Só os campos que o operador digita. A validação (nome obrigatório, CNPJ
    válido e normalização para dígitos) mora no Cliente.clean() — o ModelForm o
    dispara no is_valid() via full_clean(); NÃO se duplica a regra aqui.
    """

    class Meta:
        model = Cliente
        fields = ["nome_empresa", "cnpj"]
        widgets = {
            "nome_empresa": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: ACME Logística LTDA"}
            ),
            "cnpj": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "00.000.000/0000-00"}
            ),
        }
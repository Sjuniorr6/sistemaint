# controle_acionamentos/forms.py
from django import forms

from controle_acionamentos.models import Acionamento


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
from django import forms
from django.forms import inlineformset_factory
from .models import (
    registrodeagenteacompanhamento,
    registroacompanhamento,
    servicosacompanhamentos,
    registrodeclienteacompanhamento,
    registroacompanhamentoagente
)

# ===============================
# Cadastro de Agentes
# ===============================
class RegistroAgente(forms.ModelForm):
    class Meta:
        model = registrodeagenteacompanhamento
        fields = [
            'nome',
            'cpf',
            'pix',
            'banco',
            'agencia',
            'conta',
            'tipo_conta',
        ]

        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Cliente'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CPF'}),
            'pix': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pix'}),
            'banco': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Banco'}),
            'agencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Agência'}),
            'conta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Conta'}),
            'tipo_conta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tipo de Conta'}),
        }

# ===============================
# Cadastro de Clientes
# ===============================
class FormulariosForm(forms.ModelForm):
    class Meta:
        model = registrodeclienteacompanhamento
        fields = [
            'nome',
            'cnpj',
            'email',
        ]

        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Cliente'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CNPJ'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
        }

# ===============================
# Cadastro de Serviços
# ===============================
class ServicosAcompanhamentosForm(forms.ModelForm):
    class Meta:
        model = servicosacompanhamentos
        fields = [
            'nomeclatura',
            'tipo',
            'agentes',
        ]

        widgets = {
            'nomeclatura': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Acompanhamento Urbano – Moto'
            }),

            'tipo': forms.Select(attrs={
                'class': 'form-control',
            }),

            'agentes': forms.Select(attrs={
                'class': 'form-control',
            }),
        }

        labels = {
            'nomeclatura': 'Nomenclatura do Serviço',
            'tipo': 'Tipo do Serviço',
            'agentes': 'Quantidade de Agentes',
        }

# ===============================
# Cadastro de Acompanhamento
# ===============================
class RegistroAcompanhamentoForm(forms.ModelForm):
    class Meta:
        model = registroacompanhamento
        fields = [
            "cliente",
            "tipo_servico",
            "origem",
            "destino",
            "ocorrencia",
        ]
        widgets = {
            "cliente": forms.Select(attrs={"class": "form-control select2"}),
            "tipo_servico": forms.Select(attrs={"class": "form-control select2"}),
            "origem": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Origem'}),
            "destino": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Destino'}),
            "ocorrencia": forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Descreva a Ocorrência', 'rows': 3}),
        }

class RegistroAcompanhamentoAgenteForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in ["data_solicitada", "data_inicio", "data_finalizacao"]:
            self.fields[field_name].input_formats = ["%Y-%m-%d"]

    class Meta:
        model = registroacompanhamentoagente
        exclude = ("acompanhamento",)

        widgets = {
            "responsavel_agente": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Responsável pelo Agente'}),

            "agente": forms.Select(attrs={"class": "form-control select2"}),
            "franquia": forms.Select(attrs={"class": "form-control"}),

            "placa_agente": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Placa Agente'}),
            "motorista": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Motorista'}),
            "placa_motorista": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Placa Motorista'}),

            "data_solicitada": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "class": "form-control"}
            ),
            "horario_solicitado": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),

            "data_inicio": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "class": "form-control"}
            ),
            "horario_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),

            "data_finalizacao": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "class": "form-control"}
            ),
            "horario_finalizacao": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),

            'horario_total': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'readonly': True,
                    'placeholder': 'HH:MM:SS'
                }
            ),

            "km_inicio": forms.NumberInput(attrs={"class": "form-control", 'placeholder': 'KM Início'}),
            "km_final": forms.NumberInput(attrs={"class": "form-control", 'placeholder': 'KM Final'}),
            "km_total": forms.NumberInput(attrs={"class": "form-control", 'placeholder': 'KM Total', 'readonly': True,}),

            "pedagio": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01"
            }),

            "bancario": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "pix": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Pix'}),
            "banco": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Banco'}),
            "agencia": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Agência'}),
            "conta": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Conta'}),
            "tipo_conta": forms.TextInput(attrs={"class": "form-control", 'placeholder': 'Tipo de Conta'}),
        }

# ===============================
# FORMSET DE AGENTES
# ===============================
RegistroAcompanhamentoAgenteCreateFormSet = inlineformset_factory(
    registroacompanhamento,
    registroacompanhamentoagente,
    form=RegistroAcompanhamentoAgenteForm,
    extra=1,
    can_delete=True
)

# UPDATE → SOMENTE os agentes existentes
RegistroAcompanhamentoAgenteUpdateFormSet = inlineformset_factory(
    registroacompanhamento,
    registroacompanhamentoagente,
    form=RegistroAcompanhamentoAgenteForm,
    extra=0,
    can_delete=True
)


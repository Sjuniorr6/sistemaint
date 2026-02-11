from django import forms
from django.forms import inlineformset_factory
from .models import (
    registrodeagenteacompanhamento,
    registroacompanhamento,
    servicosacompanhamentos,
    registrodeclienteacompanhamento,
    registroacompanhamentoagente,
    registroderesposavelagenteacompanhamento
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
# Cadastro de Responsável Agentes
# ===============================
class RegistroResponsavelAgente(forms.ModelForm):
    class Meta:
        model = registroderesposavelagenteacompanhamento
        fields = [
            'nome',
        ]

        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Responsável do Agente'}),
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
            'valor_acionamento',
            'franquia_km',
            'franquia_horas',
            'valor_km_excedente',
            'valor_horas_excedente',
        ]

        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Cliente'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CNPJ'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'franquia_km': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Franquia de KM',
                'min': 0
            }),

            'franquia_horas': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Franquia de Horas',
                'min': 0
            }),

            # ---------- Valores monetários ----------
            'valor_acionamento': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Valor do Acionamento (R$)',
                'step': '0.01',
                'min': 0
            }),

            'valor_km_excedente': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Valor por KM Excedente (R$)',
                'step': '0.01',
                'min': 0
            }),

            'valor_horas_excedente': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Valor por Hora Excedente (R$)',
                'step': '0.01',
                'min': 0
            }),
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

            "latitude_origem",
            "longitude_origem",
            "raio_cerca",

            "campo_personalizado_titulo",
            "campo_personalizado_valor",

            "ocorrencia",
        ]

        widgets = {
            "cliente": forms.Select(attrs={"class": "form-control select2"}),
            "tipo_servico": forms.Select(attrs={"class": "form-control select2"}),
            "origem": forms.TextInput(attrs={"class": "form-control"}),
            "destino": forms.TextInput(attrs={"class": "form-control"}),

            "latitude_origem": forms.NumberInput(attrs={
                "class": "form-control", 
                "placeholder": "Ex: -23.550520",
                "step": "any"
            }),
            "longitude_origem": forms.NumberInput(attrs={
                "class": "form-control", 
                "placeholder": "Ex: -46.633308",
                "step": "any"
            }),
            "raio_cerca": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Raio em metros"
            }),

            "campo_personalizado_titulo": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Transportadora, Embarcador, Base..."
            }),
            "campo_personalizado_valor": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: FedEx, DHL, Matriz SP..."
            }),

            "ocorrencia": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3
            }),
        }

class RegistroAcompanhamentoAgenteForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.required = False

    class Meta:
        model = registroacompanhamentoagente
        exclude = ("acompanhamento",)

        widgets = {
            "tipo_agente": forms.HiddenInput(),
            
            "responsavel_agente": forms.Select(attrs={"class": "form-control select2"}),

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
            'nome_completo_conta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome Completo'}),
            'cpf_conta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CPF da Conta'}),
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


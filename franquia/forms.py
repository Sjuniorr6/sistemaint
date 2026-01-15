from django import forms
from django.core.exceptions import ValidationError
from datetime import datetime
from .models import registrodefranquia

# Formulário para cadastro e edição de Franquia
class FormulariosForm(forms.ModelForm):
    class Meta:
        model = registrodefranquia
        fields = [
            'nome',
            'valor_acionamento',
            'franquia_km',
            'franquia_horas',
            'valor_km_excedente',
            'valor_horas_excedente',
        ]

        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da Franquia'
            }),

            # ---------- Quantidades ----------
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
# registrodefranquia/forms.py
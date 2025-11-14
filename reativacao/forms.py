from django import forms
from django.forms import inlineformset_factory
from .models import Reativacao, IdIccid

class ReativacaoForm(forms.ModelForm):
    class Meta:
        model = Reativacao
        fields = ['nome', 'motivo_reativacao', 'canal_solicitacao','cnpj', 'observacoes', 'status_reativacao']
        widgets = {
            'nome': forms.Select(attrs={'class': 'form-control'}),
            'motivo_reativacao': forms.Select(attrs={'class': 'form-control'}),
            'canal_solicitacao': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'observacoes': forms.TextInput(attrs={'class': 'form-control'}),
            'status_reativacao': forms.Select(attrs={'class': 'form-control'}),
        }

class IdIccidForm(forms.ModelForm):
    class Meta:
        model = IdIccid
        fields = ['id_equipamentos', 'ccid_equipamentos', 'quantidade']
        widgets = {
            'id_equipamentos': forms.Textarea(attrs={'class': 'form-control'}),
            'ccid_equipamentos': forms.Textarea(attrs={'class': 'form-control'}),
            # Exibido para o usuário para que ele veja a quantidade calculada:
            'quantidade': forms.TextInput(attrs={'class': 'form-control'}),
        }

IdIccidFormSet = inlineformset_factory(Reativacao, IdIccid, form=IdIccidForm, extra=1, can_delete=True)

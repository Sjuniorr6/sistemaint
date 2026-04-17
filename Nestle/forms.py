# forms.py
from django import forms
from .models import GridInternacional, clientesNestle, ValorMensalCliente, Carga, CURRENCY_CHOICES
from django.utils import timezone

class GridInternacionalForm(forms.ModelForm):
    MODELO_CHOICES = [
        ("", "Selecione"),
        ("Tetis Dry", "Tetis Dry"),
        ("Guardian", "Guardian"),
        ("GG LL", "GG LL"),
    ]

    modelo = forms.ChoiceField(choices=MODELO_CHOICES, required=False)

    class Meta:
        model = GridInternacional
        fields = [
            "data_envio",
            "requisicao",   
            "cliente",
            "local_de_entrega",
            "modelo",
            "id_planilha",
            "id2",
            "ccid",
            "sla_insercao",
            "data_insercao",
            "destino",
            "bl",
            "container",
            "sla_viagem",
            "data_chegada_destino",
            "sla_retirada",
            "data_retirada",
            "sla_envio_brasil",
            "data_envio_brasil",
            "sla_chegada_brasil",
            "data_brasil",
            "status_operacao",
            "sla_operacao",
            "reposicao",
            "observacao",
            "data_chegada_porto",
            "data_embarque_maritimo",
            "data_desembarque_maritimo",
            "data_envoice",
            "data_chegada_terminal",
            "data_saida_terminal",
            "sla_porto_nacional",
            "sla_terrestre",
            "sla_maritimo",
            "sla_terminal_internacional",
            "sla_terrestre_internacional",
            "local",
            "status_container",
            "data_desembarque",
            "sla_internacional",
            
            "rf_invoice",
            "coleta",
            "liberacao",
            "golden_sat",
            "sla_destino",
        ]
        widgets = {
            "data_envio": forms.DateInput(attrs={"type": "date"}),
            "requisicao": forms.TextInput(attrs={"type": "text"}),
            "id_planilha": forms.TextInput(attrs={"type": "text"}),
            "id2": forms.TextInput(attrs={"type": "text"}),
            "data_insercao": forms.DateInput(attrs={"type": "date"}),
            "data_chegada_destino": forms.DateInput(attrs={"type": "date"}),
            "data_retirada": forms.DateInput(attrs={"type": "date"}),
            "data_envio_brasil": forms.DateInput(attrs={"type": "date"}),  
            "data_brasil": forms.DateInput(attrs={"type": "date"}),
            "data_chegada_porto": forms.DateInput(attrs={"type": "date"}),
            "data_embarque_maritimo": forms.DateInput(attrs={"type": "date"}),
            "data_desembarque_maritimo": forms.DateInput(attrs={"type": "date"}),
            "data_chegada_terminal": forms.DateInput(attrs={"type": "date"}),
            "data_saida_terminal": forms.DateInput(attrs={"type": "date"}),
            "data_desembarque": forms.DateInput(attrs={"type": "date"}),
            "data_envoice": forms.DateInput(attrs={"type": "date"}),
            "ultimo_grid": forms.TextInput(attrs={"type": "text"}),
            "rf_invoice": forms.TextInput(attrs={"type": "text"}),
            "coleta": forms.DateInput(attrs={"type": "date"}),
            "liberacao": forms.DateInput(attrs={"type": "date"}),
            "golden_sat": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        modelo_atual = getattr(self.instance, "modelo", None)
        opcoes = [valor for valor, _label in self.MODELO_CHOICES if valor]
        if modelo_atual and modelo_atual not in opcoes:
            self.fields["modelo"].choices = self.MODELO_CHOICES + [(modelo_atual, f"{modelo_atual} (atual)")]

    def clean(self):
        cleaned_data = super().clean()
        modelo = (cleaned_data.get("modelo") or "").strip()
        id_planilha = (cleaned_data.get("id_planilha") or "").strip()
        id2 = (cleaned_data.get("id2") or "").strip()

        cleaned_data["id_planilha"] = id_planilha
        cleaned_data["id2"] = id2

        if modelo == "Guardian":
            if len(id_planilha) != 12:
                self.add_error("id_planilha", "Para o modelo Guardian, o ID deve ter exatamente 12 caracteres.")
            if not id2:
                self.add_error("id2", "Para o modelo Guardian, o ID 2 é obrigatório.")

        return cleaned_data



class clientesNestleForm(forms.ModelForm):
    class Meta:
        model = clientesNestle
        fields = [
            "cliente",
            "cnpj",
            "endereco", 
            ]       
        widgets = {
            "cnpj": forms.TextInput(attrs={"type": "text"}),
            "endereco": forms.TextInput(attrs={"type": "text"}),
            "quantidade": forms.TextInput(attrs={"type": "text"}),
            "valor": forms.TextInput(attrs={"type": "text"}),
            "local": forms.TextInput(attrs={"type": "text"}),
        }

class ValorMensalForm(forms.ModelForm):
    class Meta:
        model = ValorMensalCliente
        fields = ['valor', 'codigo_rastreio', 'enviado']
        widgets = {
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'codigo_rastreio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código de rastreio'}),
            'enviado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'

class CargaForm(forms.ModelForm):
    class Meta:
        model = Carga
        fields = [
            'data',
            'tipo_transportadora',
            'frete_all_in_valor',
            'frete_all_in_usd',
            'frete_all_in_moeda',
            'frete_all_in_usd_moeda',
            'honorarios',
            'honorarios_moeda',
            'frete_rodoviario',
            'frete_rodoviario_moeda',
            'licenca_importacao',
            'licenca_importacao_moeda',
            'taxa_siscomex',
            'taxa_siscomex_moeda',
            'taxa_armazenagem',
            'taxa_armazenagem_moeda',
            'qtd_equipamento',
            'rf_invoice',
            'data_invoice',
            'origem',
        ]
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'tipo_transportadora': forms.Select(attrs={'class': 'form-select'}),
            'frete_all_in_valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'frete_all_in_usd': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'frete_all_in_moeda': forms.Select(attrs={'class': 'form-select'}),
            'frete_all_in_usd_moeda': forms.Select(attrs={'class': 'form-select'}),
            'honorarios': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'honorarios_moeda': forms.Select(attrs={'class': 'form-select'}),
            'frete_rodoviario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'frete_rodoviario_moeda': forms.Select(attrs={'class': 'form-select'}),
            'licenca_importacao': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'licenca_importacao_moeda': forms.Select(attrs={'class': 'form-select'}),
            'taxa_siscomex': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'taxa_siscomex_moeda': forms.Select(attrs={'class': 'form-select'}),
            'taxa_armazenagem': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'taxa_armazenagem_moeda': forms.Select(attrs={'class': 'form-select'}),
            'qtd_equipamento': forms.NumberInput(attrs={'class': 'form-control'}),
            'rf_invoice': forms.TextInput(attrs={'class': 'form-control'}),
            'data_invoice': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'origem': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Definir valores padrão para campos obrigatórios
        if not self.instance.pk:  # Se é uma nova instância
            self.fields['data'].initial = timezone.now().date()
            self.fields['qtd_equipamento'].initial = 1
        
        # Tornar campos de moeda opcionais
        campos_moeda = [
            'honorarios_moeda',
            'frete_rodoviario_moeda', 
            'licenca_importacao_moeda',
            'taxa_siscomex_moeda',
            'taxa_armazenagem_moeda',
        ]
        
        for campo in campos_moeda:
            if campo in self.fields:
                self.fields[campo].required = False
    

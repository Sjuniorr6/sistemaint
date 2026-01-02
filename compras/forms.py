from django import forms
from .models import CadastroTipoProduto, EntradaProduto, RecebimentoChip

class CadastroTipoProdutoForm(forms.ModelForm):
    """Formulário para cadastro de tipo de produto"""
    
    class Meta:
        model = CadastroTipoProduto
        fields = ['nome_produto', 'descricao', 'fabricante', 'telefone_fabricante', 'email_fabricante', 'valor_unitario']
        widgets = {
            'nome_produto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite o nome do produto'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descreva o produto'}),
            'fabricante': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do fabricante'}),
            'telefone_fabricante': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(11) 99999-9999'}),
            'email_fabricante': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'fabricante@email.com'}),
            'valor_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
        }
        labels = {
            'nome_produto': 'Nome do Produto',
            'descricao': 'Descrição',
            'fabricante': 'Fabricante',
            'telefone_fabricante': 'Telefone do Fabricante',
            'email_fabricante': 'E-mail do Fabricante',
            'valor_unitario': 'Valor Unitário (R$)',
        }

class EntradaProdutoForm(forms.ModelForm):
    """Formulário para entrada de produto"""
    
    class Meta:
        model = EntradaProduto
        fields = ['codigo_produto', 'quantidade', 'id_equipamento', 'data', 'valor_nota', 'numero_nota_fiscal']
        widgets = {
            'codigo_produto': forms.Select(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Quantidade'}),
            'id_equipamento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ID do equipamento'}),
            'data': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'valor_nota': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'numero_nota_fiscal': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° da Nota Fiscal'}),
        }
        labels = {
            'codigo_produto': 'Produto',
            'quantidade': 'Quantidade',
            'id_equipamento': 'ID do Equipamento',
            'data': 'Data e Hora',
            'valor_nota': 'Valor da Nota (R$)',
            'numero_nota_fiscal': 'Número da Nota Fiscal',
        }

class FiltroEntradaProdutoForm(forms.Form):
    """Formulário para filtrar entradas de produto"""
    
    id_equipamento = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filtrar por ID do equipamento...'
        }),
        label='ID do Equipamento'
    )

class RecebimentoChipForm(forms.ModelForm):
    """Formulário para recebimento de chips"""
    
    class Meta:
        model = RecebimentoChip
        fields = [
            'data_solicitacao_compra', 
            'data_chegada_golden', 
            'operadora', 
            'quantidade', 
            'iccid_inicial', 
            'iccid_final', 
            'data_ativacao',
            'data_envio_configuracao',
            'nome_recebedor'
        ]
        widgets = {
            'data_solicitacao_compra': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_chegada_golden': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'operadora': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da operadora'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Quantidade de chips'}),
            'iccid_inicial': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ICCID Inicial'}),
            'iccid_final': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ICCID Final'}),
            'data_ativacao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_envio_configuracao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'nome_recebedor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do recebedor'}),
        }
        labels = {
            'data_solicitacao_compra': 'Data de Solicitação da Compra',
            'data_chegada_golden': 'Data de Chegada na Golden',
            'operadora': 'Operadora',
            'quantidade': 'Quantidade',
            'iccid_inicial': 'ICCID Inicial',
            'iccid_final': 'ICCID Final',
            'data_ativacao': 'Data de Ativação',
            'data_envio_configuracao': 'Data de Envio à Configuração',
            'nome_recebedor': 'Nome do Recebedor',
        }
from django import forms
from .models import Requisicoes, Clientes,estoque_antenista
from datetime import datetime
from franquia.models import registrodefranquia

class RequisicaoForm(forms.ModelForm):
    """Edição da requisição. Modelo, quantidade e customização moram nos itens
    (ItemRequisicao) e são só leitura aqui — o template os exibe de `itens`.
    Valor unitário/total seguem editáveis (ajuste de cobrança)."""

    class Meta:
        model = Requisicoes
        fields = [
            'nome', 'endereco', 'email', 'data_entrega', 'contrato', 'cnpj', 'inicio_de_contrato', 
            'vigencia', 'motivo', 'antenista', 'envio', 'comercial', 'aos_cuidados', 'carregador', 'cabo', 'tipo_fatura', 'valor_unitario', 
            'valor_total', 'forma_pagamento', 'observacoes', 'status', 'TP', 'taxa_envio', 'status_faturamento','id_equipamentos', 'iccid', 'tipo_entrega', 'codigo_rastreio'
        ]
        widgets = {
            'nome': forms.Select(attrs={'class': 'form-control'}),
            'endereco': forms.Textarea(attrs={'class': 'form-control', 'rows': 1}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'numero_de_equipamentos': forms.TextInput(attrs={'class': 'form-control'}),
            'contrato': forms.Select(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'inicio_de_contrato': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'vigencia': forms.Select(attrs={'class': 'form-control'}),
            'data_entrega': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'motivo': forms.Select(attrs={'class': 'form-control'}),
            'antenista': forms.Select(attrs={'class': 'form-control'}),
            'comercial': forms.Select(attrs={'class': 'form-control'}),
            'tipo_produto': forms.Select(attrs={'class': 'form-control'}),
            'envio': forms.Select(attrs={'class': 'form-control'}),
            'taxa_envio': forms.NumberInput(attrs={'class': 'form-control'}),
            'carregador': forms.TextInput(attrs={'class': 'form-control'}),
            'cabo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_customizacao': forms.Select(attrs={'class': 'form-control'}),
            'tipo_fatura': forms.Select(attrs={'class': 'form-control'}),
            'valor_unitario': forms.NumberInput(attrs={'class': 'form-control'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control'}),
            'forma_pagamento': forms.TextInput(attrs={'class': 'form-control'}),
            'aos_cuidados': forms.TextInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'TP': forms.Select(attrs={'class': 'form-control'}),
            'status_faturamento': forms.Select(attrs={'class': 'form-control'}),
            'id_equipamentos': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Cole os IDs dos equipamentos separados por espaços'}),    
            'iccid': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Cole os ICCIDs separados por espaços'}),
            'tipo_entrega': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_rastreio': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        editable_fields = kwargs.pop('editable_fields', None)
        editar_itens = kwargs.pop('editar_itens', False)
        super().__init__(*args, **kwargs)

        self.fields['nome'].queryset = Clientes.objects.all()
        self.fields['nome'].empty_label = "Selecione um cliente"

        # Edição (requisicao_update): quantidade editável por modelo. O valor
        # total passa a ser a soma dos modelos, então os campos de valor soltos
        # saem — editados à mão seriam sobrescritos ao salvar.
        self.itens_editaveis = []
        if editar_itens and self.instance.pk:
            self.fields.pop('valor_unitario', None)
            self.fields.pop('valor_total', None)
            for item in self.instance.itens.select_related('tipo_produto'):
                nome = f'quantidade_{item.pk}'
                self.fields[nome] = forms.IntegerField(
                    min_value=1,
                    initial=item.quantidade,
                    label=f'Quantidade — {item.tipo_produto}',
                    widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
                )
                self.itens_editaveis.append((item, nome))

        if editable_fields:
            for field_name in self.fields:
                if field_name not in editable_fields:
                    self.fields[field_name].widget.attrs['readonly'] = 'readonly'

    def linhas_quantidade(self):
        """[(item, BoundField da quantidade)] para o template da edição."""
        return [(item, self[nome]) for item, nome in self.itens_editaveis]

    def campos_de_quantidade(self):
        return [nome for _, nome in self.itens_editaveis]

    def quantidades(self):
        """{pk do item: quantidade} do cleaned_data (após is_valid)."""
        return {item.pk: self.cleaned_data[nome] for item, nome in self.itens_editaveis}


class requisicaoFormup(forms.ModelForm):
    """Edição pela Configuração/Setor técnico. Itens só leitura (ver RequisicaoForm)."""

    class Meta:
        model = Requisicoes
        fields = ['nome', 'endereco', 'email', 'contrato', 'cnpj', 'inicio_de_contrato', 'vigencia', 
                  'motivo', 'envio', 'comercial', 'carregador', 'cabo', 'tipo_fatura', 'valor_unitario', 'valor_total',
                  'forma_pagamento','observacoes', 'status', 'TP', 'taxa_envio','id_equipamentos', 'iccid', 'tipo_entrega', 'codigo_rastreio']
        widgets = {
            'nome': forms.Select(attrs={'class': 'form-control'}),
            'endereco': forms.Textarea(attrs={'class': 'form-control', 'rows': 1}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'numero_de_equipamentos': forms.Textarea(attrs={'class': 'form-control', 'rows': 1}),
            'contrato': forms.Select(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'inicio_de_contrato': forms.DateInput(attrs={'class': 'form-control'}),
            'vigencia': forms.Select(attrs={'class': 'form-control'}),
            
            'motivo': forms.Select(attrs={'class': 'form-control'}),
            'comercial': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_produto': forms.Select(attrs={'class': 'form-control'}),
            'envio': forms.Select(attrs={'class': 'form-control'}),
            'taxa_envio': forms.NumberInput(attrs={'class': 'form-control'}),
            'carregador': forms.TextInput(attrs={'class': 'form-control'}),
            'cabo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_customizacao': forms.Select(attrs={'class': 'form-control'}),
            'tipo_fatura': forms.Select(attrs={'class': 'form-control'}),
            'valor_unitario': forms.NumberInput(attrs={'class': 'form-control'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control'}),
            'forma_pagamento': forms.TextInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'TP': forms.Select(attrs={'class': 'form-control'}),
            'id_equipamentos': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Cole os IDs dos equipamentos separados por espaços'}),
            'iccid': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Cole os ICCIDs separados por espaços'}),
            'tipo_entrega': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_rastreio': forms.TextInput(attrs={'class': 'form-control'}),
        }
        permissions = [
            ("view_requisicoes", "Can view requisicoes"),
            ("add_requisicoes", "Can add requisicoes"),
            ("change_requisicoes", "Can change requisicoes"),
            ("delete_requisicoes", "Can delete requisicoes"),
        ]

    def __init__(self, *args, **kwargs):
        editable_fields = kwargs.pop('editable_fields', None)
        super().__init__(*args, **kwargs)
        self.fields['nome'].queryset = Clientes.objects.all()
        self.fields['nome'].empty_label = "Selecione um cliente"

        if editable_fields:
            for field_name in self.fields:
                if field_name not in editable_fields:
                    self.fields[field_name].widget.attrs['readonly'] = 'readonly'


from django import forms
from django.core.exceptions import ValidationError
from .models import Requisicoes, Clientes, estoque_antenista

class RequisicoesForm(forms.ModelForm):
    class Meta:
        model = Requisicoes
        fields = '__all__'
        widgets = {
            'nome': forms.Select(attrs={'class': 'form-control'}),
            'motivo': forms.Select(attrs={'class': 'form-control', 'onchange': 'toggleAntenistaField()'}),
            'antenista': forms.Select(attrs={'class': 'form-control', 'style': 'display:none;', 'id': 'antenista-field'}),
            'tipo_produto': forms.Select(attrs={'class': 'form-control'}),
            'numero_de_equipamentos': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_equipamentos': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Cole os IDs dos equipamentos separados por espaços'}),
            'endereco': forms.Textarea(attrs={'class': 'form-control', 'rows': 1}),
            'contrato': forms.Select(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'inicio_de_contrato': forms.DateInput(attrs={'class': 'form-control'}),
            'vigencia': forms.Select(attrs={'class': 'form-control'}),
            'comercial': forms.TextInput(attrs={'class': 'form-control'}),
            'envio': forms.Select(attrs={'class': 'form-control'}),
            'taxa_envio': forms.NumberInput(attrs={'class': 'form-control'}),
            'carregador': forms.TextInput(attrs={'class': 'form-control'}),
            'cabo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_customizacao': forms.Select(attrs={'class': 'form-control'}),
            'tipo_fatura': forms.Select(attrs={'class': 'form-control'}),
            'valor_unitario': forms.NumberInput(attrs={'class': 'form-control'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control'}),
            'forma_pagamento': forms.TextInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.TextInput(attrs={'class': 'form-control'}),
            'TP': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nome'].queryset = Clientes.objects.all()
        self.fields['antenista'].widget = forms.Select(choices=[
            
            ('ALCIDES', 'ALCIDES'),
            ('EZEQUIEL', 'EZEQUIEL'),
            ('NILDO', 'NILDO'),
            ('ALEX', 'ALEX'),
            ('ANDERSON', 'ANDERSON'),
            ('ANTONIEQUE', 'ANTONIEQUE'),
            ('OSNI', 'OSNI'),
            ('ELTON', 'ELTON'),
            ('NEY', 'NEY'),
            ('ANDRÉ', 'ANDRÉ'),
            ('RILDO', 'RILDO'),
            ('WELLINGTHON', 'WELLINGTHON'),
            ('GERSON WALACE', 'GERSON WALACE'),
            ('JUSTINO', 'JUSTINO'),
            ('ANTONIO', 'ANTONIO'),
            ('FRANCISCO', 'FRANCISCO'),
            ('OSMAN', 'OSMAN'),
            ('TONHARA', 'TONHARA'),
            ('EMERSON', 'EMERSON'),
            ('MARCELO', 'MARCELO'),
            ('JEFFERSON', 'JEFFERSON'),
            ('GUILHERME', 'GUILHERME'),
            ('MARCIO', 'MARCIO'),
            ('SAMPAIO', 'SAMPAIO'),
            ('DIOGO', 'DIOGO'),
            ('WESLEY', 'WESLEY'),
            ('EVERALDO / SAMUEL', 'EVERALDO / SAMUEL'),
            ('ERIK', 'ERIK'),
            ('LUCAS CARVALHO', 'LUCAS CARVALHO'),
            ('RODRIGO', 'RODRIGO'),
            ('PITTA', 'PITTA'),
            ('JUSTO', 'JUSTO'),
            ('PAULO HENRIQUE', 'PAULO HENRIQUE'),
            ('EDUARDO', 'EDUARDO'),
            ('YURI', 'YURI'),
            ('RAFAEL', 'RAFAEL'),
        ], attrs={'class': 'form-control'})
        self.fields['antenista'].required = True
        self.fields['id_equipamentos'] = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Cole os IDs dos equipamentos separados por espaços'}))

    def clean(self):
        cleaned_data = super().clean()
        motivo = cleaned_data.get('motivo')
        antenista = cleaned_data.get('antenista')
        tipo_produto = cleaned_data.get('tipo_produto')
        numero_de_equipamentos = cleaned_data.get('numero_de_equipamentos')

        if motivo == 'Isca FAST' and antenista and tipo_produto and numero_de_equipamentos:
            try:
                antenista_estoque = estoque_antenista.objects.get(nome=antenista, tipo_produto=tipo_produto)
                quantidade_requisitada = int(numero_de_equipamentos)
                if antenista_estoque.quantidade < quantidade_requisitada:
                    raise ValidationError(f"O antenista {antenista} não tem quantidade suficiente no estoque para o produto {tipo_produto}. Quantidade disponível: {antenista_estoque.quantidade}, quantidade requisitada: {quantidade_requisitada}.")
            except estoque_antenista.DoesNotExist:
                raise ValidationError(f"O antenista {antenista} ou o produto {tipo_produto} não existem no estoque.")

        return cleaned_data

class EstoqueantenistarForm(forms.ModelForm):
    class Meta:
        model = estoque_antenista
        fields = ['nome', 'tipo_produto', 'quantidade', 'endereco']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nome'].widget.attrs.update({'class': 'form-control'})
        self.fields['tipo_produto'].widget.attrs.update({'class': 'form-control'})
        self.fields['quantidade'].widget.attrs.update({'class': 'form-control'})
        self.fields['endereco'].widget.attrs.update({'class': 'form-control'})


# models.py
# forms.py
from django import forms
from .models import ControleModel

class ControleForm(forms.ModelForm):
    class Meta:
        model = ControleModel
        fields = ['cliente', 'requisicao_id', 'quantidade' ,'iccid_equipamento1', 'id_equipamento1', 'iccid_equipamento2', 'id_equipamento2',
                  'iccid_equipamento3', 'id_equipamento3', 'iccid_equipamento4', 'id_equipamento4', 'iccid_equipamento5',
                  'id_equipamento5', 'iccid_equipamento6', 'id_equipamento6', 'iccid_equipamento7', 'id_equipamento7',
                  'iccid_equipamento8', 'id_equipamento8', 'iccid_equipamento9', 'id_equipamento9', 'iccid_equipamento10',
                  'id_equipamento10']
        widgets = {
            'cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'requisicao_id': forms.TextInput(attrs={'class': 'form-control'}),
            'quantidade': forms.TextInput(attrs={'class': 'form-control'}),
            'iccid_equipamento1': forms.TextInput(attrs={'class': 'form-control'}),
            'id_equipamento1': forms.TextInput(attrs={'class': 'form-control'}),
            'iccid_equipamento2': forms.TextInput(attrs={'class': 'form-control'}),
            'id_equipamento2': forms.TextInput(attrs={'class': 'form-control'}),
            'iccid_equipamento3': forms.TextInput(attrs={'class': 'form-control'}),
            'id_equipamento3': forms.TextInput(attrs={'class': 'form-control'}),
            'iccid_equipamento4': forms.TextInput(attrs={'class': 'form-control'}),
            'id_equipamento4': forms.TextInput(attrs={'class': 'form-control'}),
            'iccid_equipamento5': forms.TextInput(attrs={'class': 'form-control'}),
            'id_equipamento5': forms.TextInput(attrs={'class': 'form-control'}),
            'iccid_equipamento6': forms.TextInput(attrs={'class': 'form-control'}),
            'id_equipamento6': forms.TextInput(attrs={'class': 'form-control'}),
            'iccid_equipamento7': forms.TextInput(attrs={'class': 'form-control'}),
            'id_equipamento7': forms.TextInput(attrs={'class': 'form-control'}),
            'iccid_equipamento8': forms.TextInput(attrs={'class': 'form-control'}),
            'id_equipamento8': forms.TextInput(attrs={'class': 'form-control'}),
            'iccid_equipamento9': forms.TextInput(attrs={'class': 'form-control'}),
            'id_equipamento9': forms.TextInput(attrs={'class': 'form-control'}),
            'iccid_equipamento10': forms.TextInput(attrs={'class': 'form-control'}),
            'id_equipamento10': forms.TextInput(attrs={'class': 'form-control'}),
        }



from .models import antenista_CARD
class antenista_Form(forms.ModelForm):
    class Meta:
        model = antenista_CARD  # Substitua pelo nome do seu modelo
        fields = ['nome', 'tipo_produto', 'solicitante','telefone', 'cliente', 'quantidade','equipamentos','contrato','valor_total', 'valor_prestador', 'valor_isca', 'valor_cliente', 'lucro']
        widgets = {
            'nome': forms.Select(attrs={'class': 'form-control'}),
            'tipo_produto': forms.Select(attrs={'class': 'form-control'}),
            'solicitante': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Solicitante'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite o telefone'}),
            'equipamentos': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'IDS'}),
            'cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Digite a quantidade'}),
            'contrato': forms.Select(attrs={'class': 'form-control'}),
            'valor_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'}),
            'valor_prestador': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'valor_isca': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'valor_cliente': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'lucro': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use a ModelChoiceField so 'cliente' is a dropdown populated from the Clientes model
        self.fields['cliente'] = forms.ModelChoiceField(
            queryset=Clientes.objects.all(),
            empty_label="Selecione um cliente",
            widget=forms.Select(attrs={'class': 'form-control'})
        )


# Formulário para cadastro do modelo Antenista (nome + estado)
from .models import Antenista

class AntenistaForm(forms.ModelForm):
    class Meta:
        model = Antenista
        fields = ['nome', 'estado']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.TextInput(attrs={'class': 'form-control'}),
        }


from decimal import Decimal, InvalidOperation

from produto.models import Produto


class ItensRequisicaoWidget(forms.Widget):
    """Lê os blocos "modelo" da requisição.

    A tela renderiza um bloco por modelo: `item` (id do bloco, repetido) e
    `item_<id>_tipo_produto`, `_quantidade`, `_customizacao`, `_valor_unitario`,
    `_numeros`. Devolve dicts crus; bloco totalmente vazio é descartado.
    """

    CAMPOS = ("tipo_produto", "quantidade", "customizacao", "valor_unitario", "numeros")

    def value_from_datadict(self, data, files, name):
        ids = data.getlist("item") if hasattr(data, "getlist") else (data.get("item") or [])
        blocos = []
        for bid in dict.fromkeys(ids):  # ordem da tela, sem repetir
            bloco = {c: str(data.get(f"item_{bid}_{c}") or "").strip() for c in self.CAMPOS}
            if any(bloco.values()):
                blocos.append(bloco)
        return blocos


class ItensRequisicaoField(forms.Field):
    """Modelos da requisição. Sai uma lista de ItemRequisicao NÃO salvos."""

    widget = ItensRequisicaoWidget

    def clean(self, value):
        from requisicao.models import ItemRequisicao

        blocos = value or []
        if not blocos:
            raise forms.ValidationError("Informe ao menos um modelo de equipamento.")
        customizacoes = {v for v, _ in Requisicoes.customizacoes}
        ids = {b["tipo_produto"] for b in blocos if b["tipo_produto"].isdigit()}
        produtos = {str(p.pk): p for p in Produto.objects.filter(pk__in=ids)}

        erros, itens = [], []
        for n, b in enumerate(blocos, start=1):
            rotulo = f"Modelo {n}"
            produto = produtos.get(b["tipo_produto"])
            if not b["tipo_produto"]:
                erros.append(f"{rotulo}: selecione o tipo de produto.")
            elif produto is None:
                erros.append(f"{rotulo}: tipo de produto inválido.")
            quantidade = int(b["quantidade"]) if b["quantidade"].isdigit() else 0
            if quantidade < 1:
                erros.append(f"{rotulo}: informe a quantidade (número inteiro maior que zero).")
            if b["customizacao"] and b["customizacao"] not in customizacoes:
                erros.append(f"{rotulo}: customização inválida.")
            try:
                valor = Decimal(b["valor_unitario"].replace(",", ".") or "0")
                if valor < 0:
                    raise InvalidOperation
            except InvalidOperation:
                erros.append(f"{rotulo}: valor unitário inválido.")
                valor = Decimal("0")
            itens.append(ItemRequisicao(
                tipo_produto=produto,
                quantidade=quantidade,
                customizacao=b["customizacao"],
                valor_unitario=valor,
                numeros_referencia=b["numeros"],
            ))
        if erros:
            raise forms.ValidationError(erros)
        return itens


class RequisicaoCreateForm(RequisicaoForm):
    """Criação da requisição: dados do cliente/contrato/envio + um bloco por modelo."""

    itens = ItensRequisicaoField(label="Modelos")

    class Meta(RequisicaoForm.Meta):
        # valor_unitario/valor_total são derivados dos itens na criação.
        fields = [f for f in RequisicaoForm.Meta.fields if f not in ("valor_unitario", "valor_total")]

    def __init__(self, *args, itens_iniciais=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.itens_iniciais = itens_iniciais or []

    def blocos_itens(self):
        """Blocos para o template: o postado (reexibição com erro), os iniciais
        (ex.: vindos de um chamado) ou um bloco vazio."""
        blocos = self["itens"].value() if self.is_bound else self.itens_iniciais
        vazio = {c: "" for c in ItensRequisicaoWidget.CAMPOS}
        return [{**vazio, **b} for b in blocos] or [vazio]

    def opcoes_itens(self):
        return {
            "produtos": Produto.objects.order_by("nome"),
            "customizacoes": Requisicoes.customizacoes,
        }

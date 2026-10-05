from django import forms
from registrodemanutencao.models import registrodemanutencao, ImagemRegistro
from cliente.models import Cliente
from produto.models import Produto
from.models import retorno
from django.conf import settings
import os

import re

from registrodemanutencao.models import ItemEntrada


def separar_numeros(texto):
    """Nºs de equipamento de um texto colado/bipado: separa por espaço, quebra
    de linha, vírgula ou ponto e vírgula (mesmo critério do PDF de protocolo)."""
    return [n for n in re.split(r"[\s,;]+", texto or "") if n]


class ItensEntradaWidget(forms.Widget):
    """Lê os blocos "tipo de produto" da entrada.

    A tela renderiza um bloco por tipo de produto: `item` (id do bloco, repetido)
    e `item_<id>_tipo_produto`, `item_<id>_numero`, `item_<id>_customizacao`,
    `item_<id>_tipo_contrato`. Devolve uma lista de dicts crus; bloco totalmente
    vazio é descartado.
    """

    CAMPOS = ("tipo_produto", "numero", "customizacao", "tipo_contrato")

    def value_from_datadict(self, data, files, name):
        ids = data.getlist("item") if hasattr(data, "getlist") else (data.get("item") or [])
        blocos = []
        for bid in dict.fromkeys(ids):  # ordem da tela, sem repetir
            bloco = {
                campo: str(data.get(f"item_{bid}_{campo}") or "").strip()
                for campo in self.CAMPOS
            }
            if any(bloco.values()):
                blocos.append(bloco)
        return blocos


class ItensEntradaField(forms.Field):
    """Tipos de produto da entrada. Sai uma lista de ItemEntrada NÃO salvos."""

    widget = ItensEntradaWidget

    def clean(self, value):
        blocos = value or []
        if not blocos:
            raise forms.ValidationError("Informe ao menos um tipo de produto.")
        customizacoes = {v for v, _ in registrodemanutencao.custom}
        contratos = {v for v, _ in registrodemanutencao.contrato_tipo}
        # Uma query só para todos os produtos (sem lookup por bloco).
        ids = {b["tipo_produto"] for b in blocos if b["tipo_produto"].isdigit()}
        produtos = {str(p.pk): p for p in Produto.objects.filter(pk__in=ids)}

        erros, itens, vistos = [], [], set()
        for n, bloco in enumerate(blocos, start=1):
            rotulo = f"Produto {n}"
            produto = produtos.get(bloco["tipo_produto"])
            if not bloco["tipo_produto"]:
                erros.append(f"{rotulo}: selecione o tipo de produto.")
            elif produto is None:
                erros.append(f"{rotulo}: tipo de produto inválido.")
            numeros = separar_numeros(bloco["numero"])
            if not numeros:
                erros.append(f"{rotulo}: informe os nºs dos equipamentos.")
            repetidos = sorted({x for x in numeros if x in vistos or numeros.count(x) > 1})
            if repetidos:
                erros.append(f"{rotulo}: nº repetido na entrada ({', '.join(repetidos)}).")
            vistos.update(numeros)
            if bloco["customizacao"] and bloco["customizacao"] not in customizacoes:
                erros.append(f"{rotulo}: customização inválida.")
            if bloco["tipo_contrato"] and bloco["tipo_contrato"] not in contratos:
                erros.append(f"{rotulo}: tipo de contrato inválido.")
            itens.append(ItemEntrada(
                tipo_produto=produto,
                numero_equipamento=" ".join(numeros),
                customizacao=bloco["customizacao"],
                tipo_contrato=bloco["tipo_contrato"],
                quantidade=len(numeros),
            ))
        if erros:
            raise forms.ValidationError(erros)
        return itens


class FormulariosForm(forms.ModelForm):
    """Entrada de equipamento: dados da entrega + um bloco por tipo de produto.

    Tipo de produto, nºs, customização e contrato moram nos itens; a quantidade
    é a contagem dos nºs de cada item (total calculado no service).
    """

    itens = ItensEntradaField(label="Tipos de produto")

    class Meta:
        model = registrodemanutencao
        fields = [
            'nome', 'tipo_entrada', 'entregue_por_retirado_por', 'observacoes', 'status',
        ]
        widgets = {
            'nome': forms.Select(attrs={'class': 'form-control'}),
            'tipo_entrada': forms.Select(attrs={'class': 'form-control'}),
            'entregue_por_retirado_por': forms.Select(attrs={'class': 'form-control'}),
            'observacoes': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }

    def __init__(self, *args, itens_iniciais=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.itens_iniciais = itens_iniciais or []

    def blocos_itens(self):
        """Blocos para o template: o que foi postado (ao reexibir com erro), os
        iniciais (ex.: vindos do chamado) ou um bloco vazio."""
        if self.is_bound:
            blocos = self["itens"].value()
        else:
            blocos = self.itens_iniciais
        vazio = {"tipo_produto": "", "numero": "", "customizacao": "", "tipo_contrato": ""}
        return [{**vazio, **b} for b in blocos] or [vazio]

    def opcoes_itens(self):
        """Opções dos selects de cada bloco (o template repete por bloco)."""
        return {
            "produtos": Produto.objects.order_by("nome"),
            "customizacoes": [c for c in registrodemanutencao.custom if c[0]],
            "contratos": registrodemanutencao.contrato_tipo,
        }


# registrodemanutencao/forms.py

class FormulariosUpdateForm(forms.ModelForm):
    """Edição da entrada (laboratório/configuração). Tipo de produto, nºs,
    customização, contrato e quantidade moram nos itens (ItemEntrada) e são só
    leitura aqui — o template os exibe a partir de `object.itens`."""

    class Meta:
        model = registrodemanutencao
        fields = [
            'nome',
            'data_devolucao',
            'tipo_entrada',
            'tratativa',
            'status',
            'tipo_customizacao',
            'recebimento',
            'entregue_por_retirado_por',
            'motivo',
            'observacoes',
        ]
        widgets = {
            'nome': forms.Select(attrs={'class': 'form-control'}),
            'tipo_entrada': forms.Select(attrs={'class': 'form-control'}),
            'tratativa': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_customizacao': forms.Select(attrs={'class': 'form-control'}),
            'recebimento': forms.Select(attrs={'class': 'form-control'}),
            'entregue_por_retirado_por': forms.Select(attrs={'class': 'form-control'}),
            'motivo': forms.Select(attrs={'class': 'form-control'}),
            'data_devolucao': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly',
                'type': 'text',
            }),
            'observacoes': forms.TextInput(attrs={'class': 'form-control'}),
        }

from django.forms import BaseInlineFormSet, inlineformset_factory


def equipamentos_da_entrada(registro):
    """[(nº, rótulo "nº — produto")] dos itens da entrada, na ordem, sem repetir."""
    if registro is None or registro.pk is None:
        return []
    opcoes = {}
    for item in registro.itens.select_related('tipo_produto'):
        for numero in separar_numeros(item.numero_equipamento):
            opcoes.setdefault(numero, f"{numero} — {item.tipo_produto or 'sem produto'}")
    return list(opcoes.items())


class ImagemRegistroBaseFormSet(BaseInlineFormSet):
    """Laudo por equipamento: o ID do equipamento é escolhido entre os nºs
    registrados na própria entrada (itens), não digitado.

    Entrada antiga sem nºs nos itens mantém o campo de texto livre. Um valor já
    salvo que não está na lista (digitado antes do select) continua como opção,
    para a edição não apagá-lo.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Os forms do formset são criados sob demanda, depois deste __init__:
        # add_fields (abaixo) já enxerga a lista.
        self.equipamentos = equipamentos_da_entrada(self.instance)

    def clean(self):
        """Um mesmo equipamento não pode ter duas linhas de laudo."""
        super().clean()
        vistos = set()
        for form in self.forms:
            if not hasattr(form, 'cleaned_data') or self._should_delete_form(form):
                continue
            numero = (form.cleaned_data.get('id_equipamento') or '').strip()
            if not numero:
                continue
            if numero in vistos:
                form.add_error('id_equipamento', f"Equipamento {numero} já escolhido em outra linha.")
            vistos.add(numero)

    def add_fields(self, form, index):
        super().add_fields(form, index)
        equipamentos = getattr(self, 'equipamentos', None)
        if not equipamentos:
            return
        opcoes = [('', 'Selecione o equipamento')] + list(equipamentos)
        atual = (form.initial.get('id_equipamento') or '').strip()
        if atual and atual not in dict(equipamentos):
            opcoes.append((atual, f"{atual} (fora da entrada)"))
        # ChoiceField recusa no servidor nº fora da lista (não só na tela).
        form.fields['id_equipamento'] = forms.ChoiceField(
            choices=opcoes,
            required=False,
            label='ID do Equipamento',
            widget=forms.Select(attrs={'class': 'form-control'}),
        )


def formset_imagens(extra=1):
    """Formset do laudo por equipamento com `extra` linhas novas (o laudo vindo
    do chamado abre com uma linha por equipamento ainda sem laudo)."""
    return inlineformset_factory(
        registrodemanutencao,
        ImagemRegistro,
        formset=ImagemRegistroBaseFormSet,
        fields=('id_equipamento', 'imagem', 'imagem2', 'tipo_problema', 'faturamento', 'observacao2'),
        extra=extra,
        can_delete=True,
        widgets=_WIDGETS_IMAGEM,
    )


_WIDGETS_IMAGEM = {
    'imagem': forms.ClearableFileInput(attrs={'class': 'form-control'}),
    'imagem2': forms.ClearableFileInput(attrs={'class': 'form-control'}),
    'id_equipamento': forms.TextInput(attrs={'class': 'form-control', 'rows': 3}),
    'observacao2': forms.TextInput(attrs={'class': 'form-control', 'rows': 3}),
    'faturamento': forms.Select(attrs={'class': 'form-control', 'rows': 3}),
    'tipo_problema': forms.Select(attrs={'class': 'form-control', 'rows': 1}),
}

ImagemRegistroFormSet = inlineformset_factory(
    registrodemanutencao,
    ImagemRegistro,
    formset=ImagemRegistroBaseFormSet,
    fields=('id_equipamento','imagem', 'imagem2','tipo_problema','faturamento','observacao2'),
    extra=1,
    can_delete=True,
    widgets={
        'imagem': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        'imagem2': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        'id_equipamento': forms.TextInput(attrs={'class': 'form-control', 'rows': 3}),
        'observacao2': forms.TextInput(attrs={'class': 'form-control', 'rows': 3}),
        'faturamento': forms.Select(attrs={'class': 'form-control', 'rows': 3}),
        'tipo_problema': forms.Select(attrs={'class': 'form-control', 'rows': 1}),
    }
)

class RetornoForm(forms.ModelForm):
    class Meta:
        model = retorno
        fields = [
            'cliente', 'produto', 'tipo_problema','id_equipamentos','imagem'
        ]
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-control'}),
            'id_equipamentos': forms.Textarea(attrs={'class': 'form-control'}),
            'produto': forms.Select(attrs={'class': 'form-control'}),
            'tipo_problema': forms.Select(attrs={'class': 'form-control'}),
            'imagem': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }









"""Forms de movimentação de estoque: entrada, transferência, baixa, retorno."""
from django import forms

from iscas.enums import MotivoBaixa, TipoModelo
from iscas.models.cadastro import Agente, Deposito, ModeloEquipamento
from iscas.services.entrada import parse_identificadores


class EntradaLoteForm(forms.Form):
    """Entrada de unidades novas (ISC-RF-07, ISC-RF-08).

    O operador informa os identificadores de fábrica das iscas, um por linha.
    A geração automática por faixa sequencial existiu aqui e foi removida a
    pedido: na operação real o identificador vem impresso no equipamento, e
    oferecer três modos de preenchimento só fazia o operador escolher entre
    caminhos que ele nunca usava.
    """

    DESTINO_DEPOSITO = "DEPOSITO"
    DESTINO_AGENTE = "AGENTE"
    TIPOS_DESTINO = [
        (DESTINO_DEPOSITO, "Depósito"),
        (DESTINO_AGENTE, "Agente"),
    ]

    modelo = forms.ModelChoiceField(
        queryset=ModeloEquipamento.objects.all(),
        label="Modelo",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    identificadores = forms.CharField(
        label="Identificadores (um por linha)",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 8,
                "placeholder": "Cole aqui os IDs das iscas, um por linha.",
            }
        ),
        help_text="Um identificador por linha, exatamente como vem no equipamento.",
    )
    # O tipo governa qual dos dois selects a tela mostra — evita o formulário
    # com dois campos de destino em que só um pode ser preenchido.
    tipo_destino = forms.ChoiceField(
        choices=TIPOS_DESTINO,
        initial=DESTINO_DEPOSITO,
        label="Destino",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    destino_deposito = forms.ModelChoiceField(
        queryset=Deposito.objects.all(), required=False, label="Depósito",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    destino_agente = forms.ModelChoiceField(
        queryset=Agente.objects.all(), required=False, label="Agente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    nota_fiscal = forms.CharField(
        required=False, max_length=50, label="Nota fiscal",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    lote = forms.CharField(
        required=False, max_length=50, label="Lote",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    ocorrido_em = forms.DateTimeField(
        required=False, label="Ocorrido em",
        widget=forms.DateTimeInput(
            attrs={"class": "form-control", "type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        help_text="Deixe em branco para usar o momento atual.",
    )

    def clean(self):
        dados = super().clean()

        # Valida o destino conforme o tipo escolhido; o campo do outro tipo é
        # ignorado, porque a tela nem o exibe.
        tipo = dados.get("tipo_destino")
        if tipo == self.DESTINO_AGENTE:
            destino = dados.get("destino_agente")
            if not destino:
                raise forms.ValidationError({"destino_agente": "Escolha o agente."})
        else:
            destino = dados.get("destino_deposito")
            if not destino:
                raise forms.ValidationError({"destino_deposito": "Escolha o depósito."})
        dados["destino"] = destino

        identificadores = parse_identificadores(dados.get("identificadores", ""))
        if not identificadores:
            raise forms.ValidationError(
                {"identificadores": "Informe ao menos um identificador."}
            )
        dados["lista_identificadores"] = identificadores
        # Mantido para a assinatura do service, que ainda suporta geração
        # interna por outros caminhos (ISC-RF-09).
        dados["gerar_internos"] = False
        dados["quantidade"] = len(identificadores)

        return dados


class _OrigemCustodiaMixin(forms.Form):
    """Seletor de tipo de origem + os dois selects condicionais.

    A tela mostra só o select do tipo escolhido. Antes eram dois campos
    visíveis em que apenas um podia ser preenchido, o que confundia e produzia
    erro de validação em vez de guiar.
    """

    ORIGEM_DEPOSITO = "DEPOSITO"
    ORIGEM_AGENTE = "AGENTE"
    TIPOS_ORIGEM = [
        (ORIGEM_DEPOSITO, "Depósito"),
        (ORIGEM_AGENTE, "Agente"),
    ]

    tipo_origem = forms.ChoiceField(
        choices=TIPOS_ORIGEM,
        initial=ORIGEM_DEPOSITO,
        label="Onde está o equipamento",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    origem_deposito = forms.ModelChoiceField(
        queryset=Deposito.objects.all(), required=False, label="Depósito",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    origem_agente = forms.ModelChoiceField(
        queryset=Agente.objects.all(), required=False, label="Agente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def resolver_origem(self, dados):
        """Devolve a entidade de origem conforme o tipo, ou levanta erro."""
        if dados.get("tipo_origem") == self.ORIGEM_AGENTE:
            origem = dados.get("origem_agente")
            if not origem:
                raise forms.ValidationError({"origem_agente": "Escolha o agente."})
        else:
            origem = dados.get("origem_deposito")
            if not origem:
                raise forms.ValidationError({"origem_deposito": "Escolha o depósito."})
        return origem

    def normalizar_ids(self, campo="unidades"):
        """IDs do select múltiplo, nas três formas em que os dados chegam.

        Lê de `self.data` porque um `CharField` guardaria só o último valor.
        Trata `QueryDict` (POST real), lista (form instanciado com dict em
        código ou teste) e string única.
        """
        bruto = (
            self.data.getlist(campo)
            if hasattr(self.data, "getlist")
            else self.data.get(campo)
        )
        if bruto is None:
            bruto = []
        elif isinstance(bruto, (str, int)):
            bruto = [bruto]
        return [str(i).strip() for i in bruto if str(i).strip()]

    def resolver_unidades(self, origem, ids):
        """Confere que as unidades estão na origem e sem reserva ativa.

        O service recusaria de qualquer forma; aqui a mensagem é específica e
        cobre a corrida entre abrir a tela e enviar o formulário.
        """
        from iscas.services.saldo import unidades_disponiveis

        encontradas = list(unidades_disponiveis(origem).filter(pk__in=ids))
        if len(encontradas) != len(set(ids)):
            raise forms.ValidationError(
                {
                    "unidades": (
                        "Alguma unidade selecionada não está mais disponível "
                        f"em {origem} — pode ter sido reservada ou movimentada. "
                        "Recarregue a página e selecione novamente."
                    )
                }
            )
        return encontradas


class TransferenciaForm(_OrigemCustodiaMixin):
    """Transferência entre custódias internas (ISC-RF-11).

    Dois seletores de tipo — origem e destino — cada um revelando o select
    correspondente, e as unidades vêm da ORIGEM: é de lá que elas saem.

    Diferente da baixa e da manutenção, aqui a seleção unitária não é
    imprescindível (abastecer um agente com 10 iscas iguais raramente exige
    escolher quais). Mas dá controle quando importa: mandar exatamente as que
    estão há mais tempo paradas, ou separar as de um lote específico.
    """

    DESTINO_DEPOSITO = "DEPOSITO"
    DESTINO_AGENTE = "AGENTE"

    tipo_origem = forms.ChoiceField(
        choices=_OrigemCustodiaMixin.TIPOS_ORIGEM,
        initial=_OrigemCustodiaMixin.ORIGEM_DEPOSITO,
        label="Sai de",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    # Default AGENTE: o caminho mais comum é abastecer quem está em campo.
    tipo_destino = forms.ChoiceField(
        choices=_OrigemCustodiaMixin.TIPOS_ORIGEM,
        initial=_OrigemCustodiaMixin.ORIGEM_AGENTE,
        label="Vai para",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    destino_deposito = forms.ModelChoiceField(
        queryset=Deposito.objects.all(), required=False, label="Depósito",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    destino_agente = forms.ModelChoiceField(
        queryset=Agente.objects.all(), required=False, label="Agente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    unidades = forms.CharField(
        label="Unidades a transferir",
        widget=forms.SelectMultiple(
            attrs={"class": "form-select", "id": "id_unidades"}
        ),
        help_text="Busque pelo identificador da isca ou pelo modelo.",
    )
    justificativa = forms.CharField(
        required=False,
        label="Observação",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Motivo da transferência, se valer registrar.",
            }
        ),
    )

    def clean_unidades(self):
        ids = self.normalizar_ids()
        if not ids:
            raise forms.ValidationError("Selecione ao menos uma unidade.")
        return ids

    def _resolver_destino(self, dados):
        if dados.get("tipo_destino") == self.DESTINO_AGENTE:
            destino = dados.get("destino_agente")
            if not destino:
                raise forms.ValidationError({"destino_agente": "Escolha o agente."})
        else:
            destino = dados.get("destino_deposito")
            if not destino:
                raise forms.ValidationError({"destino_deposito": "Escolha o depósito."})
        return destino

    def clean(self):
        dados = super().clean()
        origem = self.resolver_origem(dados)
        destino = self._resolver_destino(dados)

        # Mesma entidade dos dois lados: o lançamento não faria nada, e o
        # service recusaria com erro genérico.
        if type(origem) is type(destino) and origem.pk == destino.pk:
            raise forms.ValidationError(
                f"Origem e destino são o mesmo lugar ({origem})."
            )

        dados["origem"] = origem
        dados["destino"] = destino

        ids = dados.get("unidades")
        if ids:
            dados["lista_unidades"] = self.resolver_unidades(origem, ids)
        return dados


class BaixaForm(_OrigemCustodiaMixin):
    """Baixa por perda, avaria ou obsolescência (ISC-RF-12, ISC-RN-13).

    O operador escolhe as unidades específicas, não modelo + quantidade: baixa
    é sobre iscas concretas que sumiram ou quebraram. Antes o sistema escolhia
    por FIFO, o que dava a quantidade certa mas as unidades erradas — e o
    identificador é justamente o que torna a baixa auditável.
    """

    #: IDs das unidades marcadas no seletor, enviados como lista.
    unidades = forms.CharField(
        label="Unidades",
        widget=forms.SelectMultiple(
            attrs={"class": "form-select", "id": "id_unidades"}
        ),
        help_text="Busque pelo identificador da isca ou pelo modelo.",
    )
    motivo = forms.ChoiceField(
        choices=MotivoBaixa.choices, label="Motivo",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    justificativa = forms.CharField(
        label="Justificativa",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Obrigatória: descreva o que aconteceu.",
            }
        ),
    )

    def clean_justificativa(self):
        texto = (self.cleaned_data["justificativa"] or "").strip()
        if len(texto) < 5:
            raise forms.ValidationError(
                "Descreva o motivo — baixa sem justificativa é buraco no inventário."
            )
        return texto

    def clean_unidades(self):
        ids = self.normalizar_ids()
        if not ids:
            raise forms.ValidationError("Selecione ao menos uma unidade.")
        return ids

    def clean(self):
        dados = super().clean()
        origem = self.resolver_origem(dados)
        dados["origem"] = origem

        ids = dados.get("unidades")
        if ids:
            dados["lista_unidades"] = self.resolver_unidades(origem, ids)
        return dados


class ManutencaoForm(_OrigemCustodiaMixin):
    """Envio para manutenção (ISC-RF-13). Não é baixa (ISC-RN-14).

    Mesma seleção unitária da baixa, e pelo mesmo motivo: a isca que vai para
    o conserto é uma peça específica. Saber qual voltou depois — e qual modelo
    dá defeito com frequência — depende do identificador.
    """

    unidades = forms.CharField(
        label="Unidades",
        widget=forms.SelectMultiple(
            attrs={"class": "form-select", "id": "id_unidades"}
        ),
        help_text="Busque pelo identificador da isca ou pelo modelo.",
    )
    justificativa = forms.CharField(
        required=False,
        label="Observação",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Qual o defeito, para qual assistência foi, nº de OS…",
            }
        ),
    )

    def clean_unidades(self):
        ids = self.normalizar_ids()
        if not ids:
            raise forms.ValidationError("Selecione ao menos uma unidade.")
        return ids

    def clean(self):
        dados = super().clean()
        origem = self.resolver_origem(dados)
        dados["origem"] = origem

        ids = dados.get("unidades")
        if ids:
            dados["lista_unidades"] = self.resolver_unidades(origem, ids)
        return dados


class RetornoManutencaoForm(_OrigemCustodiaMixin):
    """Retorno da manutenção ao estoque (ISC-RF-13, ISC-RN-14).

    A origem é sempre a conta de manutenção, então aqui o seletor governa o
    **destino**: para onde a peça consertada volta. As unidades vêm de um
    TomSelect com o que está em manutenção — antes o operador digitava os
    identificadores à mão, o que só funcionava se ele os tivesse anotado.
    """

    #: Reaproveita o seletor do mixin com rótulos de destino.
    tipo_origem = forms.ChoiceField(
        choices=_OrigemCustodiaMixin.TIPOS_ORIGEM,
        initial=_OrigemCustodiaMixin.ORIGEM_DEPOSITO,
        label="Devolver para",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    origem_deposito = forms.ModelChoiceField(
        queryset=Deposito.objects.all(), required=False, label="Depósito",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    origem_agente = forms.ModelChoiceField(
        queryset=Agente.objects.all(), required=False, label="Agente",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    unidades = forms.CharField(
        label="Unidades que voltaram",
        widget=forms.SelectMultiple(
            attrs={"class": "form-select", "id": "id_unidades"}
        ),
        help_text="Busque pelo identificador da isca ou pelo modelo.",
    )
    justificativa = forms.CharField(
        required=False,
        label="Observação",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "O que foi feito no conserto, nº da OS, garantia…",
            }
        ),
    )

    def clean_unidades(self):
        ids = self.normalizar_ids()
        if not ids:
            raise forms.ValidationError("Selecione ao menos uma unidade.")
        return ids

    def clean(self):
        dados = super().clean()
        # O seletor aponta o DESTINO; a origem é a conta de manutenção.
        dados["destino"] = self.resolver_origem(dados)

        ids = dados.get("unidades")
        if not ids:
            return dados

        # As unidades precisam estar mesmo em manutenção: se alguém já as
        # retornou por outro caminho, o service recusaria com erro genérico.
        from iscas.enums import TipoCustodia
        from iscas.models.custodia import Unidade

        encontradas = list(
            Unidade.objects.filter(
                pk__in=ids, custodia_atual__tipo=TipoCustodia.MANUTENCAO
            )
        )
        if len(encontradas) != len(set(ids)):
            raise forms.ValidationError(
                {
                    "unidades": (
                        "Alguma unidade selecionada não está mais em manutenção. "
                        "Recarregue a página e selecione novamente."
                    )
                }
            )
        dados["lista_unidades"] = encontradas
        return dados


class RetornoForm(forms.Form):
    """Retorno de retornável em posse de cliente (ISC-RF-32)."""

    destino_deposito = forms.ModelChoiceField(
        queryset=Deposito.objects.all(), required=False, label="Depósito de destino",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    destino_agente = forms.ModelChoiceField(
        queryset=Agente.objects.all(), required=False, label="Agente de destino",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    unidades = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text="IDs das unidades selecionadas, separados por vírgula.",
    )
    ocorrido_em = forms.DateTimeField(
        required=False, label="Data efetiva do retorno",
        widget=forms.DateTimeInput(
            attrs={"class": "form-control", "type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    def clean(self):
        dados = super().clean()
        if bool(dados.get("destino_deposito")) == bool(dados.get("destino_agente")):
            raise forms.ValidationError("Informe exatamente um destino.")
        dados["destino"] = dados.get("destino_deposito") or dados.get("destino_agente")

        ids = [p.strip() for p in (dados.get("unidades") or "").split(",") if p.strip()]
        if not ids:
            raise forms.ValidationError("Selecione ao menos uma unidade para retorno.")
        dados["ids_unidades"] = ids
        return dados


class EstornoForm(forms.Form):
    """Estorno de lançamento (ISC-RF-14, ISC-ADR-16)."""

    justificativa = forms.CharField(
        label="Por que está estornando?",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "O erro e a correção ficam ambos visíveis na auditoria.",
            }
        ),
    )

    def clean_justificativa(self):
        texto = (self.cleaned_data["justificativa"] or "").strip()
        if len(texto) < 5:
            raise forms.ValidationError("Descreva o motivo do estorno.")
        return texto

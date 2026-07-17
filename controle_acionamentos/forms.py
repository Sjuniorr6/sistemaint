# controle_acionamentos/forms.py
from django import forms

from controle_acionamentos.models import (
    Acionamento,
    Agente,
    Cliente,
    FranquiaAgente,
    ResponsavelAgente,
    ServicoCliente,
)


class AcionamentoForm(forms.ModelForm):
    """Form de criação/edição de Acionamento (US-05 / DD-067/ST2).

    O operador NÃO digita mais os valores do serviço: escolhe um serviço ATIVO do
    cliente (`servico_cliente`) e o backend copia os 5 valores para os campos
    inline (snapshot em aplicar_servico_ao_acionamento). Por isso os 5 campos
    inline saíram do form — eles continuam NOT NULL no model, mas quem os preenche
    é a view, ANTES do save (o _post_clean os exclui por não estarem no form).

    `nome_servico` também deixou de ser digitado: vira HiddenInput e é DERIVADO do
    serviço (label do choice). O Acionamento.clean() exige nome_servico já no
    _post_clean (antes de a view aplicar o snapshot), então derivo aqui no clean()
    do form também — o aplicar_servico_ao_acionamento repete a derivação no snapshot.

    Não duplico RN-04/05/06 aqui: ao rodar is_valid(), o ModelForm chama
    full_clean() do model, que dispara o Acionamento.clean(). O form é o portão que
    garante o full_clean antes do save.
    """

    # Seleção do serviço do catálogo (DD-067/ST2). Queryset amplo (todos os
    # serviços); o refinamento — pertencer ao cliente do POST e estar ativo — é o
    # clean() abaixo, com mensagem amigável. Obrigatório: serviço é exigido na
    # criação (regra de 17/07).
    servico_cliente = forms.ModelChoiceField(
        queryset=ServicoCliente.objects.all(),
        required=True,
        label="Serviço",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    # nome_servico não é mais digitado: hidden, derivado do serviço no clean(). No
    # GET de edição carrega o valor do registro (mantém o form populado); no POST o
    # valor é sempre sobrescrito pelo label do serviço.
    nome_servico = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Acionamento
        fields = [
            "cliente",
            # DD-067/ST3 (fresta B): servico_cliente ENTRA no Meta.fields para que o
            # construct_instance copie o serviço postado para a instância ANTES do
            # Acionamento.clean() — assim, ao trocar de cliente, o par cliente/serviço
            # da instância fica coerente. O campo declarado no topo continua mandando
            # na validação (queryset, obrigatoriedade, clean); a view segue aplicando
            # o snapshot pelo cleaned_data.
            "servico_cliente",
            "nome_servico",
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

        # servico_cliente não está em Meta.fields (a view aplica o snapshot), então
        # não herda o valor da instance sozinho. No GET de edição, semeio o initial
        # a partir do registro para o select nascer com o serviço atual selecionado
        # (o JS o mantém após repopular pelo cliente).
        if self.instance and self.instance.pk and self.instance.servico_cliente_id:
            self.fields["servico_cliente"].initial = self.instance.servico_cliente_id

    def clean(self):
        """Refina o serviço escolhido (DD-067/ST2): tem de pertencer ao cliente do
        POST E estar ativo. Mensagens amigáveis no próprio campo servico_cliente.
        Quando o serviço é válido, DERIVA nome_servico do label do choice — o
        Acionamento.clean() exige nome_servico ainda no _post_clean, então a
        derivação precisa acontecer aqui (a view repete no snapshot)."""
        cleaned = super().clean()
        cliente = cleaned.get("cliente")
        servico = cleaned.get("servico_cliente")
        if cliente and servico:
            # DD-067/ST3 (fresta C): é o MESMO serviço já vinculado a este
            # acionamento? (só na edição — instância com pk). Nesse caso a checagem
            # de ATIVO não se aplica: um serviço desativado DEPOIS do vínculo não pode
            # travar a edição. A checagem de MESMO CLIENTE permanece sempre; um
            # serviço DIFERENTE continua exigindo ativo. Na criação (sem pk) nada muda.
            e_o_ja_vinculado = (
                bool(self.instance.pk)
                and self.instance.servico_cliente_id == servico.id
            )
            if servico.cliente_id != cliente.id:
                self.add_error(
                    "servico_cliente", "Escolha um serviço do cliente selecionado."
                )
            elif not servico.ativo and not e_o_ja_vinculado:
                self.add_error(
                    "servico_cliente", "Este serviço está desativado para o cliente."
                )
            else:
                cleaned["nome_servico"] = servico.get_nome_display()
        return cleaned


class PedagioUpdateForm(forms.Form):
    """Valida a entrada do endpoint inline de pedágio (DD-014/M3); min_value=0 implementa AC-07.3."""

    pedagio = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2)


class VincularFranquiaLoteForm(forms.Form):
    """DD-015/M4 (subtask 5) — valida a entrada do vínculo em lote:
    seleção de acionamentos, franquia e flag de sobrescrita (AC-06.5)."""

    acionamentos = forms.ModelMultipleChoiceField(
        queryset=Acionamento.objects.all()
    )
    franquia = forms.ModelChoiceField(queryset=FranquiaAgente.objects.all())
    sobrescrever = forms.BooleanField(required=False)


class FiltroAcionamentosForm(forms.Form):
    """DD-015/M4 (AC-06.1) — valida o querystring da listagem. Filtro TOLERANTE:
    valor inválido ou ausente significa "sem filtro", nunca erro. Por isso o
    campo é required=False; a view trata form inválido como cliente=None.

    DD-016/M5 (AC-08.1) — o form é a alfândega da querystring: cada campo novo
    de filtro entra aqui mantendo a filosofia tolerante (inválido/ausente = sem
    filtro), e a view repassa o valor limpo ao selector."""

    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    agente = forms.ModelChoiceField(
        queryset=Agente.objects.all(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    # ISO = o que o <input type="date"> envia; dd/mm/aaaa = URL digitada à brasileira.
    data_de = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    data_ate = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "Todos"), ("com", "Com franquia"), ("sem", "Sem franquia")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def clean_status(self):
        """Traduz tela→domínio: "com"→True, "sem"→False, vazio→None."""
        valor = self.cleaned_data.get("status")
        if valor == "com":
            return True
        if valor == "sem":
            return False
        return None


class AgenteForm(forms.ModelForm):
    """DD-050/ST2 — form de criação/edição de Agente.

    Estas telas SUBSTITUEM o admin: o operador cadastra aqui inclusive os dados
    de pagamento (bancários) e os clientes vinculados (M2M). A validação (nome
    obrigatório, CPF válido e normalizado, CNH válida se preenchida) mora no
    Agente.clean() — o ModelForm o dispara no is_valid(); NÃO se duplica aqui.
    O M2M clientes_vinculados persiste sozinho no form.save() (sem commit=False).
    """

    class Meta:
        model = Agente
        fields = [
            "nome",
            "cpf",
            "cnh",
            "chave_pix",
            "banco",
            "tipo_conta",
            "agencia",
            "conta",
            "clientes_vinculados",
        ]
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: Carlos Silva"}
            ),
            "cpf": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "000.000.000-00"}
            ),
            "cnh": forms.TextInput(attrs={"class": "form-control"}),
            "chave_pix": forms.TextInput(attrs={"class": "form-control"}),
            "banco": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_conta": forms.Select(attrs={"class": "form-select"}),
            "agencia": forms.TextInput(attrs={"class": "form-control"}),
            "conta": forms.TextInput(attrs={"class": "form-control"}),
            # CheckboxSelectMultiple posta a MESMA lista (name="clientes_vinculados")
            # que o SelectMultiple — contrato de POST intacto. Sem attrs de classe:
            # o estilo vem do CSS do escopo (.acn-multicheck no tema.css).
            "clientes_vinculados": forms.CheckboxSelectMultiple(),
        }


class FranquiaForm(forms.ModelForm):
    """DD-050/ST4 — form de criação/edição de Franquia (FranquiaAgente).

    A validação (nome obrigatório, regra km 0 + escalonamento, unicidade
    cliente+nome) mora no model (clean + UniqueConstraint) — o ModelForm dispara
    o full_clean no is_valid(); NÃO se duplica aqui. Os erros do clean e da
    unicidade são NON-FIELD: o template deve renderizar form.non_field_errors.
    """

    class Meta:
        model = FranquiaAgente
        fields = [
            "cliente",
            "nome",
            "valor_acionamento",
            "franquia_km",
            "franquia_horas",
            "valor_km_excedente",
            "valor_hora_excedente",
            "escalonamento_automatico",
        ]
        widgets = {
            "cliente": forms.Select(attrs={"class": "form-select"}),
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: Franquia Moto 80km/4h"}
            ),
            "valor_acionamento": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "franquia_km": forms.NumberInput(
                attrs={"class": "form-control", "min": "0"}
            ),
            "franquia_horas": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "valor_km_excedente": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "valor_hora_excedente": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "escalonamento_automatico": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class ResponsavelForm(forms.ModelForm):
    """DD-050/ST3 — form de criação/edição de Responsável (ResponsavelAgente).

    Entidade de campo único: só o nome. A validação (nome obrigatório) mora no
    ResponsavelAgente.clean() — o ModelForm o dispara no is_valid(); NÃO se
    duplica aqui.
    """

    class Meta:
        model = ResponsavelAgente
        fields = ["nome"]
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: João Supervisor"}
            ),
        }


class ClienteForm(forms.ModelForm):
    """DD-050/ST1 — form de criação/edição de Cliente.

    Só os campos que o operador digita. A validação (nome obrigatório, CNPJ
    válido e normalização para dígitos) mora no Cliente.clean() — o ModelForm o
    dispara no is_valid() via full_clean(); NÃO se duplica a regra aqui.
    """

    class Meta:
        model = Cliente
        fields = ["nome_empresa", "cnpj"]
        widgets = {
            "nome_empresa": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: ACME Logística LTDA"}
            ),
            "cnpj": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "00.000.000/0000-00"}
            ),
        }


class ServicoClienteLinhaForm(forms.Form):
    """DD-066/ST2 — uma LINHA do catálogo de serviços dentro do form do cliente.

    Não é ModelForm: o catálogo é uma tabela FIXA de 5 linhas (uma por
    ServicoCliente.Nome), então cada linha é um Form puro cujo `nome` (HiddenInput)
    identifica qual serviço do catálogo ela representa. Todos os VALORES são
    opcionais NO CAMPO — a obrigatoriedade é condicional (regra do clean()
    cruzado abaixo): linha em branco é válida ("serviço não configurado");
    marcar Ativo OU preencher qualquer valor obriga os 5.
    """

    nome = forms.ChoiceField(
        choices=ServicoCliente.Nome.choices,
        widget=forms.HiddenInput(),
    )
    ativo = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    valor_acionamento = forms.DecimalField(
        required=False, min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
    )
    franquia_km = forms.IntegerField(
        required=False, min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
    )
    franquia_horas = forms.DecimalField(
        required=False, min_value=0, max_digits=5, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
    )
    valor_km_excedente = forms.DecimalField(
        required=False, min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
    )
    valor_hora_excedente = forms.DecimalField(
        required=False, min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
    )

    # Os 5 valores que, juntos, configuram um serviço (tudo ou nada).
    CAMPOS_VALOR = (
        "valor_acionamento",
        "franquia_km",
        "franquia_horas",
        "valor_km_excedente",
        "valor_hora_excedente",
    )

    def clean(self):
        cleaned = super().clean()
        ativo = cleaned.get("ativo")
        valores = [cleaned.get(campo) for campo in self.CAMPOS_VALOR]
        algum = any(v is not None for v in valores)
        todos = all(v is not None for v in valores)

        # Linha em branco (sem Ativo e sem nenhum valor) = válida e "vazia".
        if not ativo and not algum:
            return cleaned

        # Ativo OU qualquer valor preenchido => exige os 5 (parcial é erro).
        if not todos:
            raise forms.ValidationError(
                "Preencha todos os valores do serviço ou deixe a linha em branco."
            )
        return cleaned

    @property
    def linha_vazia(self):
        """True quando a linha não tem Ativo nem nenhum valor — serviço não
        configurado. Só faz sentido após is_valid() (usa cleaned_data)."""
        dados = getattr(self, "cleaned_data", {})
        if dados.get("ativo"):
            return False
        return not any(dados.get(campo) is not None for campo in self.CAMPOS_VALOR)

    @property
    def nome_label(self):
        """Label humano do serviço (choice) desta linha, para o template."""
        valor = self["nome"].value()
        try:
            return ServicoCliente.Nome(valor).label
        except ValueError:
            return valor


class BaseCatalogoServicosFormSet(forms.BaseFormSet):
    """Formset do catálogo com contexto do cliente.

    Recebe `cliente` para aplicar, no clean() do formset, a regra que a linha
    isolada não enxerga: uma linha DEIXADA EM BRANCO cujo serviço JÁ TEM registro
    no banco é inválida — não se "apaga" um serviço esvaziando a linha (para
    desligar, desmarca-se Ativo; deletar não existe). Sem isso, o service
    ignoraria a linha e o registro seguiria intacto, mas silenciosamente; aqui o
    operador é avisado a completar os valores.
    """

    def __init__(self, *args, cliente=None, **kwargs):
        self.cliente = cliente
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.cliente is None:
            return
        nomes_existentes = set(
            ServicoCliente.objects
            .filter(cliente=self.cliente)
            .values_list("nome", flat=True)
        )
        for form in self.forms:
            # Pula linhas já inválidas por outro motivo (cleaned_data incompleto).
            if form.errors:
                continue
            if form.linha_vazia and form.cleaned_data.get("nome") in nomes_existentes:
                form.add_error(
                    None,
                    "Complete os valores deste serviço já cadastrado ou "
                    "desmarque Ativo — a linha não pode ficar em branco.",
                )


# Formset FIXO de 5 linhas (uma por serviço do catálogo): extra=0 + initial de 5
# na ordem dos choices; max_num/validate_max blindam contra adicionar linhas, e
# can_delete=False contra removê-las (o catálogo nunca deleta — só desativa).
CatalogoServicosFormSet = forms.formset_factory(
    ServicoClienteLinhaForm,
    formset=BaseCatalogoServicosFormSet,
    extra=0,
    max_num=5,
    validate_max=True,
    can_delete=False,
)


def _initial_do_catalogo(cliente):
    """Initial das 5 linhas na ordem dos choices. Sem cliente: só o `nome` de
    cada linha (em branco). Com cliente: as linhas com registro nascem
    preenchidas (ativo + 5 valores); as demais ficam em branco."""
    if cliente is None:
        return [{"nome": nome} for nome in ServicoCliente.Nome.values]

    existentes = {s.nome: s for s in ServicoCliente.objects.filter(cliente=cliente)}
    initial = []
    for nome in ServicoCliente.Nome.values:
        servico = existentes.get(nome)
        if servico is None:
            initial.append({"nome": nome})
        else:
            initial.append({
                "nome": nome,
                "ativo": servico.ativo,
                "valor_acionamento": servico.valor_acionamento,
                "franquia_km": servico.franquia_km,
                "franquia_horas": servico.franquia_horas,
                "valor_km_excedente": servico.valor_km_excedente,
                "valor_hora_excedente": servico.valor_hora_excedente,
            })
    return initial


def montar_catalogo_formset(data=None, cliente=None):
    """DD-066/ST2 — monta o formset do catálogo, prefixo fixo "servicos".

    Sem cliente (create): 5 linhas em branco, uma por Nome na ordem de definição.
    Com cliente (update): cada linha nasce preenchida com o ServicoCliente
    existente (se houver), em branco nas que faltam. O `cliente` também chega à
    base customizada (inclusive no POST, data != None) para o clean do formset.
    """
    return CatalogoServicosFormSet(
        data=data,
        initial=_initial_do_catalogo(cliente),
        prefix="servicos",
        cliente=cliente,
    )
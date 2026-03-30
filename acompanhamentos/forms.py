from django import forms
from django.forms import inlineformset_factory
from .models import (
    registrodeagenteacompanhamento,
    registroacompanhamento,
    registroacompanhamentoagente,
    registroderesposavelagenteacompanhamento,
    FranquiaAgente
)
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.db.models import Q


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
# Cadastro de Acompanhamento
# ===============================
class RegistroAcompanhamentoForm(forms.ModelForm):
    class Meta:
        model = registroacompanhamento
        fields = [
            "cliente",
            "tipo_servico",
            "origem",
            "origem_2",
            "origem_3",
            "destino",
            "destino_2",
            "destino_3",

            "latitude_origem",
            "longitude_origem",
            "latitude_origem2",
            "longitude_origem2",
            "latitude_origem3",
            "longitude_origem3",
            "raio_cerca",
            "raio_cerca_2",
            "raio_cerca_3",

            "latitude_destino",
            "longitude_destino",
            "latitude_destino_2",
            "longitude_destino_2",
            "latitude_destino_3",
            "longitude_destino_3",

            "campo_personalizado_titulo",
            "campo_personalizado_valor",

            "ocorrencia",
        ]

        widgets = {
            "cliente": forms.Select(attrs={"class": "form-control select2"}),
            "tipo_servico": forms.Select(attrs={"class": "form-control select2"}),
            "origem": forms.TextInput(attrs={"class": "form-control bg-light"}),
            "origem_2": forms.TextInput(attrs={"class": "form-control bg-light"}),
            "origem_3": forms.TextInput(attrs={"class": "form-control bg-light"}),
            "destino": forms.TextInput(attrs={"class": "form-control bg-light"}),
            "destino_2": forms.TextInput(attrs={"class": "form-control bg-light"}),
            "destino_3": forms.TextInput(attrs={"class": "form-control bg-light"}),

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
            "latitude_origem2": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: -23.550520",
                "step": "any"
            }),
            "longitude_origem2": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: -46.633308",
                "step": "any"
            }),
            "latitude_origem3": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: -23.550520",
                "step": "any"
            }),
            "longitude_origem3": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: -46.633308",
                "step": "any"
            }),
            "raio_cerca": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Raio em metros"
            }),
            "raio_cerca_2": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Raio em metros"
            }),
            "raio_cerca_3": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Raio em metros"
            }),
            "latitude_destino": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: -23.550520",
                "step": "any"
            }),
            "longitude_destino": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: -46.633308",
                "step": "any"
            }),
            "latitude_destino_2": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: -23.550520",
                "step": "any"
            }),
            "longitude_destino_2": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: -46.633308",
                "step": "any"
            }),
            "latitude_destino_3": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: -23.550520",
                "step": "any"
            }),
            "longitude_destino_3": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: -46.633308",
                "step": "any"
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

# forms.py

class RegistroAcompanhamentoAgenteForm(forms.ModelForm):
    def _resolve_cliente_id(self):
        if getattr(self, "_cliente_id_explicit", None):
            return self._cliente_id_explicit

        if getattr(self.instance, "tipo_servico", None) and self.instance.tipo_servico.cliente_id:
            return self.instance.tipo_servico.cliente_id

        tipo_servico_id = self._resolve_tipo_servico_id()
        if tipo_servico_id:
            from .models import TipoServico
            ts = TipoServico.objects.filter(pk=tipo_servico_id).only("cliente_id").first()
            if ts:
                return ts.cliente_id

        return None

    def _resolve_tipo_servico_id(self):
        if getattr(self, "_tipo_servico_id_explicit", None):
            return self._tipo_servico_id_explicit

        # 1) Instancia existente (edicao)
        if getattr(self.instance, "tipo_servico_id", None):
            return self.instance.tipo_servico_id

        # 2) Initial (GET/formset inicial)
        initial_tipo = self.initial.get("tipo_servico") if hasattr(self, "initial") else None
        if initial_tipo:
            try:
                return int(initial_tipo)
            except (TypeError, ValueError):
                pass

        # 3) POST (quando vier no formset com prefix)
        if self.is_bound and self.prefix:
            key = f"{self.prefix}-tipo_servico"
            raw = self.data.get(key)
            if raw:
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    pass

        return None

    def __init__(self, *args, **kwargs):
        self._cliente_id_explicit = kwargs.pop("cliente_id", None)
        self._tipo_servico_id_explicit = kwargs.pop("tipo_servico_id", None)
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.required = False

        obrigatorios = ["responsavel_agente", "agente", "placa_agente", "franquia"]
        for name in obrigatorios:
            if name in self.fields:
                self.fields[name].required = True
                # ajuda o HTML5/UX também
                self.fields[name].widget.attrs["required"] = "required"

        if "franquia" in self.fields:
            tipo_servico_id = self._resolve_tipo_servico_id()
            cliente_id = self._resolve_cliente_id()
            qs_franquia = FranquiaAgente.objects.all()

            if cliente_id:
                qs_franquia = qs_franquia.filter(
                    Q(cliente_id=cliente_id) |
                    Q(cliente__isnull=True, tipo_servico__cliente_id=cliente_id)
                )

            if tipo_servico_id:
                qs_franquia = qs_franquia.filter(tipo_servico_id=tipo_servico_id)

            self.fields["franquia"].queryset = qs_franquia.order_by("nome")
            self.fields["franquia"].widget.attrs.update({"class": "form-control select2"})

        if "tipo_servico" in self.fields:
            self.fields["tipo_servico"].disabled = True
            self.fields["tipo_servico"].widget.attrs.update({"class": "form-control select2"})

    def clean_tipo_servico(self):
        if self.instance and getattr(self.instance, "pk", None):
            return self.instance.tipo_servico
        return self.cleaned_data.get("tipo_servico")

    class Meta:
        model = registroacompanhamentoagente
        exclude = ("acompanhamento",)

        widgets = {
            "tipo_agente": forms.HiddenInput(),

            "responsavel_agente": forms.Select(attrs={"class": "form-control select2"}),
            "agente": forms.Select(attrs={"class": "form-control select2"}),
            "franquia": forms.Select(attrs={"class": "form-control select2"}),

            "tipo_servico": forms.Select(attrs={"class": "form-control select2"}),

            "placa_agente": forms.TextInput(attrs={"class": "form-control", "placeholder": "Placa Agente"}),
            "motorista": forms.TextInput(attrs={"class": "form-control bg-light", "placeholder": "Motorista", "readonly": "readonly"}),
            "placa_motorista": forms.TextInput(attrs={"class": "form-control bg-light", "placeholder": "Placa Motorista", "readonly": "readonly"}),
            "numero_motorista": forms.TextInput(attrs={"class": "form-control bg-light", "placeholder": "Número Motorista", "readonly": "readonly"}),

            "data_solicitada": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control bg-light", "readonly": "readonly"}),
            "horario_solicitado": forms.TimeInput(attrs={"type": "time", "class": "form-control bg-light", "readonly": "readonly"}),

            "data_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "horario_inicio": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),

            "data_finalizacao": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "horario_finalizacao": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),

            "horario_total": forms.TextInput(attrs={"class": "form-control", "readonly": True, "placeholder": "HH:MM:SS"}),

            "km_inicio": forms.NumberInput(attrs={"class": "form-control", "placeholder": "KM Início"}),
            "km_final": forms.NumberInput(attrs={"class": "form-control", "placeholder": "KM Final"}),
            "km_total": forms.NumberInput(attrs={"class": "form-control", "placeholder": "KM Total", "readonly": True}),

            "pedagio": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),

            "bancario": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "pix": forms.TextInput(attrs={"class": "form-control", "placeholder": "Pix"}),
            "banco": forms.TextInput(attrs={"class": "form-control", "placeholder": "Banco"}),
            "agencia": forms.TextInput(attrs={"class": "form-control", "placeholder": "Agência"}),
            "conta": forms.TextInput(attrs={"class": "form-control", "placeholder": "Conta"}),
            "tipo_conta": forms.TextInput(attrs={"class": "form-control", "placeholder": "Tipo de Conta"}),
            "nome_completo_conta": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome Completo"}),
            "cpf_conta": forms.TextInput(attrs={"class": "form-control", "placeholder": "CPF da Conta"}),
        }

# ===============================
# FORMSET DE AGENTES
# ===============================
class BaseAgenteObrigatorioFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        tem_ativo = False
        for form in self.forms:
            # quando o form não tem cleaned_data ainda (erro de estrutura), ignora
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            obrigatorios = ["responsavel_agente", "agente", "placa_agente", "franquia"]
            faltando = [f for f in obrigatorios if not form.cleaned_data.get(f)]

            if all(not form.cleaned_data.get(f) for f in obrigatorios):
                continue

            tem_ativo = True

            if faltando:
                raise ValidationError(
                    "Preencha Responsável, Agente, Placa do Agente e Franquia em todos os serviços confirmados."
                )

        if not tem_ativo:
            raise ValidationError("Você precisa confirmar pelo menos 1 serviço preenchendo os dados do agente.")

RegistroAcompanhamentoAgenteCreateFormSet = inlineformset_factory(
    registroacompanhamento,
    registroacompanhamentoagente,
    form=RegistroAcompanhamentoAgenteForm,
    formset=BaseAgenteObrigatorioFormSet,
    extra=1,
    can_delete=True
)

RegistroAcompanhamentoAgenteUpdateFormSet = inlineformset_factory(
    registroacompanhamento,
    registroacompanhamentoagente,
    form=RegistroAcompanhamentoAgenteForm,
    formset=BaseAgenteObrigatorioFormSet,
    extra=0,
    can_delete=True
)

class RegistroAcompanhamentoFromRequisicaoForm(forms.ModelForm):
    class Meta:
        model = registroacompanhamento
        fields = [
            "cliente",
            "tipo_servico",
            "origem",
            "origem_2",
            "origem_3",
            "destino",
            "destino_2",
            "destino_3",
            "latitude_origem",
            "longitude_origem",
            "latitude_origem2",
            "longitude_origem2",
            "latitude_origem3",
            "longitude_origem3",
            "raio_cerca",
            "raio_cerca_2",
            "raio_cerca_3",
            "latitude_destino",
            "longitude_destino",
            "latitude_destino_2",
            "longitude_destino_2",
            "latitude_destino_3",
            "longitude_destino_3",
            "campo_personalizado_titulo",
            "campo_personalizado_valor",
            "ocorrencia",
        ]

        widgets = {
            "cliente": forms.HiddenInput(),
            "tipo_servico": forms.Select(attrs={"class": "form-control select2", "disabled": "disabled"}),
            "origem": forms.TextInput(attrs={"class": "form-control "}),
            "origem_2": forms.TextInput(attrs={"class": "form-control "}),
            "origem_3": forms.TextInput(attrs={"class": "form-control "}),
            "destino": forms.TextInput(attrs={"class": "form-control "}),
            "destino_2": forms.TextInput(attrs={"class": "form-control "}),
            "destino_3": forms.TextInput(attrs={"class": "form-control "}),
            "latitude_origem": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "longitude_origem": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "latitude_origem2": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "longitude_origem2": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "latitude_origem3": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "longitude_origem3": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "raio_cerca": forms.NumberInput(attrs={
                "class": "form-control"
            }),
            "raio_cerca_2": forms.NumberInput(attrs={
                "class": "form-control"
            }),
            "raio_cerca_3": forms.NumberInput(attrs={
                "class": "form-control"
            }),
            "latitude_destino": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "longitude_destino": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "latitude_destino_2": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "longitude_destino_2": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "latitude_destino_3": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "longitude_destino_3": forms.NumberInput(attrs={
                "class": "form-control bg-light",
                "step": "any",
                "readonly": "readonly"
            }),
            "campo_personalizado_titulo": forms.TextInput(attrs={
                "class": "form-control"
            }),
            "campo_personalizado_valor": forms.TextInput(attrs={
                "class": "form-control"
            }),
            "ocorrencia": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3
            }),
        }

    def __init__(self, *args, requisicao=None, **kwargs):
        self.requisicao = requisicao
        super().__init__(*args, **kwargs)

        if requisicao:
            self.fields["cliente"].initial = requisicao.cliente
            self.fields["tipo_servico"].queryset = requisicao.cliente.get_tipos_servico_disponiveis()
            self.fields["tipo_servico"].initial = requisicao.tipo_servico

    def clean(self):
        cleaned_data = super().clean()
        if self.requisicao:
            cleaned_data["cliente"] = self.requisicao.cliente
            cleaned_data["tipo_servico"] = self.requisicao.tipo_servico

        return cleaned_data


# EDIÇÃOOO

class RegistroAcompanhamentoEditForm(forms.ModelForm):
    CAMPOS_EDITAVEIS = [
        "origem", "origem_2", "origem_3",
        "destino", "destino_2", "destino_3",
        "raio_cerca", "raio_cerca_2", "raio_cerca_3",
        "campo_personalizado_titulo", "campo_personalizado_valor",
        "ocorrencia",
    ]

    class Meta:
        model = registroacompanhamento
        fields = [
            "cliente",
            "tipo_servico",
            "origem",
            "origem_2",
            "origem_3",
            "destino",
            "destino_2",
            "destino_3",
            "latitude_origem",
            "longitude_origem",
            "latitude_origem2",
            "longitude_origem2",
            "latitude_origem3",
            "longitude_origem3",
            "raio_cerca",
            "raio_cerca_2",
            "raio_cerca_3",
            "latitude_destino",
            "longitude_destino",
            "latitude_destino_2",
            "longitude_destino_2",
            "latitude_destino_3",
            "longitude_destino_3",
            "campo_personalizado_titulo",
            "campo_personalizado_valor",
            "ocorrencia",
        ]

        widgets = {
            "cliente": forms.Select(attrs={"class": "form-control select2"}),
            "tipo_servico": forms.Select(attrs={"class": "form-control select2"}),
            "origem": forms.TextInput(attrs={"class": "form-control"}),
            "origem_2": forms.TextInput(attrs={"class": "form-control"}),
            "origem_3": forms.TextInput(attrs={"class": "form-control"}),
            "destino": forms.TextInput(attrs={"class": "form-control"}),
            "destino_2": forms.TextInput(attrs={"class": "form-control"}),
            "destino_3": forms.TextInput(attrs={"class": "form-control"}),
            "latitude_origem": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "longitude_origem": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "latitude_origem2": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "longitude_origem2": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "latitude_origem3": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "longitude_origem3": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "raio_cerca": forms.NumberInput(attrs={
                "class": "form-control", "placeholder": "Raio em metros"
            }),
            "raio_cerca_2": forms.NumberInput(attrs={
                "class": "form-control", "placeholder": "Raio em metros"
            }),
            "raio_cerca_3": forms.NumberInput(attrs={
                "class": "form-control", "placeholder": "Raio em metros"
            }),
            "latitude_destino": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "longitude_destino": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "latitude_destino_2": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "longitude_destino_2": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "latitude_destino_3": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "longitude_destino_3": forms.NumberInput(attrs={
                "class": "form-control", "step": "any"
            }),
            "campo_personalizado_titulo": forms.TextInput(attrs={
                "class": "form-control"
            }),
            "campo_personalizado_valor": forms.TextInput(attrs={
                "class": "form-control"
            }),
            "ocorrencia": forms.Textarea(attrs={
                "class": "form-control", "rows": 3
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in self.CAMPOS_EDITAVEIS:
                field.disabled = True
                field.widget.attrs.update({
                    "class": field.widget.attrs.get("class", "") + " bg-light",
                    "readonly": "readonly",
                    "tabindex": "-1",
                })

class RegistroAcompanhamentoAgenteEditForm(forms.ModelForm):
    CAMPOS_EDITAVEIS_AGENTE = [
        "motorista", "placa_motorista", "agente", "placa_agente",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.required = False

        if "agente" in self.fields:
            self.fields["agente"].queryset = (
                registrodeagenteacompanhamento.objects.all().order_by("nome")
            )

        if "responsavel_agente" in self.fields:
            self.fields["responsavel_agente"].queryset = (
                registroderesposavelagenteacompanhamento.objects.all().order_by("nome")
            )

        if "franquia" in self.fields:
            tipo_servico_id = getattr(self.instance, "tipo_servico_id", None)
            cliente_id = None
            if getattr(self.instance, "tipo_servico", None):
                cliente_id = self.instance.tipo_servico.cliente_id

            qs_franquia = FranquiaAgente.objects.all()

            if cliente_id:
                qs_franquia = qs_franquia.filter(
                    Q(cliente_id=cliente_id) |
                    Q(cliente__isnull=True, tipo_servico__cliente_id=cliente_id)
                )

            if tipo_servico_id:
                qs_franquia = qs_franquia.filter(tipo_servico_id=tipo_servico_id)

            self.fields["franquia"].queryset = qs_franquia.order_by("nome")

        if "tipo_servico" in self.fields:
            from .models import TipoServico
            self.fields["tipo_servico"].queryset = TipoServico.objects.all()

        for name, field in self.fields.items():
            if name not in self.CAMPOS_EDITAVEIS_AGENTE:
                field.disabled = True
                current_class = field.widget.attrs.get("class", "")
                if "bg-light" not in current_class:
                    field.widget.attrs["class"] = current_class + " bg-light"

        for name in ["agente", "placa_agente"]:
            if name in self.fields:
                self.fields[name].required = True

    class Meta:
        model = registroacompanhamentoagente
        exclude = ("acompanhamento",)

        widgets = {
            "tipo_agente": forms.HiddenInput(),
            "responsavel_agente": forms.Select(attrs={"class": "form-control select2"}),
            "agente": forms.Select(attrs={"class": "form-control select2"}),
            "franquia": forms.Select(attrs={"class": "form-control select2"}),
            "tipo_servico": forms.Select(attrs={"class": "form-control select2"}),
            "placa_agente": forms.TextInput(attrs={"class": "form-control"}),
            "motorista": forms.TextInput(attrs={"class": "form-control"}),
            "placa_motorista": forms.TextInput(attrs={"class": "form-control"}),
            "data_solicitada": forms.DateInput(format="%Y-%m-%d", attrs={
                "type": "date", "class": "form-control"
            }),
            "horario_solicitado": forms.TimeInput(attrs={
                "type": "time", "class": "form-control"
            }),
            "data_inicio": forms.DateInput(format="%Y-%m-%d", attrs={
                "type": "date", "class": "form-control"
            }),
            "horario_inicio": forms.TimeInput(attrs={
                "type": "time", "class": "form-control"
            }),
            "data_finalizacao": forms.DateInput(format="%Y-%m-%d", attrs={
                "type": "date", "class": "form-control"
            }),
            "horario_finalizacao": forms.TimeInput(attrs={
                "type": "time", "class": "form-control"
            }),
            "horario_total": forms.TextInput(attrs={
                "class": "form-control", "readonly": True
            }),
            "km_inicio": forms.NumberInput(attrs={"class": "form-control"}),
            "km_final": forms.NumberInput(attrs={"class": "form-control"}),
            "km_total": forms.NumberInput(attrs={"class": "form-control", "readonly": True}),
            "pedagio": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "bancario": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "pix": forms.TextInput(attrs={"class": "form-control"}),
            "banco": forms.TextInput(attrs={"class": "form-control"}),
            "agencia": forms.TextInput(attrs={"class": "form-control"}),
            "conta": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_conta": forms.TextInput(attrs={"class": "form-control"}),
            "nome_completo_conta": forms.TextInput(attrs={"class": "form-control"}),
            "cpf_conta": forms.TextInput(attrs={"class": "form-control"}),
        }

class BaseAgenteEditFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

RegistroAcompanhamentoAgenteEditFormSet = inlineformset_factory(
    registroacompanhamento,
    registroacompanhamentoagente,
    form=RegistroAcompanhamentoAgenteEditForm,
    formset=BaseAgenteEditFormSet,
    extra=0,
    can_delete=False,
)
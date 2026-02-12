from typing import Any
import uuid
from django.shortcuts import render
from django.views.generic import (
    ListView,
    CreateView,
    DetailView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.forms import inlineformset_factory
from django.db import transaction
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
import logging
from franquia.models import registrodefranquia
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta, time
import json
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from decimal import Decimal, InvalidOperation
from openpyxl.styles import Alignment
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from .models import (
    registrodeagenteacompanhamento,
    registrodeclienteacompanhamento,
    servicosacompanhamentos,
    registroacompanhamento,
    registroacompanhamentoagente,
    registroderesposavelagenteacompanhamento,
    AcompanhamentoLocalizacao
)

from .forms import (
    RegistroAgente,
    FormulariosForm,
    ServicosAcompanhamentosForm,
    RegistroAcompanhamentoForm,
    RegistroAcompanhamentoAgenteForm,
    RegistroAcompanhamentoAgenteCreateFormSet,
    RegistroAcompanhamentoAgenteUpdateFormSet,
    RegistroResponsavelAgente
)

from typing import Any
from django.views.generic import (
    ListView,
    CreateView,
    DetailView,
    UpdateView,
    DeleteView,
)

from io import BytesIO
import openpyxl
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from .utils import gerar_link_app_missao
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404
from .api.supabase_client import get_supabase
import logging
logger = logging.getLogger(__name__)
# ------------------------------------------------------
#                 Agente Acompanhamento
# ------------------------------------------------------
class AgenteAcompanhamentoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = registrodeagenteacompanhamento
    form_class = RegistroAgente
    template_name = "agente_acompanhamento_create.html"
    success_url = reverse_lazy("agenteAcompanhamentoList")
    permission_required = "acompanhamentos.add_registrodeagenteacompanhamento"

    def get_initial(self):
        initial = super().get_initial()
        user = getattr(self.request, 'user', None)
        if user:
            initial['nome_user'] = user.get_full_name() or user.username
        return initial

    def form_valid(self, form):
        campos_para_validar = [
            'nome', 'cpf', 'pix', 'banco', 'agencia', 'conta', 'tipo_conta'
        ]

        dados = form.cleaned_data

        # Verifica se TODOS estão vazios
        todos_vazios = all(
            not dados.get(campo)
            for campo in campos_para_validar
        )

        if todos_vazios:
            return redirect("agenteAcompanhamentoCreate")

        instance = form.save(commit=False)

        user = getattr(self.request, 'user', None)
        if user:
            instance.nome_user = user.get_full_name() or user.username

        instance.save()
        return super().form_valid(form)

class AgenteAcompanhamentoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = registrodeagenteacompanhamento
    template_name = "agente_acompanhamento_list.html"
    context_object_name = "agente_acompanhamentos"
    permission_required = "acompanhamentos.view_registrodeagenteacompanhamento"

    def get_queryset(self):
        queryset = super().get_queryset()

        nome = self.request.GET.get("nome")

        if nome:
            queryset = queryset.filter(nome__icontains=nome)

        return queryset.order_by("-criado_em")

class RegistroAgenteAcompanhamentoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):

    model = registrodeagenteacompanhamento
    form_class = RegistroAgente
    template_name = "agente_acompanhamento_create.html"
    success_url = reverse_lazy("agenteAcompanhamentoList")
    permission_required = "acompanhamentos.change_registrodeagenteacompanhamento"

    def form_valid(self, form):
        return super().form_valid(form)

# ------------------------------------------------------
#             Responsável Agente Acompanhamento
# ------------------------------------------------------
class ResponsavelAgenteAcompanhamentoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = registroderesposavelagenteacompanhamento
    template_name = "responsavel_list.html"
    context_object_name = "responsavel_agente_acompanhamentos"
    permission_required = "acompanhamentos.view_registrodeagenteacompanhamento"

    def get_queryset(self):
        queryset = super().get_queryset()

        nome = self.request.GET.get("nome")

        if nome:
            queryset = queryset.filter(nome__icontains=nome)

        return queryset.order_by("-criado_em")

@login_required
@permission_required("acompanhamentos.add_registroderesposavelagenteacompanhamento", raise_exception=True)

@require_POST
def criar_responsavel_agente_ajax(request):
    nome = request.POST.get("nome")

    if not nome:
        return JsonResponse(
            {"success": False, "error": "Nome é obrigatório."},
            status=400
        )

    agente = registroderesposavelagenteacompanhamento.objects.create(
        nome=nome,
        nome_user=request.user.get_full_name() or request.user.username
    )

    return JsonResponse({
        "success": True,
        "id": agente.id,
        "nome": agente.nome
    })

@login_required
@permission_required("acompanhamentos.change_registroderesposavelagenteacompanhamento",raise_exception=True)

@require_POST
def editar_responsavel_agente_ajax(request, pk):
    nome = request.POST.get("nome")

    if not nome:
        return JsonResponse(
            {"success": False, "error": "Nome é obrigatório."},
            status=400
        )

    agente = get_object_or_404(
        registroderesposavelagenteacompanhamento,
        pk=pk
    )

    agente.nome = nome
    agente.nome_user = request.user.get_full_name() or request.user.username
    agente.save(update_fields=["nome", "nome_user", "atualizado_em"])

    return JsonResponse({
        "success": True,
        "id": agente.id,
        "nome": agente.nome
    })

# ------------------------------------------------------
#                 Cliente Acompanhamento
# ------------------------------------------------------
class ClienteAcompanhamentoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = registrodeclienteacompanhamento
    form_class = FormulariosForm
    template_name = "cliente_acompanhamento_create.html"
    success_url = reverse_lazy("clienteAcompanhamentoList")
    permission_required = "acompanhamentos.add_registrodeclienteacompanhamento"

    def get_initial(self):
        initial = super().get_initial()
        user = getattr(self.request, 'user', None)
        if user:
            initial['nome_user'] = user.get_full_name() or user.username
        return initial

    def form_valid(self, form):
        campos_para_validar = [
            'nome', 'cnpj', 'email',
        ]

        dados = form.cleaned_data

        # Verifica se TODOS estão vazios
        todos_vazios = all(
            not dados.get(campo)
            for campo in campos_para_validar
        )

        if todos_vazios:
            return redirect("clienteAcompanhamentoCreate")

        instance = form.save(commit=False)

        user = getattr(self.request, 'user', None)
        if user:
            instance.nome_user = user.get_full_name() or user.username

        instance.save()
        return super().form_valid(form)

class ClienteAcompanhamentoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = registrodeclienteacompanhamento
    template_name = "cliente_acompanhamento_list.html"
    context_object_name = "cliente_acompanhamentos"
    permission_required = "acompanhamentos.view_registrodeclienteacompanhamento"

    def get_queryset(self):
        queryset = super().get_queryset()

        nome = self.request.GET.get("nome")

        if nome:
            queryset = queryset.filter(nome__icontains=nome)

        return queryset.order_by("-criado_em")

class RegistroClienteAcompanhamentoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):

    model = registrodeclienteacompanhamento
    form_class = FormulariosForm
    template_name = "cliente_acompanhamento_create.html"
    success_url = reverse_lazy("clienteAcompanhamentoList")
    permission_required = "acompanhamentos.change_registrodeclienteacompanhamento"

    def form_valid(self, form):
        return super().form_valid(form)

# ------------------------------------------------------
#                 Serviço Acompanhamento
# ------------------------------------------------------
class ServicoAcompanhamentoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = servicosacompanhamentos
    form_class = ServicosAcompanhamentosForm
    template_name = "servico_acompanhamento_create.html"
    success_url = reverse_lazy("servicoAcompanhamentoList")
    permission_required = "acompanhamentos.add_servicosacompanhamentos"

    def get_initial(self):
        initial = super().get_initial()
        user = getattr(self.request, 'user', None)
        if user:
            initial['nome_user'] = user.get_full_name() or user.username
        return initial

    def form_valid(self, form):
        campos_para_validar = [
            'tipo', 'agentes', 'nomeclatura'
        ]

        dados = form.cleaned_data

        # Verifica se TODOS estão vazios
        todos_vazios = all(
            not dados.get(campo)
            for campo in campos_para_validar
        )

        if todos_vazios:
            return redirect("servicoAcompanhamentoCreate")

        instance = form.save(commit=False)

        user = getattr(self.request, 'user', None)
        if user:
            instance.nome_user = user.get_full_name() or user.username

        instance.save()
        return super().form_valid(form)

class ServicoAcompanhamentoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = servicosacompanhamentos
    template_name = "servico_acompanhamento_list.html"
    context_object_name = "servico_acompanhamentos"
    permission_required = "servico_acompanhamento.view_servicosacompanhamentos"

    def get_queryset(self):
        queryset = super().get_queryset()

        nome = self.request.GET.get("nomeclatura")

        if nome:
            queryset = queryset.filter(nome__icontains=nome)

        return queryset.order_by("-criado_em")

class RegistroServicoAcompanhamentoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):

    model = servicosacompanhamentos
    form_class = ServicosAcompanhamentosForm
    template_name = "servico_acompanhamento_create.html"
    success_url = reverse_lazy("servicoAcompanhamentoList")
    permission_required = "acompanhamentos.change_servicosacompanhamentos"

    def form_valid(self, form):
        return super().form_valid(form)

# ------------------------------------------------------
#                   Acompanhamento
# ------------------------------------------------------
def join_values(values):
    return "\n".join(str(v) for v in values if v)

def moeda(valor):
    if valor is None:
        return ""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def agentes_nao_carona(agentes):
    return [a for a in agentes if a.tipo_agente != "carona"]

def join_values_nao_carona(values):
    return "\n".join(str(v) for v in values if v)

from .utils import sync_acompanhamento_to_supabase, delete_supabase_mission

class AcompanhamentoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = registroacompanhamento
    form_class = RegistroAcompanhamentoForm
    template_name = "acompanhamento_create.html"
    success_url = reverse_lazy("AcompanhamentosCreate")
    permission_required = "acompanhamentos.add_registroacompanhamento"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["agentes_formset"] = RegistroAcompanhamentoAgenteCreateFormSet(
                self.request.POST
            )
        else:
            context["agentes_formset"] = RegistroAcompanhamentoAgenteCreateFormSet()

        context["agentes_cadastrados"] = (
            registrodeagenteacompanhamento.objects
            .all()
            .order_by("nome")
        )

        return context

    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data()
        agentes_formset = context["agentes_formset"]

        if not agentes_formset.is_valid():
            return self.render_to_response(context)

        acompanhamento = form.save(commit=False)

        if not acompanhamento.status:
            acompanhamento.status = "pendente"

        user = self.request.user
        acompanhamento.nome_user = user.get_full_name() or user.username

        # 🔥 SALVAR PRIMEIRO PARA GERAR O ID
        acompanhamento.save()

        agentes_formset.instance = acompanhamento
        agentes = agentes_formset.save(commit=False)

        for agente in agentes:
            agente.acompanhamento = acompanhamento
            agente.save()

        caronas = self.request.POST.getlist("carona_agente[]")

        agente_principal = (
            acompanhamento.agentes
            .filter(tipo_agente="principal")
            .first()
        )

        for agente_id in caronas:
            if agente_id and agente_principal:
                agente_obj = registrodeagenteacompanhamento.objects.filter(id=agente_id).first()

                registroacompanhamentoagente.objects.create(
                    acompanhamento=acompanhamento,
                    tipo_agente="carona",
                    responsavel_agente=agente_principal.responsavel_agente,
                    agente=agente_obj,
                    placa_agente=agente_principal.placa_agente,
                    motorista=agente_principal.motorista,
                    placa_motorista=agente_principal.placa_motorista,
                    km_inicio=agente_principal.km_inicio,
                    km_final=agente_principal.km_final,
                    km_total=agente_principal.km_total,
                    data_solicitada=agente_principal.data_solicitada,
                    horario_solicitado=agente_principal.horario_solicitado,
                    data_inicio=agente_principal.data_inicio,
                    horario_inicio=agente_principal.horario_inicio,
                    data_finalizacao=agente_principal.data_finalizacao,
                    horario_finalizacao=agente_principal.horario_finalizacao,
                    pedagio=Decimal("0.00"),
                    valor_agente=Decimal("0.00"),
                )

        for obj in agentes_formset.deleted_objects:
            obj.delete()

        success, mission_id, error = sync_acompanhamento_to_supabase(acompanhamento)
        
        if not success:
            # Log o erro mas não bloqueia a criação
            messages.warning(
                self.request, 
                f"Acompanhamento criado, mas houve erro ao sincronizar com sistema de rastreamento: {error}"
            )
            logger.warning(f"Acompanhamento {acompanhamento.id} criado mas não sincronizado: {error}")
        else:
            messages.success(
                self.request,
                f"Acompanhamento criado e sincronizado com sucesso! ID da missão: {mission_id}"
            )

        return redirect(self.success_url)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

class AcompanhamentoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = registroacompanhamento
    template_name = "acompanhamento_list.html"
    context_object_name = "itens"
    permission_required = "acompanhamentos.view_registroacompanhamento"

    def get_pendentes_queryset(self):
        return registroacompanhamento.objects.filter(
            Q(tipo_servico__isnull=True) |

            Q(agentes__responsavel_agente__isnull=True) |
            Q(agentes__responsavel_agente__isnull=True) |

            Q(agentes__agente__isnull=True) |

            Q(agentes__data_solicitada__isnull=True) |
            Q(agentes__horario_solicitado__isnull=True) |

            Q(agentes__data_inicio__isnull=True) |
            Q(agentes__horario_inicio__isnull=True) |

            Q(agentes__data_finalizacao__isnull=True) |
            Q(agentes__horario_finalizacao__isnull=True) |

            Q(agentes__km_inicio__isnull=True) |
            Q(agentes__km_final__isnull=True) |

            Q(agentes__franquia__isnull=True)
        ).distinct()

    def get_queryset(self):
        qs = (
            registroacompanhamento.objects
            .prefetch_related(
                "agentes",
                "agentes__agente",
                "agentes__franquia"
            )
            .select_related("cliente")
        )

        pendente = self.request.GET.get("pendente")
        if pendente == "true":
            return self.get_pendentes_queryset().order_by("-criado_em")

        data = self.request.GET.get("data")
        data2 = self.request.GET.get("data2")
        agente = self.request.GET.get("agente")
        cliente = self.request.GET.get("cliente")
        responsavel = self.request.GET.get("responsavel")

        if data and data2:
            if data > data2:
                data, data2 = data2, data
            qs = qs.filter(agentes__data_solicitada__range=[data, data2])
        elif data:
            qs = qs.filter(agentes__data_solicitada=data)
        elif data2:
            qs = qs.filter(agentes__data_solicitada=data2)

        if agente:
            qs = qs.filter(agentes__agente__nome__icontains=agente)

        if cliente:
            qs = qs.filter(cliente__nome__icontains=cliente)

        if responsavel:
            queryset = queryset.filter(
                agentes__responsavel_agente_id=responsavel
            )

        return qs.distinct().order_by("-criado_em")

    def render_to_response(self, context, **response_kwargs):

        queryset = context["itens"]

        if self.request.GET.get("export") == "excel":
            return self.exportar_excel(queryset)
        
        if self.request.GET.get("export") == "pdf":
            return self.exportar_pdf(queryset)

        return super().render_to_response(context, **response_kwargs)

    def exportar_pdf(self, queryset):
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=(2000, 900),
            topMargin=20,
            leftMargin=20,
            rightMargin=20,
            bottomMargin=20
        )

        elements = []

        styles = getSampleStyleSheet()
        title_style = styles["Title"]

        cell_style = ParagraphStyle(
            name="CellStyle",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            wordWrap="CJK",
            alignment=0
        )

        title = Paragraph("Relatório de Acompanhamentos", title_style)
        title.alignment = 1
        elements.append(title)
        elements.append(Paragraph("<br/>", styles["Normal"]))

        headers = [
            "Protocolo", "Cliente", "Tipo Serviço", "Origem", "Destino",
            "Responsável", "Agente", "Placa Agente",
            "Motorista", "Placa Motorista",
            "Data Solicitada", "Hora Solicitada",
            "Data Inicial", "Hora Inicial",
            "Data Final", "Hora Final",
            "Hora Total", "Hora Excedente",
            "KM Início", "KM Final", "KM Total", "KM Excedente",
            "Pedágio", "Franquia",
            "Valor Agente(s)",
            "TOTAL",
            "Ocorrência", "Feito Por"
        ]

        data = [headers]

        total_geral = Decimal("0.00")

        for item in queryset:
            agentes = item.agentes.all()
            agentes_validos = agentes_nao_carona(agentes)

            total_geral += item.total_valor_agentes

            row = [
                str(item.id),
                Paragraph(str(item.cliente), cell_style),
                Paragraph(str(item.tipo_servico), cell_style),
                Paragraph(item.origem or "", cell_style),
                Paragraph(item.destino or "", cell_style),

                Paragraph(
                    join_values(a.responsavel_agente.nome for a in agentes_validos),
                    cell_style
                ),
                Paragraph(join_values(str(a.agente) for a in agentes), cell_style),
                Paragraph(join_values(a.placa_agente for a in agentes_validos), cell_style),

                Paragraph(join_values(a.motorista for a in agentes_validos), cell_style),
                Paragraph(join_values(a.placa_motorista for a in agentes_validos), cell_style),

                join_values_nao_carona(a.data_solicitada.strftime("%d/%m/%Y") for a in agentes_validos if a.data_solicitada),
                join_values_nao_carona(a.horario_solicitado.strftime("%H:%M") for a in agentes_validos if a.horario_solicitado),

                join_values_nao_carona(a.data_inicio.strftime("%d/%m/%Y") for a in agentes_validos if a.data_inicio),
                join_values_nao_carona(a.horario_inicio.strftime("%H:%M") for a in agentes_validos if a.horario_inicio),

                join_values_nao_carona(a.data_finalizacao.strftime("%d/%m/%Y") for a in agentes_validos if a.data_finalizacao),
                join_values_nao_carona(a.horario_finalizacao.strftime("%H:%M") for a in agentes_validos if a.horario_finalizacao),

                join_values_nao_carona(str(a.horario_total) for a in agentes_validos if a.horario_total),
                join_values_nao_carona(str(a.horario_excedente) for a in agentes_validos if a.horario_excedente),

                join_values_nao_carona(str(a.km_inicio) for a in agentes_validos if a.km_inicio is not None),
                join_values_nao_carona(str(a.km_final) for a in agentes_validos if a.km_final is not None),
                join_values_nao_carona(str(a.km_total) for a in agentes_validos if a.km_total is not None),
                join_values_nao_carona(str(a.km_excedente) for a in agentes_validos if a.km_excedente),

                join_values_nao_carona(moeda(a.pedagio) for a in agentes_validos if a.pedagio),
                join_values(a.franquia.nome if a.franquia else "" for a in agentes_validos),

                join_values(moeda(a.valor_agente) for a in agentes if a.valor_agente),
                moeda(item.total_valor_agentes),

                Paragraph(item.ocorrencia or "", cell_style),
                Paragraph(item.nome_user or "", cell_style),
            ]

            data.append(row)

        total_row = [""] * len(headers)
        total_row[25] = Paragraph(f"Total Geral: {moeda(total_geral)}", cell_style)
        data.append(total_row)

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),

            ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]))

        elements.append(table)
        doc.build(elements)

        buffer.seek(0)
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="acompanhamentos.pdf"'
        return response

    def exportar_excel(self, queryset):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Acompanhamentos"

        headers = [
            "Protocolo", "Cliente", "Tipo Serviço", "Origem", "Destino",
            "Responsável", "Agente", "Placa Agente",
            "Motorista", "Placa Motorista",
            "Data Solicitada", "Hora Solicitada",
            "Data Inicial", "Hora Inicial",
            "Data Final", "Hora Final",
            "Hora Total", "Hora Excedente",
            "KM Início", "KM Final", "KM Total", "KM Excedente",
            "Pedágio", "Franquia",
            "Valor Agente(s)",
            "TOTAL",
            "Ocorrência", "Feito Por"
        ]

        sheet.append(headers)

        total_geral = Decimal("0.00")

        for item in queryset:
            agentes = item.agentes.all()
            agentes_validos = agentes_nao_carona(agentes)
            total_geral += item.total_valor_agentes or Decimal("0.00")

            sheet.append([
                item.id,
                str(item.cliente),
                str(item.tipo_servico),
                item.origem,
                item.destino,

                join_values(a.responsavel_agente.nome for a in agentes_validos),
                join_values(str(a.agente) for a in agentes),
                join_values(a.placa_agente for a in agentes_validos),

                join_values(a.motorista for a in agentes_validos),
                join_values(a.placa_motorista for a in agentes_validos),

                join_values(a.data_solicitada.strftime("%d/%m/%Y") for a in agentes_validos if a.data_solicitada),
                join_values(a.horario_solicitado.strftime("%H:%M") for a in agentes_validos if a.horario_solicitado),

                join_values(a.data_inicio.strftime("%d/%m/%Y") for a in agentes_validos if a.data_inicio),
                join_values(a.horario_inicio.strftime("%H:%M") for a in agentes_validos if a.horario_inicio),

                join_values(a.data_finalizacao.strftime("%d/%m/%Y") for a in agentes_validos if a.data_finalizacao),
                join_values(a.horario_finalizacao.strftime("%H:%M") for a in agentes_validos if a.horario_finalizacao),

                join_values(str(a.horario_total) for a in agentes_validos if a.horario_total),
                join_values(str(a.horario_excedente) for a in agentes_validos if a.horario_excedente),

                join_values(str(a.km_inicio) for a in agentes_validos if a.km_inicio is not None),
                join_values(str(a.km_final) for a in agentes_validos if a.km_final is not None),
                join_values(str(a.km_total) for a in agentes_validos if a.km_total is not None),
                join_values(str(a.km_excedente) for a in agentes_validos if a.km_excedente),

                join_values(moeda(a.pedagio) for a in agentes_validos if a.pedagio),
                join_values(a.franquia.nome if a.franquia else "" for a in agentes_validos),

                join_values(moeda(a.valor_agente) for a in agentes if a.valor_agente),
                moeda(item.total_valor_agentes),

                item.ocorrencia,
                item.nome_user,
            ])

            row_number = sheet.max_row

            multi_columns = [
                6, 7, 8, 9, 10,
                11, 12, 13, 14, 15, 16,
                17, 18,
                19, 20, 21, 22,
                23, 24, 25
            ]

            max_lines = 1
            for col in multi_columns:
                cell = sheet.cell(row=row_number, column=col)
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if cell.value:
                    max_lines = max(max_lines, cell.value.count("\n") + 1)

            sheet.row_dimensions[row_number].height = 15 * max_lines

        sheet.append([])

        total_row = [""] * len(headers)
        total_row[25] = f"TOTAL GERAL: {moeda(total_geral)}"
        sheet.append(total_row)

        last_row = sheet.max_row
        for col in range(1, len(headers) + 1):
            cell = sheet.cell(row=last_row, column=col)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color="D3D3D3",
                end_color="D3D3D3",
                fill_type="solid"
            )

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="acompanhamentos.xlsx"'
        workbook.save(response)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["franquias"] = registrodefranquia.objects.all().order_by("nome")

        context["pendentes_count"] = self.get_pendentes_queryset().count()

        context["data"] = self.request.GET.get("data", "")
        context["data2"] = self.request.GET.get("data2", "")
        context["agente"] = self.request.GET.get("agente", "")
        context["cliente"] = self.request.GET.get("cliente", "")

        return context

class RegistroAcompanhamentoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = registroacompanhamento
    form_class = RegistroAcompanhamentoForm
    template_name = "acompanhamento_create.html"
    success_url = reverse_lazy("acompanhamentosList")
    permission_required = "acompanhamentos.change_registroacompanhamento"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["agentes_formset"] = RegistroAcompanhamentoAgenteUpdateFormSet(
                self.request.POST,
                instance=self.object
            )
        else:
            context["agentes_formset"] = RegistroAcompanhamentoAgenteUpdateFormSet(
                instance=self.object
            )

        return context

    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data()
        agentes_formset = context["agentes_formset"]

        if not agentes_formset.is_valid():
            return self.render_to_response(context)

        acompanhamento = form.save(commit=False)
        
        user = self.request.user
        acompanhamento.nome_user = user.get_full_name() or user.username

        acompanhamento.save()

        agentes_formset.instance = acompanhamento
        agentes = agentes_formset.save(commit=False)

        for agente in agentes:
            agente.acompanhamento = acompanhamento

            if agente.pk:
                agente_antigo = registroacompanhamentoagente.objects.get(pk=agente.pk)
                agente.franquia = agente_antigo.franquia

            agente.save()

        for obj in agentes_formset.deleted_objects:
            obj.delete()

        # 🔥 ATUALIZAR STATUS NO SUPABASE
        from .utils import update_supabase_mission_status

        if getattr(acompanhamento, "supabase_mission_id", None) and acompanhamento.status:
            success = update_supabase_mission_status(
                str(acompanhamento.supabase_mission_id),
                acompanhamento.status
            )

            if not success:
                messages.warning(
                    self.request,
                    "Acompanhamento atualizado, mas houve erro ao sincronizar status com sistema de rastreamento"
                )

        return redirect(self.success_url)

class AcompanhamentoFaturamentoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = registroacompanhamento
    template_name = "acompanhamento_faturamento_list.html"
    context_object_name = "itens"
    permission_required = "acompanhamentos.view_listacompanhamento"

    def get_pendentes_queryset(self):
        return registroacompanhamento.objects.filter(
            # ========================
            # OPERACIONAL
            # ========================
            Q(tipo_servico__isnull=True) |

            Q(agentes__responsavel_agente__isnull=True) |
            Q(agentes__responsavel_agente__isnull=True) |

            Q(agentes__agente__isnull=True) |

            Q(agentes__data_solicitada__isnull=True) |
            Q(agentes__horario_solicitado__isnull=True) |

            Q(agentes__data_inicio__isnull=True) |
            Q(agentes__horario_inicio__isnull=True) |

            Q(agentes__data_finalizacao__isnull=True) |
            Q(agentes__horario_finalizacao__isnull=True) |

            Q(agentes__km_inicio__isnull=True) |
            Q(agentes__km_final__isnull=True) |

            Q(agentes__franquia__isnull=True) |

            # ========================
            # FINANCEIRO
            # ========================
            Q(validar_acompanhamento=False) |
            Q(valor_contrato__isnull=True) |
            Q(lucro_total__isnull=True) |
            Q(validar_pagamento=False) |
            Q(nf__isnull=True) |
            Q(nf="")
        ).distinct()

    def get_queryset(self):
        qs = (
            registroacompanhamento.objects
            .prefetch_related(
                "agentes",
                "agentes__agente",
                "agentes__franquia"
            )
            .select_related("cliente")
        )

        data = self.request.GET.get("data")
        data2 = self.request.GET.get("data2")
        agente = self.request.GET.get("agente")
        cliente = self.request.GET.get("cliente")
        status = self.request.GET.get("status")

        if data and data2:
            if data > data2:
                data, data2 = data2, data
            qs = qs.filter(agentes__data_solicitada__range=[data, data2])
        elif data:
            qs = qs.filter(agentes__data_solicitada=data)
        elif data2:
            qs = qs.filter(agentes__data_solicitada=data2)

        if agente:
            qs = qs.filter(agentes__agente__nome__icontains=agente)

        if cliente:
            qs = qs.filter(cliente__nome__icontains=cliente)

        if status:
            qs = qs.filter(status=status)

        return qs.distinct().order_by("-criado_em")

    def render_to_response(self, context, **response_kwargs):
        queryset = context["itens"]
        export = self.request.GET.get("export")

        if export == "faturamento_excel":
            return self.exportar_excel(queryset)
        
        if export == "faturamento_excel_cliente":
            return self.exportar_excel_cliente(queryset)

        if export == "faturamento_pdf":
            return self.exportar_pdf(queryset)

        return super().render_to_response(context, **response_kwargs)

    def exportar_pdf(self, queryset):
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=(2000, 900),
            topMargin=20,
            leftMargin=20,
            rightMargin=20,
            bottomMargin=20
        )

        elements = []

        styles = getSampleStyleSheet()
        title_style = styles["Title"]

        cell_style = ParagraphStyle(
            name="CellStyle",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            wordWrap="CJK",
            alignment=0
        )

        title = Paragraph("Relatório de Acompanhamentos", title_style)
        title.alignment = 1
        elements.append(title)
        elements.append(Paragraph("<br/>", styles["Normal"]))

        headers = [
            "Protocolo", "Cliente", "Tipo Serviço", "Origem", "Destino",
            "Responsável", "Agente", "Placa Agente",
            "Motorista", "Placa Motorista",
            "Data Solicitada", "Hora Solicitada",
            "Data Inicial", "Hora Inicial",
            "Data Final", "Hora Final",
            "Hora Total", "Hora Excedente",
            "KM Início", "KM Final", "KM Total", "KM Excedente",
            "Pedágio", "Franquia",
            "Valor Agente(s)",
            "Total Agentes",
            "Ocorrência",
            "Usuário",
            "Valor Contrato Cliente",
            "Lucro",
            "Pagamento",
            "Status",
            "NF",
        ]


        data = [headers]

        total_geral = Decimal("0.00")
        total_contrato = Decimal("0.00")
        total_lucro = Decimal("0.00")

        for item in queryset:
            agentes = item.agentes.all()
            agentes_validos = agentes_nao_carona(agentes)

            total_geral += item.total_valor_agentes
            total_contrato += item.valor_contrato or Decimal("0.00")
            total_lucro += item.lucro_total or Decimal("0.00")

            row = [
                str(item.id),
                Paragraph(str(item.cliente), cell_style),
                Paragraph(str(item.tipo_servico), cell_style),
                Paragraph(item.origem or "", cell_style),
                Paragraph(item.destino or "", cell_style),

                Paragraph(join_values(a.responsavel_agente.nome for a in agentes_validos), cell_style),
                Paragraph(join_values(str(a.agente) for a in agentes), cell_style),
                Paragraph(join_values(a.placa_agente for a in agentes_validos), cell_style),

                Paragraph(join_values(a.motorista for a in agentes_validos), cell_style),
                Paragraph(join_values(a.placa_motorista for a in agentes_validos), cell_style),

                join_values_nao_carona(a.data_solicitada.strftime("%d/%m/%Y") for a in agentes_validos if a.data_solicitada),
                join_values_nao_carona(a.horario_solicitado.strftime("%H:%M") for a in agentes_validos if a.horario_solicitado),

                join_values(a.data_inicio.strftime("%d/%m/%Y") for a in agentes_validos if a.data_inicio),
                join_values(a.horario_inicio.strftime("%H:%M") for a in agentes_validos if a.horario_inicio),

                join_values(a.data_finalizacao.strftime("%d/%m/%Y") for a in agentes_validos if a.data_finalizacao),
                join_values(a.horario_finalizacao.strftime("%H:%M") for a in agentes_validos if a.horario_finalizacao),

                join_values_nao_carona(str(a.horario_total) for a in agentes_validos if a.horario_total),
                join_values(str(a.horario_excedente) for a in agentes_validos if a.horario_excedente),

                join_values_nao_carona(str(a.km_inicio) for a in agentes_validos if a.km_inicio is not None),
                join_values_nao_carona(str(a.km_final) for a in agentes_validos if a.km_final is not None),
                join_values_nao_carona(str(a.km_total) for a in agentes_validos if a.km_total is not None),
                join_values(str(a.km_excedente) for a in agentes_validos if a.km_excedente),

                join_values(moeda(a.pedagio) for a in agentes_validos if a.pedagio),
                join_values(a.franquia.nome if a.franquia else "" for a in agentes_validos),

                join_values(moeda(a.valor_agente) for a in agentes if a.valor_agente),
                moeda(item.total_valor_agentes),

                Paragraph(item.ocorrencia or "", cell_style),
                Paragraph(item.nome_user or "", cell_style),

                moeda(item.valor_contrato) if item.valor_contrato else "",
                moeda(item.lucro_total) if item.lucro_total is not None else "",

                "Pago" if item.validar_pagamento else "",

                item.get_status_display(),

                item.nf or "",

            ]

            data.append(row)

        total_row = [""] * len(headers)
        total_row[25] = Paragraph(f"Total Geral Agentes: {moeda(total_geral)}", cell_style)
        total_row[28] = Paragraph(f"Total Contrato: {moeda(total_contrato)}",cell_style)
        total_row[29] = Paragraph(f"Total Lucro: {moeda(total_lucro)}",cell_style)
        data.append(total_row)

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),

            ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]))

        elements.append(table)
        doc.build(elements)

        buffer.seek(0)
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="faturamento_acompanhamentos.pdf"'
        return response

    def exportar_excel(self, queryset):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Acompanhamentos"

        headers = [
            "Protocolo", "Cliente", "Tipo Serviço", "Origem", "Destino",
            "Responsável", "Agente", "Placa Agente",
            "Motorista", "Placa Motorista",
            "Data Solicitada", "Hora Solicitada",
            "Data Inicial", "Hora Inicial",
            "Data Final", "Hora Final",
            "Hora Total", "Hora Excedente",
            "KM Início", "KM Final", "KM Total", "KM Excedente",
            "Pedágio", "Franquia",
            "Valor Agente(s)",
            "Total Agentes",
            "Ocorrência",
            "Usuário",
            "Valor Contrato Cliente",
            "Lucro",
            "Pagamento",
            "Status",
            "NF",

        ]


        sheet.append(headers)

        total_geral = Decimal("0.00")
        total_contrato = Decimal("0.00")
        total_lucro = Decimal("0.00")

        for item in queryset:
            agentes = item.agentes.all()
            agentes_validos = agentes_nao_carona(agentes)

            total_geral += item.total_valor_agentes or Decimal("0.00")
            total_contrato += item.valor_contrato or Decimal("0.00")
            total_lucro += item.lucro_total or Decimal("0.00")

            sheet.append([
                item.id,
                str(item.cliente),
                str(item.tipo_servico),
                item.origem,
                item.destino,

                join_values(a.responsavel_agente.nome for a in agentes_validos),
                join_values(str(a.agente) for a in agentes),
                join_values(a.placa_agente for a in agentes_validos),

                join_values(a.motorista for a in agentes_validos),
                join_values(a.placa_motorista for a in agentes_validos),

                join_values(a.data_solicitada.strftime("%d/%m/%Y") for a in agentes_validos if a.data_solicitada),
                join_values(a.horario_solicitado.strftime("%H:%M") for a in agentes_validos if a.horario_solicitado),

                join_values(a.data_inicio.strftime("%d/%m/%Y") for a in agentes_validos if a.data_inicio),
                join_values(a.horario_inicio.strftime("%H:%M") for a in agentes_validos if a.horario_inicio),

                join_values(a.data_finalizacao.strftime("%d/%m/%Y") for a in agentes_validos if a.data_finalizacao),
                join_values(a.horario_finalizacao.strftime("%H:%M") for a in agentes_validos if a.horario_finalizacao),

                join_values(str(a.horario_total) for a in agentes_validos if a.horario_total),
                join_values(str(a.horario_excedente) for a in agentes_validos if a.horario_excedente),

                join_values(str(a.km_inicio) for a in agentes_validos if a.km_inicio is not None),
                join_values(str(a.km_final) for a in agentes_validos if a.km_final is not None),
                join_values(str(a.km_total) for a in agentes_validos if a.km_total is not None),
                join_values(str(a.km_excedente) for a in agentes_validos if a.km_excedente),

                join_values(moeda(a.pedagio) for a in agentes_validos if a.pedagio),
                join_values(a.franquia.nome if a.franquia else "" for a in agentes_validos),

                join_values(moeda(a.valor_agente) for a in agentes if a.valor_agente),
                moeda(item.total_valor_agentes),

                item.ocorrencia,
                item.nome_user,

                moeda(item.valor_contrato) if item.valor_contrato else "",
                moeda(item.lucro_total) if item.lucro_total is not None else "",

                "Pago" if item.validar_pagamento else "",

                item.get_status_display(),

                item.nf or "",
            ])

            row_number = sheet.max_row

            multi_columns = [
                6, 7, 8, 9, 10,
                11, 12, 13, 14, 15, 16,
                17, 18,
                19, 20, 21, 22,
                23, 24, 25
            ]

            max_lines = 1
            for col in multi_columns:
                cell = sheet.cell(row=row_number, column=col)
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if cell.value:
                    max_lines = max(max_lines, cell.value.count("\n") + 1)

            sheet.row_dimensions[row_number].height = 15 * max_lines

        sheet.append([])

        total_row = [""] * len(headers)
        total_row[25] = f"Total Geral Agentes: {moeda(total_geral)}"
        total_row[28] = f"Total Contrato: {moeda(total_contrato)}"
        total_row[29] = f"Total Lucro: {moeda(total_lucro)}"
        sheet.append(total_row)


        last_row = sheet.max_row
        for col in range(1, len(headers) + 1):
            cell = sheet.cell(row=last_row, column=col)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color="D3D3D3",
                end_color="D3D3D3",
                fill_type="solid"
            )

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="faturamento_acompanhamentos.xlsx"'
        workbook.save(response)
        return response
    
    def exportar_excel_cliente(self, queryset):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Acompanhamentos"

        titulo_custom = next(
            (
                i.campo_personalizado_titulo.strip()
                for i in queryset
                if i.campo_personalizado_titulo and i.campo_personalizado_titulo.strip()
            ),
            " "
        )

        headers = [
            "Protocolo",
            "Cliente",
            titulo_custom,
            "Origem",
            "Destino",

            "Agente",
            "Placa Agente",
            "Motorista",
            "Placa Motorista",

            "Data Solicitada",
            "Hora Solicitada",
            "Data Inicial",
            "Hora Inicial",
            "Data Final",
            "Hora Final",

            "KM Início",
            "KM Final",
            "KM Total",

            "Franquia de Horas",
            "Hora Total",
            "Hora Excedente",
            "Valor Hora Excedente",
            "Valor Hora Excedente Total",

            "Franquia de KM",
            "KM Excedente",
            "Valor KM Excedente",
            "Valor KM Excedente Total",

            "Valor Diária",
            "Pedágio",
            "Valor Total",

            "Tipo Serviço"
        ]

        sheet.append(headers)

        from openpyxl.styles import Font, PatternFill, Alignment

        header_fill = PatternFill(
            start_color="1F4E78",
            end_color="1F4E78",
            fill_type="solid"
        )

        header_font = Font(
            color="FFFFFF",
            bold=True
        )

        header_alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )

        for col in range(1, len(headers) + 1):
            cell = sheet.cell(row=1, column=col)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment

        sheet.freeze_panes = "A2"

        total_contrato = Decimal("0.00")

        def join_values_excel(values):
            return "\n\n".join(str(v) for v in values if v)

        for item in queryset:
            agentes = item.agentes.all()

            agentes_visuais = agentes              # TODOS (inclui carona)
            agentes_validos = agentes_nao_carona(agentes)  # só principais

            total_contrato += item.valor_contrato or Decimal("0.00")

            sheet.append([
                item.id,
                str(item.cliente),
                item.campo_personalizado_valor or "",
                item.origem,
                item.destino,

                # --- AGENTES ---
                join_values_excel(str(a.agente) for a in agentes_visuais),
                join_values(a.placa_agente for a in agentes_validos),
                join_values(a.motorista for a in agentes_validos),
                join_values(a.placa_motorista for a in agentes_validos),

                join_values(a.data_solicitada.strftime("%d/%m/%Y") for a in agentes_validos if a.data_solicitada),
                join_values(a.horario_solicitado.strftime("%H:%M") for a in agentes_validos if a.horario_solicitado),

                join_values(a.data_inicio.strftime("%d/%m/%Y") for a in agentes_validos if a.data_inicio),
                join_values(a.horario_inicio.strftime("%H:%M") for a in agentes_validos if a.horario_inicio),

                join_values(a.data_finalizacao.strftime("%d/%m/%Y") for a in agentes_validos if a.data_finalizacao),
                join_values(a.horario_finalizacao.strftime("%H:%M") for a in agentes_validos if a.horario_finalizacao),

                join_values(str(a.km_inicio) for a in agentes_validos if a.km_inicio is not None),
                join_values(str(a.km_final) for a in agentes_validos if a.km_final is not None),
                join_values(str(a.km_total) for a in agentes_validos if a.km_total is not None),

                str(item.cliente.franquia_horas) if item.cliente and item.cliente.franquia_horas is not None else "",
                join_values(str(a.horario_total) for a in agentes_validos if a.horario_total),
                join_values(str(a.horario_excedente) for a in agentes_validos if a.horario_excedente),
                moeda(item.cliente.valor_horas_excedente) if item.cliente and item.cliente.valor_horas_excedente else "",
                join_values(
                    moeda(
                        (Decimal(a.horario_excedente.total_seconds()) / Decimal(3600))
                        * item.cliente.valor_horas_excedente
                    )
                    for a in agentes_validos
                    if (
                        a.horario_excedente
                        and item.cliente
                        and item.cliente.valor_horas_excedente
                    )
                ),

                str(item.cliente.franquia_km) if item.cliente and item.cliente.franquia_km is not None else "",
                join_values(str(a.km_excedente) for a in agentes_validos if a.km_excedente),
                moeda(item.cliente.valor_km_excedente) if item.cliente and item.cliente.valor_km_excedente else "",
                join_values(
                    moeda(
                        Decimal(a.km_excedente or 0) * item.cliente.valor_km_excedente
                    )
                    for a in agentes_validos
                    if item.cliente and item.cliente.valor_km_excedente and a.km_excedente
                ),

                moeda(item.cliente.valor_acionamento) if item.cliente and item.cliente.valor_acionamento else "",
                join_values(moeda(a.pedagio) for a in agentes_validos if a.pedagio),
                moeda(item.valor_contrato),

                str(item.tipo_servico),
            ])

            row_number = sheet.max_row

            multi_columns = [
                6,
                7, 8, 9, 10, 11,
                12, 13, 14, 15, 16, 17,
                18, 19,
                20, 21, 22, 23,
                24, 25, 26
            ]

            max_lines = 1
            for col in multi_columns:
                cell = sheet.cell(row=row_number, column=col)
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if cell.value:
                    max_lines = max(max_lines, cell.value.count("\n") + 1)

            sheet.row_dimensions[row_number].height = 15 * max_lines

        sheet.append([])

        total_row = [""] * len(headers)
        total_row[29] = f"TOTAL GERAL (CONTRATOS): {moeda(total_contrato)}"
        sheet.append(total_row)

        last_row = sheet.max_row
        for col in range(1, len(headers) + 1):
            cell = sheet.cell(row=last_row, column=col)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color="D3D3D3",
                end_color="D3D3D3",
                fill_type="solid"
            )

        for col in sheet.columns:
            max_length = 0
            column_letter = col[0].column_letter

            for cell in col:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))

            sheet.column_dimensions[column_letter].width = min(max_length + 2, 40)


        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="faturamento_acompanhamentos.xlsx"'
        workbook.save(response)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["franquias"] = registrodefranquia.objects.all().order_by("nome")

        context["pendentes_count"] = self.get_pendentes_queryset().count()
        
        context["status"] = self.request.GET.get("status", "")
        context["data"] = self.request.GET.get("data", "")
        context["data2"] = self.request.GET.get("data2", "")
        context["agente"] = self.request.GET.get("agente", "")
        context["cliente"] = self.request.GET.get("cliente", "")

        return context

# ACOMPANHAMENTO PANICO

class AcompanhamentoPanicoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = registroacompanhamento
    template_name = "acompanhamento_panico.html"
    context_object_name = "itens"
    permission_required = "acompanhamentos.view_registroacompanhamento"

    def get_pendentes_queryset(self):
        return registroacompanhamento.objects.filter(
            Q(tipo_servico__isnull=True) |
            Q(agentes__responsavel_agente__isnull=True) |
            Q(agentes__agente__isnull=True) |
            Q(agentes__data_solicitada__isnull=True) |
            Q(agentes__horario_solicitado__isnull=True)
        ).distinct()

    def get_queryset(self):
        qs = (
            registroacompanhamento.objects
            .prefetch_related(
                "agentes",
                "agentes__agente",
                "agentes__franquia"
            )
            .select_related("cliente")
        )

        pendente = self.request.GET.get("pendente")
        if pendente == "true":
            return self.get_pendentes_queryset().order_by("-criado_em")

        data = self.request.GET.get("data")
        data2 = self.request.GET.get("data2")
        agente = self.request.GET.get("agente")
        cliente = self.request.GET.get("cliente")
        responsavel = self.request.GET.get("responsavel")

        if data and data2:
            if data > data2:
                data, data2 = data2, data
            qs = qs.filter(agentes__data_solicitada__range=[data, data2])
        elif data:
            qs = qs.filter(agentes__data_solicitada=data)
        elif data2:
            qs = qs.filter(agentes__data_solicitada=data2)

        if agente:
            qs = qs.filter(agentes__agente__nome__icontains=agente)

        if cliente:
            qs = qs.filter(cliente__nome__icontains=cliente)

        if responsavel:
            qs = qs.filter(
                agentes__responsavel_agente_id=responsavel
            )

        return qs.distinct().order_by("-criado_em")

    def render_to_response(self, context, **response_kwargs):
        queryset = context["itens"]

        if self.request.GET.get("export") == "excel_panico":
            return self.exportar_excel_panico(queryset)
        
        if self.request.GET.get("export") == "pdf_panico":
            return self.exportar_pdf_panico(queryset)

        return super().render_to_response(context, **response_kwargs)

    def exportar_pdf_panico(self, queryset):
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=(2000, 900),
            topMargin=20,
            leftMargin=20,
            rightMargin=20,
            bottomMargin=20
        )

        elements = []

        styles = getSampleStyleSheet()
        title_style = styles["Title"]

        cell_style = ParagraphStyle(
            name="CellStyle",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            wordWrap="CJK",
            alignment=0
        )

        title = Paragraph("Relatório de Acompanhamentos - Pânico", title_style)
        title.alignment = 1
        elements.append(title)
        elements.append(Paragraph("<br/>", styles["Normal"]))

        headers = [
            "Protocolo", "Status", "Cliente", "Tipo Serviço", "Origem", "Destino",
            "Responsável Agente", "Agente", "Placa Agente",
            "Motorista", "Placa Motorista",
            "Data Solicitada", "Horário Solicitado"
        ]

        data = [headers]

        for item in queryset:
            agentes = item.agentes.all()
            agentes_validos = agentes_nao_carona(agentes)

            row = [
                str(item.id),
                item.get_status_acompanhamento_display() if hasattr(item, 'get_status_acompanhamento_display') else item.status,
                Paragraph(str(item.cliente), cell_style),
                Paragraph(str(item.tipo_servico) if item.tipo_servico else "", cell_style),
                Paragraph(item.origem or "", cell_style),
                Paragraph(item.destino or "", cell_style),

                Paragraph(
                    join_values(a.responsavel_agente.nome for a in agentes_validos if a.responsavel_agente),
                    cell_style
                ),
                Paragraph(join_values(str(a.agente) for a in agentes), cell_style),
                Paragraph(join_values(a.placa_agente for a in agentes_validos if a.placa_agente), cell_style),

                Paragraph(join_values(a.motorista for a in agentes_validos if a.motorista), cell_style),
                Paragraph(join_values(a.placa_motorista for a in agentes_validos if a.placa_motorista), cell_style),

                join_values_nao_carona(a.data_solicitada.strftime("%d/%m/%Y") for a in agentes_validos if a.data_solicitada),
                join_values_nao_carona(a.horario_solicitado.strftime("%H:%M") for a in agentes_validos if a.horario_solicitado),
            ]

            data.append(row)

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ]))

        elements.append(table)
        doc.build(elements)

        buffer.seek(0)
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="acompanhamentos_panico.pdf"'
        return response

    def exportar_excel_panico(self, queryset):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Acompanhamentos Panico"

        headers = [
            "Protocolo", "Status", "Cliente", "Tipo Serviço", "Origem", "Destino",
            "Responsável Agente", "Agente", "Placa Agente",
            "Motorista", "Placa Motorista",
            "Data Solicitada", "Horário Solicitado"
        ]

        sheet.append(headers)

        for item in queryset:
            agentes = item.agentes.all()
            agentes_validos = agentes_nao_carona(agentes)

            sheet.append([
                item.id,
                item.get_status_acompanhamento_display() if hasattr(item, 'get_status_acompanhamento_display') else item.status,
                str(item.cliente),
                str(item.tipo_servico) if item.tipo_servico else "",
                item.origem,
                item.destino,

                join_values(a.responsavel_agente.nome for a in agentes_validos if a.responsavel_agente),
                join_values(str(a.agente) for a in agentes),
                join_values(a.placa_agente for a in agentes_validos if a.placa_agente),

                join_values(a.motorista for a in agentes_validos if a.motorista),
                join_values(a.placa_motorista for a in agentes_validos if a.placa_motorista),

                join_values(a.data_solicitada.strftime("%d/%m/%Y") for a in agentes_validos if a.data_solicitada),
                join_values(a.horario_solicitado.strftime("%H:%M") for a in agentes_validos if a.horario_solicitado),
            ])

            row_number = sheet.max_row

            multi_columns = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]

            max_lines = 1
            for col in multi_columns:
                cell = sheet.cell(row=row_number, column=col)
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if cell.value:
                    max_lines = max(max_lines, cell.value.count("\n") + 1)

            sheet.row_dimensions[row_number].height = 15 * max_lines

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="acompanhamentos_panico.xlsx"'
        workbook.save(response)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        itens = context["itens"]
        for item in itens:
            # ✅ agora pega domínio e https corretos automaticamente se settings não estiverem setadas
            item.link_app = gerar_link_app_missao(item, request=self.request)

        context["nao_concluidos_count"] = registroacompanhamento.objects.exclude(
            status_acompanhamento="concluido"
        ).count()

        return context

@login_required
def acompanhamento_missao(request, pk):
    acompanhamento = get_object_or_404(registroacompanhamento, pk=pk)

    return render(
        request,
        "acompanhamento_missao.html",
        {
            "acompanhamento": acompanhamento
        }
    )

@login_required
def acompanhamento_mapa(request, pk):
    acompanhamento = get_object_or_404(registroacompanhamento, pk=pk)

    # ✅ Descobre o UUID do Supabase salvo no seu model (ajuste se necessário)
    supabase_mission_id = (
        getattr(acompanhamento, "supabase_mission_id", None)
        or getattr(acompanhamento, "mission_uuid", None)
        or getattr(acompanhamento, "supabase_id", None)
        or getattr(acompanhamento, "mission_id", None)
    )
    supabase_mission_id = str(supabase_mission_id or "")

    # Nome do agente
    agente_vinculo = acompanhamento.agentes.filter(tipo_agente="principal").first() or acompanhamento.agentes.first()
    nome_agente = agente_vinculo.agente.nome if agente_vinculo and agente_vinculo.agente else "Não atribuído"

    # Pontos iniciais do Supabase (para render inicial sem depender do JS)
    localizacoes = []
    if supabase_mission_id:
        sb = get_supabase()
        tracking_res = (
            sb.table("mission_tracking")
            .select("id,lat,lng,timestamp,created_at")
            .eq("mission_id", supabase_mission_id)
            .order("timestamp", desc=False)
            .limit(5000)
            .execute()
        )
        tracking_rows = tracking_res.data or []

        localizacoes = [
            {
                "id": r.get("id"),
                "latitude": float(r["lat"]) if r.get("lat") is not None else None,
                "longitude": float(r["lng"]) if r.get("lng") is not None else None,
                "criado_em": r.get("timestamp") or r.get("created_at"),
                "origem": getattr(acompanhamento, "origem", "") or "",
            }
            for r in tracking_rows
            if r.get("lat") is not None and r.get("lng") is not None
        ]

    return render(
        request,
        "acompanhamento_mapa.html",
        {
            "acompanhamento": acompanhamento,
            "nome_agente": nome_agente,
            "origem": getattr(acompanhamento, "origem", "") or "",
            "supabase_mission_id": supabase_mission_id,
            "localizacoes_json": json.dumps(localizacoes, cls=DjangoJSONEncoder),
        }
    )

@login_required
def acompanhamento_mapa_supabase(request, mission_id):
    """
    Renderiza o mapa usando APENAS o UUID do Supabase.
    Não depende do registroacompanhamento do Django.
    """

    sb = get_supabase()
    mission_uuid = str(mission_id)

    # 1) Buscar a missão no Supabase (pra mostrar origem/status/agente)
    mission_res = (
        sb.table("missions_control")
        .select("*")
        .eq("id", mission_uuid)
        .maybe_single()
        .execute()
    )
    mission = mission_res.data or {}

    # 2) Buscar tracking inicial (pra desenhar no load)
    tracking_res = (
        sb.table("mission_tracking")
        .select("id,lat,lng,timestamp,created_at")
        .eq("mission_id", mission_uuid)
        .order("timestamp", desc=False)
        .limit(5000)
        .execute()
    )
    tracking_rows = tracking_res.data or []

    localizacoes = [
        {
            "id": r.get("id"),
            "latitude": float(r["lat"]) if r.get("lat") is not None else None,
            "longitude": float(r["lng"]) if r.get("lng") is not None else None,
            "criado_em": r.get("timestamp") or r.get("created_at"),
            "origem": (mission.get("origem") or ""),
        }
        for r in tracking_rows
        if r.get("lat") is not None and r.get("lng") is not None
    ]

    return render(
        request,
        "acompanhamento_mapa.html",
        {
            "mission_id": mission_uuid,
            "supabase_mission_id": mission_uuid,
            "mission": mission,                         # pra aparecer no header do template
            "origem": mission.get("origem") or "-",                         # pra aparecer no header do template
            "status": mission.get("status") or "-",                         # pra aparecer no header do template
            "nome_agente": mission.get("agente") or "-",# idem
            "localizacoes_json": json.dumps(localizacoes, cls=DjangoJSONEncoder),
        }
    )

def validar_acompanhamento(request, id):
    acompanhamento = get_object_or_404(registroacompanhamento, id=id)

    acompanhamento.validar_acompanhamento = True

    acompanhamento.recalcular_financeiro()

    acompanhamento.nome_user = request.user.get_full_name() or request.user.username
    acompanhamento.save(update_fields=["validar_acompanhamento", "nome_user"])

    return redirect("acompanhamentosListFaturamento")

def validar_pagamento(request, id):
    acompanhamentos = get_object_or_404(registroacompanhamento, id=id)
    acompanhamentos.validar_pagamento = '1'
    acompanhamentos.save()
    
    return redirect('acompanhamentosListFaturamento')

def usuario_eh_faturamento_master(user):
    return user.groups.filter(name="FaturamentoMaster").exists()

@require_POST
def atualizar_status_acompanhamento(request):

    if not request.user.groups.filter(name="FaturamentoMaster").exists():
        return JsonResponse({
            "success": False,
            "error": "Sem permissão para alterar status."
        }, status=403)

    try:
        data = json.loads(request.body)

        acompanhamento = get_object_or_404(
            registroacompanhamento,
            id=data.get("acompanhamento_id")
        )

        status = data.get("status")

        if status not in dict(registroacompanhamento.STATUS_CHOICES):
            return JsonResponse({"success": False, "error": "Status inválido."})

        acompanhamento.status = status

        if status != "faturado":
            acompanhamento.nf = None

        acompanhamento.save(update_fields=["status", "nf"])

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@require_POST
def atualizar_nf_acompanhamento(request):

    if not request.user.groups.filter(name="FaturamentoMaster").exists():
        return JsonResponse({
            "success": False,
            "error": "Sem permissão para alterar NF."
        }, status=403)

    try:
        data = json.loads(request.body)

        acompanhamento = get_object_or_404(
            registroacompanhamento,
            id=data.get("acompanhamento_id")
        )

        if acompanhamento.status != "faturado":
            return JsonResponse({
                "success": False,
                "error": "NF só pode ser informada quando status for faturado."
            })

        acompanhamento.nf = data.get("nf")
        acompanhamento.save(update_fields=["nf"])

        return JsonResponse({"success": True})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

# @login_required
# @require_POST
# def atualizar_valor_contrato_cliente(request):
#     try:
#         data = json.loads(request.body)

#         acompanhamento = get_object_or_404(
#             registroacompanhamento,
#             id=data.get("acompanhamento_id")
#         )

#         valor_raw = data.get("valor_contrato_cliente")

#         if not valor_raw:
#             acompanhamento.valor_contrato = None
#             acompanhamento.lucro_total = None
#         else:
#             try:
#                 valor_contrato = Decimal(
#                     str(valor_raw)
#                     .replace(' ', '')
#                     .replace('.', '')
#                     .replace(',', '.')
#                 )
#             except InvalidOperation:
#                 return JsonResponse(
#                     {"success": False, "error": "Valor monetário inválido"},
#                     status=400
#                 )

#             acompanhamento.valor_contrato = valor_contrato

#             total_agentes = acompanhamento.total_valor_agentes or Decimal("0.00")
#             acompanhamento.lucro_total = valor_contrato - total_agentes

#         acompanhamento.save(update_fields=["valor_contrato", "lucro_total"])

#         return JsonResponse({
#             "success": True,
#             "lucro_total": f"{acompanhamento.lucro_total:.2f}" if acompanhamento.lucro_total is not None else ""
#         })

#     except Exception as e:
#         return JsonResponse(
#             {"success": False, "error": str(e)},
#             status=400
#         )

@login_required
@permission_required("acompanhamentos.change_registroacompanhamento", raise_exception=False)
def atualizar_franquia_acompanhamento(request):

    if request.method != "POST":
        return JsonResponse({"success": False}, status=405)

    data = json.loads(request.body)

    acompanhamento = get_object_or_404(
        registroacompanhamento,
        id=data.get("acompanhamento_id")
    )

    franquia = None
    franquia_id = data.get("franquia_id")

    if franquia_id:
        franquia = get_object_or_404(registrodefranquia, id=franquia_id)

    agentes_response = []

    for agente in acompanhamento.agentes.all():
        agente.franquia = franquia
        agente.save()  # dispara save() → recalcula tudo

        agentes_response.append({
            "horario_excedente": str(agente.horario_excedente) if agente.horario_excedente else "—",
            "km_excedente": agente.km_excedente if agente.km_excedente and agente.km_excedente > 0 else "—",
            "valor_agente": f"R$ {agente.valor_agente:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                if agente.valor_agente else "—",
        })

    # Só recalcula financeiro se já estiver validado
    if acompanhamento.validar_acompanhamento:
        acompanhamento.recalcular_financeiro()
    acompanhamento.nome_user = request.user.get_full_name() or request.user.username
    acompanhamento.save(update_fields=["nome_user"])

    return JsonResponse({
        "success": True,
        "agentes": agentes_response,
        "total": acompanhamento.total_valor_agentes_formatado,
        "usuario": acompanhamento.nome_user,
    })

def format_decimal(value):
    if value is None:
        return ""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ------------------------------------------------------
#               ACOMPANHAMENTO DASHBOARD
# ------------------------------------------------------
class AcompanhamentoDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "acompanhamento_dashboard.html"
    permission_required = "acompanhamentos.view_listacompanhamento"

@login_required
def acompanhamento_dashboard_data(request):

    periodo = request.GET.get('periodo', 'mensal')
    hoje = timezone.now()

    if periodo == 'semanal':
        data_inicio = hoje - timedelta(days=7)
    elif periodo == 'quinzenal':
        data_inicio = hoje - timedelta(days=15)
    else:
        data_inicio = hoje - timedelta(days=30)

    dados = (
        registrodeacompanhamento.objects
        .filter(criado_em__gte=data_inicio)
        .exclude(cliente__isnull=True)
        .exclude(cliente="")
        .exclude(cliente__icontains="teste")
        .values('cliente')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )

    return JsonResponse({
        'labels': [d['cliente'] for d in dados],
        'valores': [d['total'] for d in dados],
    })

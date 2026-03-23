# acompanhamentos/api_views.py

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Count, Sum, F
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncDate
from decimal import Decimal
from django.utils.dateparse import parse_date
from django.db.models import Q
from .models import Cliente, TipoServico, RequisicaoSolicitacao, FranquiaAgente, Missao, registroacompanhamento, registroacompanhamentoagente

def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ("1", "true", "t", "yes", "y", "sim")

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def callback_acompanhamento_aprovado(request):
    data = request.data

    try:
        requisicao_id_externo = data.get("requisicao_id_externo")
        aprovado = _to_bool(data.get("aprovado", True))

        if not requisicao_id_externo:
            return Response(
                {"success": False, "error": "requisicao_id_externo é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = registroacompanhamento.objects.filter(
            requisicao_solicitacao__requisicao_id_externo=int(requisicao_id_externo)
        )

        if not qs.exists():
            return Response(
                {
                    "success": False,
                    "error": f"Nenhum acompanhamento no INT encontrado para requisicao_id_externo={requisicao_id_externo}",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        updated = qs.update(validado_cliente=aprovado)

        return Response(
            {
                "success": True,
                "requisicao_id_externo": int(requisicao_id_externo),
                "aprovado": aprovado,
                "updated": updated,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def sync_cliente(request):
    """Recebe e sincroniza um Cliente do GSAcionamento"""
    data = request.data
    
    try:
        cliente, created = Cliente.objects.update_or_create(
            id_externo=data.get('id_externo'),
            defaults={
                'nome': data.get('nome'),
                'cnpj': data.get('cnpj'),
                'tipo_cadastro': data.get('tipo_cadastro') or None,
                'email': data.get('email', ''),
                'ativo': data.get('ativo', True),

                "comercial": data.get("comercial_nome") or "",
            }
        )
        
        return Response({
            'success': True,
            'message': 'Cliente sincronizado com sucesso',
            'id': cliente.id,
            'id_externo': cliente.id_externo,
            'created': created
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def sync_tipo_servico(request):
    """Recebe e sincroniza um TipoServico do GSAcionamento"""
    data = request.data
    
    try:
        # Busca o cliente pelo id_externo
        cliente = Cliente.objects.get(id_externo=data.get('cliente_id_externo'))
        
        tipo_servico, created = TipoServico.objects.update_or_create(
            id_externo=data.get('id_externo'),
            defaults={
                'cliente': cliente,
                'codigo': data.get('codigo'),
                'ativo': data.get('ativo', True),
                'tipo_cadastro': data.get('tipo_cadastro', '') or None,
                'valor_acionamento': data.get('valor_acionamento', 0),
                'franquia_km': data.get('franquia_km', 0),
                'franquia_horas': data.get('franquia_horas', 0),
                'valor_hora': data.get('valor_hora'),
                'valor_km': data.get('valor_km'),
            }
        )
        
        return Response({
            'success': True,
            'message': 'Tipo de Serviço sincronizado com sucesso',
            'id': tipo_servico.id,
            'id_externo': tipo_servico.id_externo,
            'created': created
        }, status=status.HTTP_200_OK)
        
    except Cliente.DoesNotExist:
        return Response({
            'success': False,
            'error': f"Cliente com id_externo={data.get('cliente_id_externo')} não encontrado"
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def sync_requisicao(request):
    data = request.data

    try:
        cliente = Cliente.objects.get(id_externo=data.get('cliente_id_externo'))
        tipo_servico = TipoServico.objects.get(id_externo=data.get('tipo_servico_id_externo'))

        # Busca a missão
        missao_id_externo = data.get('missao_id_externo')
        missao = None
        if missao_id_externo:
            try:
                missao = Missao.objects.get(id_externo=missao_id_externo)
            except Missao.DoesNotExist:
                return Response({
                    'success': False,
                    'error': f"Missão com id_externo={missao_id_externo} não encontrada. Sincronize a missão primeiro."
                }, status=status.HTTP_400_BAD_REQUEST)

        comboio = bool(data.get("comboio", False))
        qtd_raw = data.get("quantidade_veiculos_comboio")
        qtd = int(qtd_raw) if str(qtd_raw).strip() not in ("", "None", "null") else None

        if comboio and not qtd:
            return Response({
                "success": False,
                "error": "comboio=True exige quantidade_veiculos_comboio >= 1"
            }, status=status.HTTP_400_BAD_REQUEST)

        requisicao, created = RequisicaoSolicitacao.objects.update_or_create(
            id_externo=data.get('id_externo'),  # PK do AgenteVeiculo
            defaults={
                'requisicao_id_externo': data.get('requisicao_id_externo'),
                'cliente': cliente,
                'missao': missao,
                'tipo_servico': tipo_servico,
                'campo_personalizado_titulo': data.get('campo_personalizado_titulo', ''),
                'campo_personalizado_valor': data.get('campo_personalizado_valor', ''),
                'ocorrencia': data.get('observacoes', ''),
                'origem': data.get('origem'),
                'latitude_origem': data.get('latitude_origem'),
                'longitude_origem': data.get('longitude_origem'),
                'destino': data.get('destino', ''),
                'motorista': data.get('motorista'),
                'numero_motorista': data.get('numero_motorista'),
                'placa': data.get('placa'),
                'agente': data.get('agente', ''),
                'placa_agente': data.get('placa_agente', ''),
                'data_agendamento': data.get('data_agendamento'),
                'horario_agendamento': data.get('horario_agendamento'),
                'nome_user': data.get('nome_user', ''),
                "comboio": comboio,
                "quantidade_veiculos_comboio": qtd,
                'sincronizado_em': timezone.now(),

                'is_reuso': bool(data.get('is_reuso', False)),
                'agente_nome_reuso': data.get('agente_nome_reuso', '') or '',
                'agente_placa_reuso': data.get('agente_placa_reuso', '') or '',
            }
        )

        return Response({
            'success': True,
            'message': 'Requisição sincronizada com sucesso',
            'id': requisicao.id,
            'id_externo': requisicao.id_externo,
            'missao_id': missao.id if missao else None,
            'created': created
        }, status=status.HTTP_200_OK)

    except Cliente.DoesNotExist:
        return Response({
            'success': False,
            'error': f"Cliente com id_externo={data.get('cliente_id_externo')} não encontrado"
        }, status=status.HTTP_400_BAD_REQUEST)
    except TipoServico.DoesNotExist:
        return Response({
            'success': False,
            'error': f"TipoServico com id_externo={data.get('tipo_servico_id_externo')} não encontrado"
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def sync_franquia(request):
    """Recebe e sincroniza uma FranquiaAgente do GSAcionamento"""
    data = request.data

    try:
        id_externo = data.get('id_externo')

        if not id_externo:
            return Response({
                'success': False,
                'error': 'id_externo é obrigatório'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Se veio flag de exclusão
        if data.get('deleted'):
            deleted_count, _ = FranquiaAgente.objects.filter(
                id_externo=id_externo
            ).delete()

            return Response({
                'success': True,
                'message': f'Franquia {id_externo} excluída' if deleted_count else 'Franquia não encontrada (já excluída)',
                'deleted': deleted_count > 0,
            }, status=status.HTTP_200_OK)

        # Cria ou atualiza
        franquia, created = FranquiaAgente.objects.update_or_create(
            id_externo=id_externo,
            defaults={
                'nome': data.get('nome', ''),
                'valor_acionamento': data.get('valor_acionamento'),
                'franquia_km': data.get('franquia_km'),
                'franquia_horas': data.get('franquia_horas'),
                'valor_km_excedente': data.get('valor_km_excedente'),
                'valor_horas_excedente': data.get('valor_horas_excedente'),
                'nome_user': data.get('nome_user', ''),
            }
        )

        return Response({
            'success': True,
            'message': 'Franquia sincronizada com sucesso',
            'id': franquia.id,
            'id_externo': franquia.id_externo,
            'created': created,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def sync_missao(request):
    data = request.data

    try:
        id_externo = data.get('id_externo')

        if not id_externo:
            return Response({
                'success': False,
                'error': 'id_externo é obrigatório'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Busca o cliente pelo id_externo
        cliente = Cliente.objects.get(id_externo=data.get('cliente_id_externo'))

        missao, created = Missao.objects.update_or_create(
            id_externo=id_externo,
            defaults={
                'cliente': cliente,
                'nome': data.get('nome', ''),
                'status': data.get('status', 'ativa'),
                'criado_por': data.get('criado_por', ''),
            }
        )

        return Response({
            'success': True,
            'message': 'Missão sincronizada com sucesso',
            'id': missao.id,
            'id_externo': missao.id_externo,
            'created': created,
        }, status=status.HTTP_200_OK)

    except Cliente.DoesNotExist:
        return Response({
            'success': False,
            'error': f"Cliente com id_externo={data.get('cliente_id_externo')} não encontrado"
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_lucro_total_por_dia(request):
    dt_ini_raw = (request.GET.get("dt_ini") or "").strip()
    dt_fim_raw = (request.GET.get("dt_fim") or "").strip()
    somente_concluidos = (request.GET.get("somente_concluidos") or "true").strip().lower() != "false"

    dt_ini = parse_date(dt_ini_raw) if dt_ini_raw else None
    dt_fim = parse_date(dt_fim_raw) if dt_fim_raw else None

    qs = registroacompanhamento.objects.exclude(lucro_total__isnull=True)

    if somente_concluidos:
        qs = qs.filter(status_acompanhamento="verificado")

    if dt_ini and dt_fim:
        qs = qs.filter(criado_em__date__range=(dt_ini, dt_fim))
    elif dt_ini:
        qs = qs.filter(criado_em__date__gte=dt_ini)
    elif dt_fim:
        qs = qs.filter(criado_em__date__lte=dt_fim)

    rows = (
        qs.annotate(dia=TruncDate("criado_em"))
          .values("dia")
          .annotate(total=Sum("lucro_total"))
          .order_by("dia")
    )

    labels = []
    values = []
    total_geral = 0.0

    for r in rows:
        dia = r.get("dia")
        total = r.get("total") or 0
        labels.append(dia.strftime("%d/%m/%Y") if dia else "")
        values.append(float(total))
        total_geral += float(total)

    return Response({
        "labels": labels,
        "values": values,
        "total_geral": total_geral,
    })

@api_view(["GET"])
def api_top_clientes_pagadores(request):
    dt_ini_raw = (request.GET.get("dt_ini") or "").strip()
    dt_fim_raw = (request.GET.get("dt_fim") or "").strip()
    limit_raw = (request.GET.get("limit") or "10").strip()

    somente_concluidos = (request.GET.get("somente_concluidos") or "true").strip().lower() in ("1", "true", "sim", "yes")
    somente_validados = (request.GET.get("somente_validados") or "true").strip().lower() in ("1", "true", "sim", "yes")

    dt_ini = parse_date(dt_ini_raw) if dt_ini_raw else None
    dt_fim = parse_date(dt_fim_raw) if dt_fim_raw else None

    try:
        limit = max(1, min(int(limit_raw), 50))
    except ValueError:
        limit = 10

    qs = (
        registroacompanhamento.objects
        .select_related("cliente")
        .exclude(cliente__isnull=True)
        .exclude(valor_contrato__isnull=True)
    )

    if somente_concluidos:
        qs = qs.filter(status_acompanhamento="verificado")

    if somente_validados:
        qs = qs.filter(validar_acompanhamento=True)

    if dt_ini and dt_fim:
        qs = qs.filter(criado_em__date__range=(dt_ini, dt_fim))
    elif dt_ini:
        qs = qs.filter(criado_em__date__gte=dt_ini)
    elif dt_fim:
        qs = qs.filter(criado_em__date__lte=dt_fim)

    rows = (
        qs.values("cliente__nome")
        .annotate(
            # soma do que foi cobrado do cliente
            total_contrato=Coalesce(Sum("valor_contrato"), Decimal("0.00")),

            # soma do que foi pago para agentes (somente principais, exclui carona)
            total_agentes=Coalesce(
                Sum(
                    "agentes__valor_agente",
                    filter=~Q(agentes__tipo_agente="carona")
                ),
                Decimal("0.00")
            )
        )
    )

    # Agora calcula o líquido (python) e ordena
    data = []
    for r in rows:
        contrato = r["total_contrato"] or Decimal("0.00")
        agentes = r["total_agentes"] or Decimal("0.00")
        liquido = contrato - agentes
        data.append({
            "cliente": r["cliente__nome"],
            "liquido": liquido,
        })

    data.sort(key=lambda x: x["liquido"], reverse=True)
    data = data[:limit]

    labels = [d["cliente"] for d in data]
    values = [float(d["liquido"]) for d in data]
    total_geral = float(sum((d["liquido"] for d in data), Decimal("0.00")))

    return Response({
        "labels": labels,
        "values": values,
        "total_geral": total_geral,
    })


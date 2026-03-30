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
from django.utils.dateparse import parse_date, parse_time
from django.db.models import Q
from .models import Cliente, TipoServico, RequisicaoSolicitacao, FranquiaAgente, Missao, registroacompanhamento, registroacompanhamentoagente

def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ("1", "true", "t", "yes", "y", "sim")


def _to_int(value, default=None, min_value=None):
    if value in (None, "", "None", "null"):
        return default

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if min_value is not None and parsed < min_value:
        return default

    return parsed


def _to_decimal(value, default=None):
    if value in (None, "", "None", "null"):
        return default

    try:
        return Decimal(str(value))
    except Exception:
        return default


def _resolve_tipo_servico_for_franquia(data):
    """
    Resolve TipoServico vinculado a franquia com prioridade por id_externo.
    Fallback: cliente_id_externo + codigo (+ nome_variacao, quando vier).
    """
    # 1) Via id_externo direto (principal)
    tipo_servico_id_externo = _to_int(data.get('tipo_servico_id_externo'), default=None)
    if tipo_servico_id_externo is not None:
        ts = TipoServico.objects.filter(id_externo=tipo_servico_id_externo).first()
        if ts:
            return ts

    # 2) Fallback por codigo/cliente/variacao
    codigo = (data.get('tipo_servico_codigo') or '').strip()
    nome_variacao = data.get('tipo_servico_nome_variacao')
    cliente_id_externo = _to_int(data.get('cliente_id_externo'), default=None)

    if not codigo:
        return None

    qs = TipoServico.objects.filter(codigo=codigo)

    if cliente_id_externo is not None:
        qs = qs.filter(cliente__id_externo=cliente_id_externo)

    if nome_variacao not in (None, ''):
        qs = qs.filter(nome_variacao=nome_variacao)

    return qs.order_by('id').first()


def _resolve_cliente_for_franquia(data, tipo_servico=None):
    """
    Resolve Cliente vinculado a franquia.
    Prioridade: cliente_id_externo do payload; fallback para cliente do tipo_servico.
    """
    cliente_id_externo = _to_int(data.get('cliente_id_externo'), default=None)

    if cliente_id_externo is not None:
        return Cliente.objects.filter(id_externo=cliente_id_externo).first()

    if tipo_servico is not None:
        return tipo_servico.cliente

    return None

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
                'ativo': _to_bool(data.get('ativo', True)),
                'permite_comboio': _to_bool(data.get('permite_comboio', False)),
                'max_veiculos_comboio': _to_int(data.get('max_veiculos_comboio'), default=1, min_value=1) or 1,
                'reutilizar_franquia': _to_bool(data.get('reutilizar_franquia', False)),

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
                'ativo': _to_bool(data.get('ativo', True)),
                'tipo_cadastro': data.get('tipo_cadastro', '') or None,
                'nome_variacao': data.get('nome_variacao') or None,
                'valor_acionamento': _to_decimal(data.get('valor_acionamento'), default=Decimal('0.00')),
                'franquia_km': _to_decimal(data.get('franquia_km'), default=Decimal('0.00')),
                'franquia_horas': _to_decimal(data.get('franquia_horas'), default=Decimal('0.00')),
                'valor_hora': _to_decimal(data.get('valor_hora'), default=None),
                'valor_km': _to_decimal(data.get('valor_km'), default=None),
                'lat_origem': _to_decimal(data.get('lat_origem'), default=None),
                'long_origem': _to_decimal(data.get('long_origem'), default=None),
                'lat_destino': _to_decimal(data.get('lat_destino'), default=None),
                'long_destino': _to_decimal(data.get('long_destino'), default=None),
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

        comboio = _to_bool(data.get("comboio", False))
        qtd_raw = data.get("quantidade_veiculos_comboio")
        qtd = _to_int(qtd_raw, default=None, min_value=1)

        data_agendamento = parse_date((data.get('data_agendamento') or '').strip())
        horario_agendamento = parse_time((data.get('horario_agendamento') or '').strip())

        if not data_agendamento:
            return Response({
                "success": False,
                "error": "data_agendamento inválida ou ausente"
            }, status=status.HTTP_400_BAD_REQUEST)

        if not horario_agendamento:
            return Response({
                "success": False,
                "error": "horario_agendamento inválido ou ausente"
            }, status=status.HTTP_400_BAD_REQUEST)

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
                'origem': data.get('origem') or '',
                'latitude_origem': _to_decimal(data.get('latitude_origem'), default=None),
                'longitude_origem': _to_decimal(data.get('longitude_origem'), default=None),
                'origem_2': data.get('origem_2') or '',
                'latitude_origem_2': _to_decimal(data.get('latitude_origem_2'), default=None),
                'longitude_origem_2': _to_decimal(data.get('longitude_origem_2'), default=None),
                'origem_3': data.get('origem_3') or '',
                'latitude_origem_3': _to_decimal(data.get('latitude_origem_3'), default=None),
                'longitude_origem_3': _to_decimal(data.get('longitude_origem_3'), default=None),
                'destino': data.get('destino', ''),
                'latitude_destino': _to_decimal(data.get('latitude_destino'), default=None),
                'longitude_destino': _to_decimal(data.get('longitude_destino'), default=None),
                'destino_2': data.get('destino_2', ''),
                'latitude_destino_2': _to_decimal(data.get('latitude_destino_2'), default=None),
                'longitude_destino_2': _to_decimal(data.get('longitude_destino_2'), default=None),
                'destino_3': data.get('destino_3', ''),
                'latitude_destino_3': _to_decimal(data.get('latitude_destino_3'), default=None),
                'longitude_destino_3': _to_decimal(data.get('longitude_destino_3'), default=None),
                'motorista': data.get('motorista') or '',
                'numero_motorista': data.get('numero_motorista') or '',
                'placa': data.get('placa') or '',
                'agente': data.get('agente', ''),
                'placa_agente': data.get('placa_agente', ''),
                'data_agendamento': data_agendamento,
                'horario_agendamento': horario_agendamento,
                'nome_user': data.get('nome_user', ''),
                "comboio": comboio,
                "quantidade_veiculos_comboio": qtd,
                'sincronizado_em': timezone.now(),

                'is_reuso': _to_bool(data.get('is_reuso', False)),
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
        if _to_bool(data.get('deleted')):
            deleted_count, _ = FranquiaAgente.objects.filter(
                id_externo=id_externo
            ).delete()

            return Response({
                'success': True,
                'message': f'Franquia {id_externo} excluída' if deleted_count else 'Franquia não encontrada (já excluída)',
                'deleted': deleted_count > 0,
            }, status=status.HTTP_200_OK)

        tipo_servico = _resolve_tipo_servico_for_franquia(data)
        cliente = _resolve_cliente_for_franquia(data, tipo_servico=tipo_servico)

        # Se payload trouxe referência de tipo_servico mas não encontrou no INT, retorna erro claro
        referencia_tipo_enviada = any([
            data.get('tipo_servico_id_externo') not in (None, ''),
            data.get('tipo_servico_codigo') not in (None, ''),
            data.get('tipo_servico_nome_variacao') not in (None, ''),
        ])

        if referencia_tipo_enviada and tipo_servico is None:
            return Response({
                'success': False,
                'error': 'TipoServico vinculado a franquia não encontrado no Sistema Interno.',
                'detalhes': {
                    'tipo_servico_id_externo': data.get('tipo_servico_id_externo'),
                    'cliente_id_externo': data.get('cliente_id_externo'),
                    'tipo_servico_codigo': data.get('tipo_servico_codigo'),
                    'tipo_servico_nome_variacao': data.get('tipo_servico_nome_variacao'),
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        if data.get('cliente_id_externo') not in (None, '') and cliente is None:
            return Response({
                'success': False,
                'error': 'Cliente vinculado a franquia não encontrado no Sistema Interno.',
                'detalhes': {
                    'cliente_id_externo': data.get('cliente_id_externo'),
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        defaults = {
            'nome': data.get('nome', ''),
            'valor_acionamento': _to_decimal(data.get('valor_acionamento'), default=Decimal('0.00')),
            'franquia_km': _to_int(data.get('franquia_km'), default=None, min_value=0),
            'franquia_horas': _to_int(data.get('franquia_horas'), default=None, min_value=0),
            'valor_km_excedente': _to_decimal(data.get('valor_km_excedente'), default=Decimal('0.00')),
            'valor_horas_excedente': _to_decimal(data.get('valor_horas_excedente'), default=Decimal('0.00')),
            'nome_user': data.get('nome_user', ''),
        }

        if cliente is not None:
            defaults['cliente'] = cliente

        # Só atualiza o vínculo se o tipo_servico tiver sido resolvido.
        if tipo_servico is not None:
            defaults['tipo_servico'] = tipo_servico

        # Cria ou atualiza
        franquia, created = FranquiaAgente.objects.update_or_create(
            id_externo=id_externo,
            defaults=defaults
        )

        return Response({
            'success': True,
            'message': 'Franquia sincronizada com sucesso',
            'id': franquia.id,
            'id_externo': franquia.id_externo,
            'cliente_id': franquia.cliente_id,
            'tipo_servico_id': franquia.tipo_servico_id,
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


# acompanhamentos/api_views.py

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from .models import Cliente, TipoServico, RequisicaoSolicitacao, FranquiaAgente


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
                'email': data.get('email', ''),
                'ativo': data.get('ativo', True),
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
    """Recebe e sincroniza uma Requisição do GSAcionamento"""
    data = request.data
    
    try:
        cliente = Cliente.objects.get(id_externo=data.get('cliente_id_externo'))
        tipo_servico = TipoServico.objects.get(id_externo=data.get('tipo_servico_id_externo'))
        
        requisicao, created = RequisicaoSolicitacao.objects.update_or_create(
            id_externo=data.get('id_externo'),
            defaults={
                'cliente': cliente,
                'tipo_servico': tipo_servico,
                'campo_personalizado_titulo': data.get('campo_personalizado_titulo', ''),
                'campo_personalizado_valor': data.get('campo_personalizado_valor', ''),
                'origem': data.get('origem'),
                'latitude_origem': data.get('latitude_origem'),
                'longitude_origem': data.get('longitude_origem'),
                'destino': data.get('destino', ''),
                'motorista': data.get('motorista'),
                'placa': data.get('placa'),
                'data_agendamento': data.get('data_agendamento'),
                'horario_agendamento': data.get('horario_agendamento'),
                'nome_user': data.get('nome_user', ''),
                'sincronizado_em': timezone.now(),
            }
        )
        
        return Response({
            'success': True,
            'message': 'Requisição sincronizada com sucesso',
            'id': requisicao.id,
            'id_externo': requisicao.id_externo,
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
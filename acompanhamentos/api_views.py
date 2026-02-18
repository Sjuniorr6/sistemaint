from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    ClienteSerializer, 
    TipoServicoSerializer, 
    RequisicaoSolicitacaoSerializer
)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def sync_cliente(request):
    """Recebe e sincroniza um Cliente do GSAcionamento"""
    serializer = ClienteSerializer(data=request.data)
    if serializer.is_valid():
        cliente = serializer.save()
        return Response({
            'success': True,
            'message': 'Cliente sincronizado com sucesso',
            'id': cliente.id,
            'id_externo': cliente.id_externo
        }, status=status.HTTP_200_OK)
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def sync_tipo_servico(request):
    """Recebe e sincroniza um TipoServico do GSAcionamento"""
    serializer = TipoServicoSerializer(data=request.data)
    if serializer.is_valid():
        tipo_servico = serializer.save()
        return Response({
            'success': True,
            'message': 'Tipo de Serviço sincronizado com sucesso',
            'id': tipo_servico.id,
            'id_externo': tipo_servico.id_externo
        }, status=status.HTTP_200_OK)
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def sync_requisicao(request):
    """Recebe e sincroniza uma Requisição do GSAcionamento"""
    serializer = RequisicaoSolicitacaoSerializer(data=request.data)
    if serializer.is_valid():
        requisicao = serializer.save()
        return Response({
            'success': True,
            'message': 'Requisição sincronizada com sucesso',
            'id': requisicao.id,
            'id_externo': requisicao.id_externo
        }, status=status.HTTP_200_OK)
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)
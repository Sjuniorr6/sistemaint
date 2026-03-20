from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from .models import GridInternacional
from .serializers import GridInternacionalUpdateSerializer


class GridInternacionalUpdateAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, id_planilha):
        objeto = GridInternacional.objects.filter(
            id_planilha=id_planilha,
            status_operacao='Estoque Cliente'
        ).order_by('-id').first()

        if not objeto:
            return Response(
                {'error': 'Registro com status "Estoque Cliente" não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = GridInternacionalUpdateSerializer(objeto)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, id_planilha):
        objeto = GridInternacional.objects.filter(
            id_planilha=id_planilha,
            status_operacao='Estoque Cliente'
        ).order_by('-id').first()

        if not objeto:
            return Response(
                {'error': 'Registro com status "Estoque Cliente" não encontrado para atualização'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = GridInternacionalUpdateSerializer(objeto, data=request.data, partial=True)

        if serializer.is_valid():
            equipamento = serializer.save()
            return Response({
                'success': True,
                'updated': True,
                'data': GridInternacionalUpdateSerializer(equipamento).data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
from rest_framework import serializers
from .models import Cliente, TipoServico, RequisicaoSolicitacao


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = [
            'id', 'id_externo', 'nome', 'cnpj', 'email', 'ativo'
        ]
    
    def create(self, validated_data):
        id_externo = validated_data.get('id_externo')
        cliente, created = Cliente.objects.update_or_create(
            id_externo=id_externo,
            defaults=validated_data
        )
        return cliente


class TipoServicoSerializer(serializers.ModelSerializer):
    cliente_id_externo = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = TipoServico
        fields = [
            'id', 'id_externo', 'cliente_id_externo', 'codigo', 'ativo',
            'valor_acionamento', 'franquia_km', 'franquia_horas',
            'valor_hora', 'valor_km'
        ]
    
    def create(self, validated_data):
        cliente_id_externo = validated_data.pop('cliente_id_externo')
        
        try:
            cliente = Cliente.objects.get(id_externo=cliente_id_externo)
        except Cliente.DoesNotExist:
            raise serializers.ValidationError(
                f"Cliente com id_externo={cliente_id_externo} não encontrado"
            )
        
        id_externo = validated_data.get('id_externo')
        tipo_servico, created = TipoServico.objects.update_or_create(
            id_externo=id_externo,
            defaults={**validated_data, 'cliente': cliente}
        )
        return tipo_servico


class RequisicaoSolicitacaoSerializer(serializers.ModelSerializer):
    cliente_id_externo = serializers.IntegerField(write_only=True)
    tipo_servico_id_externo = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = RequisicaoSolicitacao
        fields = [
            'id', 'id_externo', 'cliente_id_externo', 'tipo_servico_id_externo',
            'campo_personalizado_titulo', 'campo_personalizado_valor',
            'origem', 'latitude_origem', 'longitude_origem', 'destino',
            'motorista', 'placa', 'data_agendamento', 'horario_agendamento',
            'ocorrencia', 'nome_user'
        ]
    
    def create(self, validated_data):
        cliente_id_externo = validated_data.pop('cliente_id_externo')
        tipo_servico_id_externo = validated_data.pop('tipo_servico_id_externo')
        
        try:
            cliente = Cliente.objects.get(id_externo=cliente_id_externo)
        except Cliente.DoesNotExist:
            raise serializers.ValidationError(
                f"Cliente com id_externo={cliente_id_externo} não encontrado"
            )
        
        try:
            tipo_servico = TipoServico.objects.get(id_externo=tipo_servico_id_externo)
        except TipoServico.DoesNotExist:
            raise serializers.ValidationError(
                f"TipoServico com id_externo={tipo_servico_id_externo} não encontrado"
            )
        
        id_externo = validated_data.get('id_externo')
        
        if id_externo:
            requisicao, created = RequisicaoSolicitacao.objects.update_or_create(
                id_externo=id_externo,
                defaults={
                    **validated_data,
                    'cliente': cliente,
                    'tipo_servico': tipo_servico
                }
            )
        else:
            requisicao = RequisicaoSolicitacao.objects.create(
                cliente=cliente,
                tipo_servico=tipo_servico,
                **validated_data
            )
        
        return requisicao
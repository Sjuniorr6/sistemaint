# models.py
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import timedelta # Necessário para calcular_slas
import requests

class GridInternacional(models.Model):
    STATUS_CHOICES = [
        ('Aguardando Liberação RFB', 'Aguardando Liberação RFB'),
        ('Aguardando Chegada na Base', 'Aguardando Chegada na Base'),
        ('Aguardando Coleta', 'Aguardando Coleta'),
        ('Aguardando Embarque Internacional', 'Aguardando Embarque Internacional'),
        ('Em reversa para o Brasil', 'Em reversa para o Brasil'),
        ('Retirado, Ag. Envio', 'Retirado, Ag. Envio'),
        ('Em viagem', 'Em viagem'),
        ('No destino', 'No destino'),
        ('Estoque Cliente', 'Estoque Cliente'),
        ('Danificado', 'Danificado'),
        ('Extraviado', 'Extraviado'),
        ('Reversa Finalizada', 'Reversa Finalizada'),
        ('Equipamento na Base', 'Equipamento na Base'),
        ('Fora de Operação', 'Fora de Operação'),
        
    ]

    id = models.BigAutoField(primary_key=True) 
    data_envio                  = models.DateField("Data de Envio", null=True, blank=True)
    requisicao                  = models.CharField("Requisição", max_length=255, null=True, blank=True)
    cliente                     = models.CharField("Cliente", max_length=255, null=True, blank=True)
    local_de_entrega            = models.CharField("Local de Entrega", max_length=255, null=True, blank=True)
    modelo                      = models.CharField("Modelo", max_length=255, null=True, blank=True)
    id_planilha                 = models.CharField("ID", max_length=255, null=True, blank=True)
    ccid                        = models.CharField("CCID", max_length=255, null=True, blank=True)
    sla_insercao                = models.CharField("SLA de Inserção", max_length=255, null=True, blank=True)
    data_insercao               = models.DateField("Data / Inserção", null=True, blank=True)
    destino                     = models.CharField("Destino", max_length=255, null=True, blank=True)
    bl                          = models.CharField("BL", max_length=255, null=True, blank=True)
    container                   = models.CharField("Container", max_length=255, null=True, blank=True)
    sla_viagem                  = models.CharField("SLA de Viagem", max_length=255, null=True, blank=True)
    data_chegada_destino        = models.DateField("Data / Chegada no Destino", null=True, blank=True)
    sla_retirada                = models.CharField("SLA de Retirada", max_length=255, null=True, blank=True)
    data_retirada               = models.DateField("Data / Retirada", null=True, blank=True)
    sla_envio_brasil            = models.CharField("SLA / Envio ao Brasil", max_length=255, null=True, blank=True)
    data_envio_brasil           = models.DateField("Data / Envio ao Brasil", null=True, blank=True)
    sla_chegada_brasil          = models.CharField("SLA / Chegada ao Brasil", max_length=255, null=True, blank=True)
    data_brasil                 = models.DateField("Data / Brasil", null=True, blank=True)
    status_operacao             = models.CharField("Status / Operação", max_length=255, null=True, blank=True, choices=STATUS_CHOICES)
    sla_operacao                = models.CharField("SLA da Operação", max_length=255, null=True, blank=True)
    reposicao                   = models.CharField("Reposição", max_length=255, null=True, blank=True)
    observacao                  = models.TextField("Observação", null=True, blank=True)
    data_chegada_porto          = models.DateField("Data / Chegada no Porto", null=True, blank=True)
    data_embarque_maritimo      = models.DateField("Data / Embarque Marítimo", null=True, blank=True)
    data_desembarque_maritimo   = models.DateField("Data / Desembarque Marítimo", null=True, blank=True)
    data_envoice                = models.DateField("Data / envoice", null=True, blank=True)
    data_chegada_terminal       = models.DateField("Data / Chegada no Terminal", null=True, blank=True)
    data_saida_terminal         = models.DateField("Data / Saída do Terminal", null=True, blank=True)
    sla_porto_nacional          = models.CharField("SLA Porto Nacional", max_length=255, null=True, blank=True)
    sla_terrestre               = models.CharField("SLA Terrestre", max_length=255, null=True, blank=True)
    sla_maritimo                = models.CharField("SLA Marítimo", max_length=255, null=True, blank=True)
    sla_terminal_internacional  = models.CharField("SLA Terminal Internacional", max_length=255, null=True, blank=True)
    sla_terrestre_internacional = models.CharField("SLA Terrestre Internacional", max_length=255, null=True, blank=True)
    local                       = models.CharField("Local", max_length=255, null=True, blank=True)
    status_container            = models.CharField("Status do Container", max_length=255, null=True, blank=True)
    data_desembarque            = models.DateField("Data do Desembarque", null=True, blank=True)
    sla_internacional           = models.CharField("SLA Internacional", max_length=255, null=True, blank=True)
    rf_invoice                  = models.CharField("RF Invoice", max_length=255, null=True, blank=True)
    data_envoice                = models.DateField("Data / envoice", null=True, blank=True)
    coleta                      = models.DateField("Coleta", null=True, blank=True)
    liberacao                  = models.DateField("Liberacao", null=True, blank=True)
    golden_sat                  = models.DateField("GoldenSat", null=True, blank=True)
    sla_destino                 = models.CharField("SLA Destino", max_length=255, null=True, blank=True)
   

    def __str__(self):
        return f"{self.cliente} — {self.container or 'sem container'}"

    def calcular_slas(self):
        def diff_days(a, b):
            if a and b:
                return (a - b).days
            return ''
        self.sla_insercao = diff_days(self.data_insercao, self.data_envio)
        self.sla_viagem = diff_days(self.data_chegada_destino, self.data_insercao)
        self.sla_retirada = diff_days(self.data_retirada, self.data_chegada_destino)
        self.sla_envio_brasil = diff_days(self.data_envio_brasil, self.data_retirada)
        self.sla_chegada_brasil = diff_days(self.data_brasil, self.data_envio_brasil)
        self.sla_terrestre_nacional = diff_days(self.data_chegada_porto, self.data_insercao)
        self.sla_embarque = diff_days(self.data_embarque_maritimo, self.data_chegada_porto)
        self.sla_maritimo = diff_days(self.data_desembarque_maritimo, self.data_embarque_maritimo)
        self.sla_terrestre_internacional = diff_days(self.data_chegada_destino, self.data_desembarque_maritimo)
        self.sla_terrestre = diff_days(self.data_chegada_destino, self.data_desembarque_maritimo)
        self.sla_internacional = diff_days(self.data_retirada, self.data_chegada_destino)
       
        # Soma total dos SLAs exibidos
        sla_soma = 0
        for v in [
            self.sla_insercao, self.sla_retirada, self.sla_envio_brasil, self.sla_chegada_brasil,
            self.sla_terrestre_nacional, self.sla_embarque, self.sla_maritimo,
            self.sla_terrestre_internacional, self.sla_terrestre, self.sla_internacional,
           
        ]:
            if v not in [None, '', ' ']:
                try:
                    sla_soma += int(v)
                except Exception:
                    pass
        self.sla_operacao = sla_soma

    def save(self, *args, **kwargs):
        # Sempre recalcula o status antes de salvar
        self.status_operacao = self.get_status_automatico()
        self.calcular_slas()
        super().save(*args, **kwargs)

    def get_status_automatico(self):
        # Se o status for Danificado, retorna Danificado independente das datas
        if self.status_operacao == 'Danificado':
            return 'Danificado'
            
        # NOVA LÓGICA: Se todas as datas relevantes estiverem vazias, retorna 'Equipamento na Base'
        datas = [
            self.data_envio,
            self.data_insercao,
            self.data_chegada_destino,
            self.data_retirada,
            self.data_envio_brasil,
            self.data_brasil,
            self.data_chegada_porto,
            self.data_embarque_maritimo,
            self.data_desembarque_maritimo,
            self.data_chegada_terminal,
            self.data_saida_terminal,
            self.data_desembarque,
            self.coleta,
            self.liberacao,
            self.golden_sat,
            self.data_envoice,
        ]
        if all(d is None or d == '' for d in datas):
            return 'Equipamento na Base'
        
        status = None
        
        if self.status_operacao == 'Extraviado':
            status = 'Extraviado'
        elif self.status_operacao == 'Fora de Operação':
            status = 'Fora de Operação'
        elif self.golden_sat:
            status = 'Reversa Finalizada'
        elif self.liberacao:
            status = 'Aguardando Chegada na Base'
        elif self.data_brasil:
            status = 'Aguardando Liberação RFB'
        elif self.coleta:
            status = 'Aguardando Embarque Internacional'
        elif self.data_envoice:
            status = 'Aguardando Coleta'
        elif self.data_envio_brasil:
            status = 'Em reversa para o Brasil'
        elif self.data_retirada:
            status = 'Retirado, Ag. Envio'
        elif self.data_chegada_destino:
            status = 'No destino'
        elif self.data_envio and not self.data_insercao and not self.data_envio_brasil and not self.data_chegada_destino:
            status = 'Estoque Cliente'
        elif self.data_envio and self.data_insercao and not self.data_envio_brasil and not self.data_chegada_destino:
            status = 'Em viagem'
        elif self.status_operacao == 'Estoque Cliente':
            status = 'Estoque Cliente'
        else:
            status = 'GoldenSat'

        return status

    @classmethod
    def atualizar_status_existentes(cls):
        """
        Atualiza os status existentes no banco de dados para os novos valores padronizados.
        """
        # Mapeamento de status antigos para novos
        mapeamento_status = {
            'Aguardando Liberação': 'Aguardando Liberação RFB',
            'Em Viagem': 'Em viagem',
            'Estoque Golden': 'Estoque Cliente',
            'Aguardando Envio': 'Aguardando Embarque Internacional',
            'Fora de Operação': 'Fora de Operação',
            # Adicione outros mapeamentos conforme necessário
        }

        # Atualiza todos os registros
        for registro in cls.objects.all():
            status_antigo = registro.status_operacao
            if status_antigo in mapeamento_status:
                registro.status_operacao = mapeamento_status[status_antigo]
                registro.save(update_fields=['status_operacao'])
            # Se o status não estiver no mapeamento, recalcula usando get_status_automatico
            else:
                novo_status = registro.get_status_automatico()
                if novo_status != registro.status_operacao:
                    registro.status_operacao = novo_status
                    registro.save(update_fields=['status_operacao'])

    def sla_operacao_dias(self):
        if self.golden_sat and self.data_envio:
            return (self.golden_sat - self.data_envio).days
        return ''

    def rejeitar(self):
        """Rejeita a cotação"""
        self.status = 'rejeitado'
        self.save(update_fields=['status'])




class clientesNestle(models.Model):
    cliente = models.CharField("Cliente", max_length=255, null=True, blank=True)
    cnpj = models.CharField("CNPJ", max_length=255, null=True, blank=True)
    endereco = models.CharField("Endereço", max_length=255, null=True, blank=True)
    quantidade = models.IntegerField("Quantidade",  null=True, blank=True)
    valor = models.DecimalField("Valor", max_digits=10, decimal_places=2, null=True, blank=True)
    local = models.CharField("Local", max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.cliente} — {self.cnpj or 'sem cnpj'}"




class ValorMensalCliente(models.Model):
    MESES_CHOICES = [
        ('01', 'Janeiro'),
        ('02', 'Fevereiro'),
        ('03', 'Março'),
        ('04', 'Abril'),
        ('05', 'Maio'),
        ('06', 'Junho'),
        ('07', 'Julho'),
        ('08', 'Agosto'),
        ('09', 'Setembro'),
        ('10', 'Outubro'),
        ('11', 'Novembro'),
        ('12', 'Dezembro'),
    ]

    cliente = models.ForeignKey('clientesNestle', on_delete=models.CASCADE)
    mes = models.CharField(max_length=2, choices=MESES_CHOICES)
    ano = models.IntegerField()
    valor = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    codigo_rastreio = models.CharField(max_length=255, null=True, blank=True, verbose_name='Código de Rastreio')
    enviado = models.BooleanField(default=False)
    data_envio = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['cliente', 'mes', 'ano']
        ordering = ['cliente__cliente', 'ano', 'mes']

    def __str__(self):
        return f"{self.cliente.cliente} - {self.get_mes_display()} {self.ano}"

from decimal import Decimal
from django.db import models

CURRENCY_CHOICES = [
    ('EUR', 'Euro'),
    ('USD', 'Dólar'),
    ('BRL', 'Real'),
]












class Carga(models.Model):
    TIPO_CHOICES = [
        ('FEDEX', 'FedEx'),
        ('DHL', 'DHL'),
        ('Agente', 'Agente'),
    ]

    data                = models.DateField()
    tipo_transportadora = models.CharField("Transportadora", max_length=15, choices=TIPO_CHOICES, default='Agente')
    
    STATUS_CHOICES = [
        ('Pendente', 'Pendente'),
        ('Aprovada', 'Aprovada'),
        ('Reprovada', 'Reprovada'),
    ]
    status = models.CharField("Status da Cotação", max_length=10, choices=STATUS_CHOICES, default='Pendente')

    # ─── FRETE ALL IN ───────────────────────────
    frete_all_in_valor  = models.DecimalField("Frete ALL IN (EUR)", max_digits=12, decimal_places=2, null=True, blank=True)
    frete_all_in_usd    = models.DecimalField("Frete ALL IN (USD)", max_digits=12, decimal_places=2, null=True, blank=True)
    frete_all_in_moeda  = models.CharField("Moeda", max_length=3, choices=CURRENCY_CHOICES, default='EUR')
    frete_all_in_brl    = models.DecimalField(max_digits=12, decimal_places=2, editable=False, null=True, blank=True)
    cotacao_usada       = models.DecimalField(max_digits=10, decimal_places=4, editable=False, null=True, blank=True)
    cotacao_dolar_na_data = models.DecimalField(max_digits=10, decimal_places=4, editable=False, null=True, blank=True)
    cotacao_euro_na_data = models.DecimalField(max_digits=10, decimal_places=4, editable=False, null=True, blank=True)
    frete_all_in_eur_brl = models.DecimalField(max_digits=12, decimal_places=2, editable=False, null=True, blank=True)
    frete_all_in_usd_brl = models.DecimalField(max_digits=12, decimal_places=2, editable=False, null=True, blank=True)
    frete_all_in_usd_moeda = models.CharField("Moeda Frete ALL IN (USD)", max_length=3, choices=CURRENCY_CHOICES, default='USD')

    # ─── DEMAIS CUSTOS (com conversão para BRL) ────────────────
    honorarios = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    honorarios_moeda = models.CharField("Moeda Honorários", max_length=3, choices=CURRENCY_CHOICES, default='BRL')
    honorarios_brl = models.DecimalField(max_digits=12, decimal_places=2, editable=False, null=True, blank=True)

    frete_rodoviario = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    frete_rodoviario_moeda = models.CharField("Moeda Frete Rodoviário", max_length=3, choices=CURRENCY_CHOICES, default='BRL')
    frete_rodoviario_brl = models.DecimalField(max_digits=12, decimal_places=2, editable=False, null=True, blank=True)

    licenca_importacao = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    licenca_importacao_moeda = models.CharField("Moeda Licença Importação", max_length=3, choices=CURRENCY_CHOICES, default='BRL')
    licenca_importacao_brl = models.DecimalField(max_digits=12, decimal_places=2, editable=False, null=True, blank=True)

    taxa_siscomex = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    taxa_siscomex_moeda = models.CharField("Moeda Taxa Siscomex", max_length=3, choices=CURRENCY_CHOICES, default='BRL')
    taxa_siscomex_brl = models.DecimalField(max_digits=12, decimal_places=2, editable=False, null=True, blank=True)

    taxa_armazenagem = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    taxa_armazenagem_moeda = models.CharField("Moeda Taxa Armazenagem", max_length=3, choices=CURRENCY_CHOICES, default='BRL')
    taxa_armazenagem_brl = models.DecimalField(max_digits=12, decimal_places=2, editable=False, null=True, blank=True)

    # ─── Qtd & totais ──────────────────────────
    qtd_equipamento     = models.PositiveIntegerField(null=True, blank=True)
    total               = models.DecimalField(max_digits=14, decimal_places=2, editable=False, null=True, blank=True)
    valor_por_equip     = models.DecimalField(max_digits=14, decimal_places=2, editable=False, null=True, blank=True)
    
    rf_invoice          = models.CharField("RF Invoice", max_length=255, null=True, blank=True)
    data_invoice        = models.DateField("Data Invoice", null=True, blank=True)
    origem              = models.CharField("Origem", max_length=255, null=True, blank=True)

    def save(self, *args, **kwargs):
        try:
            # Definir valores padrão para campos de moeda se estiverem vazios
            if not self.honorarios_moeda:
                self.honorarios_moeda = 'BRL'
            if not self.frete_rodoviario_moeda:
                self.frete_rodoviario_moeda = 'BRL'
            if not self.licenca_importacao_moeda:
                self.licenca_importacao_moeda = 'BRL'
            if not self.taxa_siscomex_moeda:
                self.taxa_siscomex_moeda = 'BRL'
            if not self.taxa_armazenagem_moeda:
                self.taxa_armazenagem_moeda = 'BRL'
            
            # Obter cotações de moeda se não estiverem definidas
            if not self.cotacao_dolar_na_data or not self.cotacao_euro_na_data:
                try:
                    self.cotacao_dolar_na_data = self.get_rate_to_brl('USD')
                    self.cotacao_euro_na_data = self.get_rate_to_brl('EUR')
                except Exception as e:
                    print(f"Erro ao obter cotações: {e}")
                    # Usar cotações padrão em caso de erro
                    self.cotacao_dolar_na_data = Decimal('5.00')
                    self.cotacao_euro_na_data = Decimal('5.50')
            
            # ─── FRETE ALL IN ───────────────────────────
            if self.frete_all_in_moeda == 'BRL':
                self.frete_all_in_eur_brl = self.frete_all_in_valor or Decimal('0.00')
                self.frete_all_in_usd_brl = self.frete_all_in_usd or Decimal('0.00')
            elif self.frete_all_in_moeda == 'EUR':
                self.frete_all_in_eur_brl = (self.frete_all_in_valor or Decimal('0.00')) * (self.cotacao_euro_na_data or Decimal('0.00'))
                self.frete_all_in_usd_brl = (self.frete_all_in_usd or Decimal('0.00')) * (self.cotacao_euro_na_data or Decimal('0.00'))
            elif self.frete_all_in_moeda == 'USD':
                self.frete_all_in_eur_brl = (self.frete_all_in_valor or Decimal('0.00')) * (self.cotacao_dolar_na_data or Decimal('0.00'))
                self.frete_all_in_usd_brl = (self.frete_all_in_usd or Decimal('0.00')) * (self.cotacao_dolar_na_data or Decimal('0.00'))
            else:
                self.frete_all_in_eur_brl = Decimal('0.00')
                self.frete_all_in_usd_brl = Decimal('0.00')
            
            # ─── DEMAIS CAMPOS ───────────────────────────
            if self.honorarios_moeda == 'BRL':
                self.honorarios_brl = self.honorarios or Decimal('0.00')
            elif self.honorarios_moeda == 'EUR':
                self.honorarios_brl = (self.honorarios or Decimal('0.00')) * (self.cotacao_euro_na_data or Decimal('0.00'))
            elif self.honorarios_moeda == 'USD':
                self.honorarios_brl = (self.honorarios or Decimal('0.00')) * (self.cotacao_dolar_na_data or Decimal('0.00'))
            else:
                self.honorarios_brl = Decimal('0.00')
            
            if self.frete_rodoviario_moeda == 'BRL':
                self.frete_rodoviario_brl = self.frete_rodoviario or Decimal('0.00')
            elif self.frete_rodoviario_moeda == 'EUR':
                self.frete_rodoviario_brl = (self.frete_rodoviario or Decimal('0.00')) * (self.cotacao_euro_na_data or Decimal('0.00'))
            elif self.frete_rodoviario_moeda == 'USD':
                self.frete_rodoviario_brl = (self.frete_rodoviario or Decimal('0.00')) * (self.cotacao_dolar_na_data or Decimal('0.00'))
            else:
                self.frete_rodoviario_brl = Decimal('0.00')
            
            if self.licenca_importacao_moeda == 'BRL':
                self.licenca_importacao_brl = self.licenca_importacao or Decimal('0.00')
            elif self.licenca_importacao_moeda == 'EUR':
                self.licenca_importacao_brl = (self.licenca_importacao or Decimal('0.00')) * (self.cotacao_euro_na_data or Decimal('0.00'))
            elif self.licenca_importacao_moeda == 'USD':
                self.licenca_importacao_brl = (self.licenca_importacao or Decimal('0.00')) * (self.cotacao_dolar_na_data or Decimal('0.00'))
            else:
                self.licenca_importacao_brl = Decimal('0.00')
            
            if self.taxa_siscomex_moeda == 'BRL':
                self.taxa_siscomex_brl = self.taxa_siscomex or Decimal('0.00')
            elif self.taxa_siscomex_moeda == 'EUR':
                self.taxa_siscomex_brl = (self.taxa_siscomex or Decimal('0.00')) * (self.cotacao_euro_na_data or Decimal('0.00'))
            elif self.taxa_siscomex_moeda == 'USD':
                self.taxa_siscomex_brl = (self.taxa_siscomex or Decimal('0.00')) * (self.cotacao_dolar_na_data or Decimal('0.00'))
            else:
                self.taxa_siscomex_brl = Decimal('0.00')
            
            if self.taxa_armazenagem_moeda == 'BRL':
                self.taxa_armazenagem_brl = self.taxa_armazenagem or Decimal('0.00')
            elif self.taxa_armazenagem_moeda == 'EUR':
                self.taxa_armazenagem_brl = (self.taxa_armazenagem or Decimal('0.00')) * (self.cotacao_euro_na_data or Decimal('0.00'))
            elif self.taxa_armazenagem_moeda == 'USD':
                self.taxa_armazenagem_brl = (self.taxa_armazenagem or Decimal('0.00')) * (self.cotacao_dolar_na_data or Decimal('0.00'))
            else:
                self.taxa_armazenagem_brl = Decimal('0.00')
            
            # Total e valor por equipamento
            self.total = sum([
                self.frete_all_in_eur_brl or Decimal('0.00'),
                self.frete_all_in_usd_brl or Decimal('0.00'),
                self.honorarios_brl or Decimal('0.00'),
                self.frete_rodoviario_brl or Decimal('0.00'),
                self.licenca_importacao_brl or Decimal('0.00'),
                self.taxa_siscomex_brl or Decimal('0.00'),
                self.taxa_armazenagem_brl or Decimal('0.00'),
            ])
            
            if self.qtd_equipamento and self.qtd_equipamento > 0:
                self.valor_por_equip = self.total / self.qtd_equipamento
            else:
                self.valor_por_equip = Decimal('0.00')
            
            super().save(*args, **kwargs)
            
        except Exception as e:
            print(f"Erro no método save() do modelo Carga: {e}")
            # Em caso de erro, salva com valores padrão
            self.total = Decimal('0.00')
            self.valor_por_equip = Decimal('0.00')
            super().save(*args, **kwargs)

    def _converter_para_brl(self, valor, moeda):
        """
        Converte um valor para BRL baseado na moeda especificada.
        """
        if valor is None:
            return Decimal('0.00')
        
        valor = Decimal(str(valor))
        
        if moeda == 'EUR':
            return (valor * self.cotacao_euro_na_data).quantize(Decimal('0.01'))
        elif moeda == 'USD':
            return (valor * self.cotacao_dolar_na_data).quantize(Decimal('0.01'))
        else:  # BRL
            return valor.quantize(Decimal('0.01'))

    # ─── util ──────────────────────────────────
    @staticmethod
    def get_rate_to_brl(code: str) -> Decimal:
        """
        Busca a cotação atual → BRL usando a API do Banco Central do Brasil.
        Retorna 1 se já for BRL.
        """
        if code == 'BRL':
            return Decimal('1')
        
        try:
            # API do Banco Central do Brasil
            r = requests.get(
                'https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados/ultimos/1?formato=json',
                timeout=10
            )
            r.raise_for_status()
            data = r.json()
            
            if not data or not isinstance(data, list) or len(data) == 0:
                raise ValueError("Invalid response format from BCB API")
            
            # O valor retornado é a cotação do dólar
            usd_rate = Decimal(str(data[0]['valor']))
            
            if code == 'USD':
                return usd_rate
            elif code == 'EUR':
                # Para EUR, precisamos fazer uma segunda chamada
                r = requests.get(
                    'https://api.bcb.gov.br/dados/serie/bcdata.sgs.21619/dados/ultimos/1?formato=json',
                    timeout=10
                )
                r.raise_for_status()
                eur_data = r.json()
                
                if not eur_data or not isinstance(eur_data, list) or len(eur_data) == 0:
                    raise ValueError("Invalid response format from BCB API for EUR")
                
                eur_rate = Decimal(str(eur_data[0]['valor']))
                return eur_rate
            
            raise ValueError(f"Unsupported currency code: {code}")
            
        except (requests.RequestException, ValueError, KeyError, IndexError) as e:
            # Em caso de erro, retorna uma cotação padrão
            print(f"Error fetching exchange rate: {str(e)}")
            if code == 'USD':
                return Decimal('5.00')  # Cotação padrão USD
            elif code == 'EUR':
                return Decimal('5.50')  # Cotação padrão EUR
            return Decimal('1.00')  # Fallback

    def __str__(self):
        return f"Cotação {self.id} - {self.tipo_transportadora} - {self.data}"

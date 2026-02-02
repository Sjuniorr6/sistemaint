from django.db import models
from acompanhamento.models import Clientes   
from produto.models import Produto    
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from franquia.models import registrodefranquia
from datetime import timedelta
from decimal import Decimal


class Antenista(models.Model):
    """Modelo simples para armazenar antenistas cadastrados via UI.

    Campos:
    - nome: nome identificador do antenista (único)
    - estado: estado/UF ou observação curta (opcional)
    """
    nome = models.CharField(max_length=120, unique=True)
    estado = models.CharField(max_length=60, null=True, blank=True)

    def __str__(self):
        return self.nome

class Requisicoes(models.Model):
    # Definição das escolhas de status
    statuschoice = [
        ('Aprovado', 'Aprovado'),
        ('Reprovado', 'Reprovado'),
        ('Pendente', 'Pendente'),
        ('Configurado', 'Configurado'),
        ('Expedido', 'Expedido'),
    ]

    # Definição das escolhas de TP (tempo de processamento)
    TP = [
        ('5', '5'),
        ('10', '10'),
        ('15', '15'),
        ('30', '30'),
        ('60', '60'),
        ('360', '360'),
        ('720', '720'),
    ]
    statusfat = [
        
        
        
        ('Pendente', 'Pendente'),
        ('Faturado sem taxa', 'Faturado sem taxa'),
        ('Faturado com taxa', 'Faturado com taxa'),
        ('Pendente', 'Pendente'),
        ('Pendente sem Contrato', 'Pendente sem Contrato'),
        ('Pendente Sem Termo', 'Pendente Sem Termo'),
        ('Pendente Sem Contrato', 'Pendente Sem Contrato'),
        ('Sem Custo', 'Sem Custo'),
        ('Dados invalidos', 'Dados invalidos'),
        ('Reprovado Pelo CEO','Reprovado Pelo CEO'),
    ]
    motivoc = [
        ('Tipo de Faturamento', 'Tipo de Faturamento'),
        ('Aquisicão Nova', 'Aquisicão Nova'),
        ('Manutenção', 'Manutenção'),
        ('Aditivo', 'Aditivo'),
        ('Acessórios', 'Acessórios'),
        ('Extravio', 'Extravio'),
        ('Teste', 'Teste'),
        ('Spot','Spot'),
        ('Isca Fast - Agente', 'Isca Fast - Agente'),
        ('Antenista', 'Antenista'),
        ('Reversa', 'Reversa'),
        ('Isca FAST', 'Isca FAST'),
        # ('Estoque Antenista', 'Estoque Antenista'),
        ('Renovação', 'Renovação'),
    ]


    # Definição das escolhas de tipo de envio
    tipo_envio = [
        ('Agente', 'Agente'),
        ('Retirada na base', 'Retirada na base'),
        ('Motoboy', 'Motoboy'),
        ('transportadora', 'Transportadora'),
        ('Correio', 'Correio'),
        ('Comercial', 'Comercial'),
    ]

    # Definição das escolhas de tipo de contrato
    contrato_tipo = [
        ('', ''),
        ('Descartavel', 'Descartavel'),
        ('Retornavel', 'Retornavel'),
    ]

    # Definição das escolhas de tipo de fatura
    fatura_tipo = [
        ('Com Custo', 'Com Custo'),
        ('Sem Custo', 'Sem Custo'),
    ]

    # Definição das escolhas de status
    STATUS_CHOICES = [
        
        ('Pendente', 'Pendente'),
        ('Configurado', 'Configurado'),
        ('Reprovado pelo CEO', 'Reprovado pelo CEO'),
        ('Aprovado pelo CEO', 'Aprovado pelo CEO'),
        ('Enviado para o cliente', 'Enviado para o cliente'),
    ]
    customizacoes = [

        ('Sem custumização' , 'Sem custumização'),
        ('Caixa de papelão' , 'Caixa de papelão' ),
        ('Caixa de papelão (bateria desacoplada)' , 'Caixa de papelão (bateria desacoplada)'),
        ('Caixa de papelão + DF' , 'Caixa de papelão + DF'),
        ('Termo branco' , 'Termo branco'),
        ('Termo branco + imã' , 'Termo branco + imã'),
        ('Termo branco + D.F ' , 'Termo branco + D.F'),
        ('Termo branco slim ' , 'Termo branco slim'),
        ('Termo branco slim + D.F +EQT  ' , 'Termo branco slim + D.F +EQT'),
        ('Termo cinza slim + D.F +EQT  ' , 'Termo cinza slim + D.F +EQT'),
        ('Termo branco  (isopor) ' , 'Termo branco  (isopor)'),
        ('Termo branco - bateria externa ' , 'Termo branco - bateria externa'),
        ('Termo marrom + imã' , 'Termo marrom + imã'),
        ('Termo cinza' , 'Termo cinza'),
        ('Termo cinza + imã' , 'Termo cinza + imã'),
        ('Termo preto' , 'Termo preto'),
        ('Termo preto + imã' , 'Termo preto + imã'),
        ('Termo branco - slim' , 'Termo branco - slim'),
        ('Termo marrom slim +D.F + EQT' , 'Termo marrom slim +D.F + EQT'),
        ('Termo marrom' , 'Termo marrom'),
        ('Termo marrom + ETQ' , 'Termo marrom + ETQ'),
        ('Termo marrom slim' , 'Termo marrom slim'),
        ('Caixa blindada' , 'Caixa blindada'),
        ('Tênis/ Sapato' , 'Tênis/ Sapato'),
        ('Projetor' , 'Projetor'),
        ('Caixa de som' , 'Caixa de som'),
        ('Luminaria' , 'Luminaria'),
        ('Alexa' , 'Alexa'),
        ('Video Game' , 'Video Game'),
        ('Secador de cabelo' , 'Secador de cabelo'),
        ('Roteador' , 'Roteador'),
        ('Relogio digital' , 'Relogio digital'),


    ]
    meses = [
    ('N/A', 'N/A'),
    ('6', '6'),
    ('12', '12'),
    ('18', '18'),
    ('24', '24'),
    ('30', '30'),
    ('36', '36'),
    ('48', '48'),
]
    ANTENISTA_CHOICES = [
    ('RODRIGO SILVA', 'RODRIGO SILVA'),
    ('FELIPPE CAMELO', 'FELIPPE CAMELO'),
    ('FILIPPE CAMELO', 'FILIPPE CAMELO'),
    ('JOSÉ ANTONIO', 'JOSÉ ANTONIO'),
    ('CESAR RODRIGO - SPO', 'CESAR RODRIGO - SPO'),
    ('LUCIO', 'LUCIO'),
    ('FELIPE MACEDO - SPO', 'FELIPE MACEDO - SPO'),
    ('RAFAEL ALVES - SPO', 'RAFAEL ALVES - SPO'),
    ('ANDERSON COSTA / L', 'ANDERSON COSTA / L'),
    ('YURI NETTO', 'YURI NETTO'),
    ('HERCULES / FILIPE', 'HERCULES / FILIPE'),
    ('ALEXANDRE', 'ALEXANDRE'),
    ('AILTON', 'AILTON'),
    ('SATURNINO', 'SATURNINO'),
    ('CLEBSON ARANDU - SPO', 'CLEBSON ARANDU - SPO'),
    ('TENORIO', 'TENORIO'),
    ('WILSON JOSE', 'WILSON JOSE'),
    ('WESLEY RODRIGO', 'WESLEY RODRIGO'),
    ('WESLEY RODRIGO - SPO', 'WESLEY RODRIGO - SPO'),
    ('ANGELO/AGATHA', 'ANGELO/AGATHA'),
    ('STEVERSON ROGGER', 'STEVERSON ROGGER'),
    ('IGOR BARBOSA', 'IGOR BARBOSA'),
    ('CAIQUE GONÇALVES', 'CAIQUE GONÇALVES'),
    ('GIOVAN MENDES', 'GIOVAN MENDES'),
    ('RONALDO/SILVA', 'RONALDO/SILVA'),
    ('CARDOSO/PAULA', 'CARDOSO/PAULA'),
    ('BORGES / ALMEIDA - JONAS', 'BORGES / ALMEIDA - JONAS'),
    ('DINAYDER/CLEITON - JONAS', 'DINAYDER/CLEITON - JONAS'),
    ('IVAN/LEANDRO - ALEX', 'IVAN/LEANDRO - ALEX'),
    ('WILSON JOSE - SPO', 'WILSON JOSE - SPO'),
    ('VINICIUS SUHE', 'VINICIUS SUHE'),
    ('AURELIO ANDRADE - RJ', 'AURELIO ANDRADE - RJ'),
    ('THAISY/JOAO PEDRO', 'THAISY/JOAO PEDRO'),
    ('PAULO VICENTE/LUCIA - JONAS', 'PAULO VICENTE/LUCIA - JONAS'),
    ('ANDERSON NOGUEIRA', 'ANDERSON NOGUEIRA'),
    ('THIAGO MATHEUS - SPO', 'THIAGO MATHEUS - SPO'),
    ('SIMEI SANTANA - SPO', 'SIMEI SANTANA - SPO'),
    ('FLORIANO FERREIRA - SPO', 'FLORIANO FERREIRA - SPO'),
    ('AURELIO', 'AURELIO'),
    ('RAPHAEL/LIMA', 'RAPHAEL/LIMA'),
    ('RIBEIRO/DUTRA', 'RIBEIRO/DUTRA'),
    ('HUGO/MOTTA', 'HUGO/MOTTA'),
    ('ANDRADE/LEONARDO', 'ANDRADE/LEONARDO'),
    ('ANDERSON/MARCIO', 'ANDERSON/MARCIO'),
    ('SILVIO ROMERO', 'SILVIO ROMERO'),
    ('ALEX SILVA', 'ALEX SILVA'),
    ('GABRIEL QUILANTE', 'GABRIEL QUILANTE'),
    ('VITOR ROGERIO', 'VITOR ROGERIO'),
    ('MARCIO JUNIOR', 'MARCIO JUNIOR'),
    ('TADEU', 'TADEU'),
    ('LEANDRO FERREIRA - RJ', 'LEANDRO FERREIRA - RJ'),
    ('NASCIMENTO/AMERSON', 'NASCIMENTO/AMERSON'),
    ('IZABEL/SAMPAIO', 'IZABEL/SAMPAIO'),
    ('ANDRE/TELES', 'ANDRE/TELES'),
    ('ALLAN/CRISTINA', 'ALLAN/CRISTINA'),
    ('CARLOS MAIA/FELIPE SOUSA', 'CARLOS MAIA/FELIPE SOUSA'),
    ('FELIPE SOUZA', 'FELIPE SOUZA'),
    ('ROBSON RAMIRO', 'ROBSON RAMIRO'),
    ('WASHINGTON FERNANDES - RJ', 'WASHINGTON FERNANDES - RJ'),
    ('CARLOS CARVALHO/DIOGO SENA', 'CARLOS CARVALHO/DIOGO SENA'),
    ('ROGERIO/ISMAEL', 'ROGERIO/ISMAEL'),
    ('JANDERSO FERNANDES', 'JANDERSO FERNANDES'),
    ('JOAO MARCOS', 'JOAO MARCOS'),
    ('ADRIANO GONÇALVES', 'ADRIANO GONÇALVES'),
    ('COUTINHO/SANTOS', 'COUTINHO/SANTOS'),
    ('NUNES/CRYSOSTOMO', 'NUNES/CRYSOSTOMO'),
    ('ESTEVAO/ULYSSES', 'ESTEVAO/ULYSSES'),
    ('ALCIDES', 'ALCIDES'),
    ('EZEQUIEL', 'EZEQUIEL'),
    ('NILDO', 'NILDO'),
    ('ALEX', 'ALEX'),
    ('ANDERSON', 'ANDERSON'),
    ('ANTONIEQUE', 'ANTONIEQUE'),
    ('OSNI', 'OSNI'),
    ('ELTON', 'ELTON'),
    ('NEY', 'NEY'),
    ('ANDRÉ', 'ANDRÉ'),
    ('RILDO', 'RILDO'),
    ('WELLINGTHON', 'WELLINGTHON'),
    ('GERSON WALACE', 'GERSON WALACE'),
    ('JUSTINO', 'JUSTINO'),
    ('ANTONIO', 'ANTONIO'),
    ('FRANCISCO', 'FRANCISCO'),
    ('OSMAN', 'OSMAN'),
    ('TONHARA', 'TONHARA'),
    ('EMERSON', 'EMERSON'),
    ('MARCELO', 'MARCELO'),
    ('JEFFERSON', 'JEFFERSON'),
    ('GUILHERME', 'GUILHERME'),
    ('MARCIO', 'MARCIO'),
    ('SAMPAIO', 'SAMPAIO'),
    ('DIOGO', 'DIOGO'),
    ('WESLEY', 'WESLEY'),
    ('EVERALDO / SAMUEL', 'EVERALDO / SAMUEL'),
    ('ERIK', 'ERIK'),
    ('LUCAS CARVALHO', 'LUCAS CARVALHO'),
    ('RODRIGO', 'RODRIGO'),
    ('PITTA', 'PITTA'),
    ('JUSTO', 'JUSTO'),
    ('PAULO HENRIQUE', 'PAULO HENRIQUE'),
    ('EDUARDO', 'EDUARDO'),
    ('YURI', 'YURI'),
    ('RAFAEL', 'RAFAEL'),
    ('MARLON', 'MARLON'),
    ('MALLONE ROCHA DA SILVA', 'MALLONE ROCHA DA SILVA'),
    ('Ian Carlos Severino', 'Ian Carlos Severino'),
    ('Matheus (Praia Grande)', 'Matheus (Praia Grande)'),
    ('André Tsubamoto | Uniforme Seguros', 'André Tsubamoto | Uniforme Seguros'),
    ('Fernandes - Nordeste Seguros', 'Fernandes - Nordeste Seguros'),
    ('RAY ALBINO -MOGIGUAÇU/SP','RAY ALBINO -MOGIGUAÇU/SP'),
    ('Barbosa - Nordeste Seguros de FORTALEZA','Barbosa - Nordeste Seguros de FORTALEZA'),	
    ('Kelly - DeCaprio Seguros de Belo Horizonte','Kelly - DeCaprio Seguros de Belo Horizonte'),
    ('Gilmar Dutra - Natal / RN','Gilmar Dutra - Natal / RN'),
    ('Redvagner Schroeder Silva / Atibaia - SP', 'Redvagner Schroeder Silva / Atibaia - SP'),
    ('Marcio Raimundo da Silva / Pouso Alegre - MG', 'Marcio Raimundo da Silva / Pouso Alegre - MG'),
    ('osé Nilton Costa de Souza / Petrolina - PE', 'osé Nilton Costa de Souza / Petrolina - PE'),
    ('João Paulo Alexandre da Silva | Maceió - BA', 'João Paulo Alexandre da Silva | Maceió - BA'),
    ('Andrei Angelim Pinheiro - MANAUS - AM', 'Andrei Angelim Pinheiro - MANAUS - AM'),
    ('Valdeci Nunes Neto - Itajaí','Valdeci Nunes Neto - Itajaí'),
    ('Oscar Carneiro de Souza Junior','Oscar Carneiro de Souza Junior'),
]
    comercial_choices = [

        ('MAYRA','MAYRA'),
        ('DANIEL','DANIEL'),
        ('MARCIO','MARCIO'),
        ('CIDO','CIDO'),
        ('ALISON','ALISON'),
        ('THIAGO','THIAGO'),
        ('GOLDEN','GOLDEN'),
        ('ARMANDO','ARMANDO'),
        ('JOÃO','JOÃO'),
        ('INFINITY','INFINITY')

    ]

    # Campos do modelo
    id = models.AutoField(primary_key=True)
    nome = models.ForeignKey(Clientes, on_delete=models.CASCADE, related_name='requisicoes_nome')
    endereco = models.CharField(max_length=255, blank=True, null=True)
    contrato = models.CharField(choices=contrato_tipo, null=True, blank=True, max_length=50)
    cnpj = models.CharField(max_length=25, blank=True, null=True)
    numero_de_equipamentos = models.CharField(max_length=14, blank=True, null=True)
    inicio_de_contrato = models.DateField(blank=True, null=True)
    vigencia = models.CharField(max_length=50,choices=meses,blank=True, null=True)
    customizacao = models.CharField(max_length=50,choices=meses,blank=True, null=True)
    data = models.DateTimeField(auto_now_add=True)
    data_alteracao = models.DateTimeField(default=timezone.now)
    data_entrega = models.DateField(blank=True, null=True)
    tipo_customizacao = models.CharField(choices=customizacoes ,null=True,blank=True, max_length=50)
    antenista = models.CharField(choices= ANTENISTA_CHOICES,max_length=50, blank=True, null=True)  # Novo campo para antenistas
    envio = models.CharField(choices=tipo_envio, null=True, blank=True, max_length=50)
    taxa_envio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    comercial = models.CharField(choices=comercial_choices ,max_length=100, blank=True, default='')
    tipo_produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='requisicoes_produto')
    carregador = models.CharField(max_length=100, blank=True, default='')
    motivo = models.CharField(choices=motivoc,  default='', null=True, blank=True, max_length=50)
    cabo = models.CharField(max_length=100, blank=True, default='')
    tipo_fatura = models.CharField(choices=fatura_tipo, null=True, blank=True, max_length=50)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    forma_pagamento = models.CharField(max_length=100,null=True, blank=True, default='')
    observacoes = models.TextField(max_length=250,null=True, blank=True, default='')
    aos_cuidados = models.TextField(max_length=250,null=True, blank=True, default='')
    status = models.CharField(choices=STATUS_CHOICES,default='Pendente', null=True, blank=True, max_length=50)
    TP = models.CharField(choices=TP, null=True, blank=True, max_length=50)
    status_faturamento = models.CharField(choices=statusfat,  default="Pendente",null=True, blank=True, max_length=50)
    id_equipamentos= models.TextField(max_length=180000, null=True, blank=True, default='')
    faturamento= models.CharField(choices=statusfat ,max_length=1200, blank=True, default='Pendente')
    iccid = models.CharField(max_length=600000,null=True, blank=True, default='')
    
    # Campos para o Kanban Board
    KANBAN_STATUS_CHOICES = [
        ('a_fazer', 'A Fazer'),
        ('em_progresso', 'Em Progresso'),
        ('auditoria', 'Auditoria'),
    ]
    
    RESPONSAVEL_MANUTENCAO_CHOICES = [
        ('GuilhermeAmarante', 'Guilherme Amarante'),
        ('Talita.Espinosa', 'Talita Espinosa'),
        ('Vinicius.Rodrigues', 'Vinicius Rodrigues'),
        ('Patricia.Costa', 'Patricia Costa'),
        ('Anália', 'Anália Venancio'),
        ('Evellyn.Taila', 'Evellyn Taila'),
        ('Tiago.Faria', 'Tiago Faria'),
        ('Inteligencia', 'Inteligencia'),
    ]
    
    kanban_status = models.CharField(
        choices=KANBAN_STATUS_CHOICES, 
        default='a_fazer', 
        max_length=20,
        null=True,
        blank=True
    )
    prioridade = models.BooleanField(default=False)
    cor_card = models.CharField(max_length=20, null=True, blank=True, default='')
    responsavel_manutencao = models.CharField(
        choices=RESPONSAVEL_MANUTENCAO_CHOICES,
        max_length=50,
        null=True,
        blank=True,
        help_text='Responsável pela manutenção/configuração do equipamento'
    )
    
    # Campos para checklist de auditoria na expedição
    ids_auditados = models.TextField(
        max_length=180000,
        null=True,
        blank=True,
        default='',
        help_text='IDs dos equipamentos que passaram pela auditoria antes da expedição'
    )
    memoria_apagada = models.BooleanField(
        default=False,
        help_text='Indica se Apagaram a Memória do Equipamento'
    )
    verificacao_tp = models.BooleanField(
        default=False,
        help_text='Indica se houve verificação do TP conforme a Requisição'
    )
    verificacao_plataforma = models.BooleanField(
        default=False,
        help_text='Indica se houve verificação via plataforma durante a auditoria'
    )
    customizacao_conforme = models.BooleanField(
        default=False,
        help_text='Indica se a customização está de acordo com o solicitado'
    )
    
    # Campos para expedição parcial
    requisicao_original_id = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisicoes_parciais',
        help_text='Requisição original de onde esta foi derivada (expedição parcial)'
    )
    quantidade_expedida = models.IntegerField(
        default=0,
        help_text='Quantidade já expedida desta requisição'
    )
    
    def __str__(self):
        return f"Requisição {self.id} - {self.nome} "
    
    def get_quantidade_ids_incluidos(self):
        """Retorna a quantidade de IDs incluídos no campo id_equipamentos"""
        if not self.id_equipamentos or not self.id_equipamentos.strip():
            return 0
        return len(self.id_equipamentos.strip().split())


class estoque_antenista(models.Model):
    ANTENISTA_CHOICES =[
    ('RODRIGO SILVA', 'RODRIGO SILVA'),
    ('FELIPPE CAMELO', 'FELIPPE CAMELO'),
    ('FILIPPE CAMELO', 'FILIPPE CAMELO'),
    ('JOSÉ ANTONIO', 'JOSÉ ANTONIO'),
    ('CESAR RODRIGO - SPO', 'CESAR RODRIGO - SPO'),
    ('LUCIO', 'LUCIO'),
    ('FELIPE MACEDO - SPO', 'FELIPE MACEDO - SPO'),
    ('RAFAEL ALVES - SPO', 'RAFAEL ALVES - SPO'),
    ('ANDERSON COSTA / L', 'ANDERSON COSTA / L'),
    ('YURI NETTO', 'YURI NETTO'),
    ('HERCULES / FILIPE', 'HERCULES / FILIPE'),
    ('ALEXANDRE', 'ALEXANDRE'),
    ('AILTON', 'AILTON'),
    ('SATURNINO', 'SATURNINO'),
    ('CLEBSON ARANDU - SPO', 'CLEBSON ARANDU - SPO'),
    ('TENORIO', 'TENORIO'),
    ('WILSON JOSE', 'WILSON JOSE'),
    ('WESLEY RODRIGO', 'WESLEY RODRIGO'),
    ('WESLEY RODRIGO - SPO', 'WESLEY RODRIGO - SPO'),
    ('ANGELO/AGATHA', 'ANGELO/AGATHA'),
    ('STEVERSON ROGGER', 'STEVERSON ROGGER'),
    ('IGOR BARBOSA', 'IGOR BARBOSA'),
    ('CAIQUE GONÇALVES', 'CAIQUE GONÇALVES'),
    ('GIOVAN MENDES', 'GIOVAN MENDES'),
    ('RONALDO/SILVA', 'RONALDO/SILVA'),
    ('CARDOSO/PAULA', 'CARDOSO/PAULA'),
    ('BORGES / ALMEIDA - JONAS', 'BORGES / ALMEIDA - JONAS'),
    ('DINAYDER/CLEITON - JONAS', 'DINAYDER/CLEITON - JONAS'),
    ('IVAN/LEANDRO - ALEX', 'IVAN/LEANDRO - ALEX'),
    ('WILSON JOSE - SPO', 'WILSON JOSE - SPO'),
    ('VINICIUS SUHE', 'VINICIUS SUHE'),
    ('AURELIO ANDRADE - RJ', 'AURELIO ANDRADE - RJ'),
    ('THAISY/JOAO PEDRO', 'THAISY/JOAO PEDRO'),
    ('PAULO VICENTE/LUCIA - JONAS', 'PAULO VICENTE/LUCIA - JONAS'),
    ('ANDERSON NOGUEIRA', 'ANDERSON NOGUEIRA'),
    ('THIAGO MATHEUS - SPO', 'THIAGO MATHEUS - SPO'),
    ('SIMEI SANTANA - SPO', 'SIMEI SANTANA - SPO'),
    ('FLORIANO FERREIRA - SPO', 'FLORIANO FERREIRA - SPO'),
    ('AURELIO', 'AURELIO'),
    ('RAPHAEL/LIMA', 'RAPHAEL/LIMA'),
    ('RIBEIRO/DUTRA', 'RIBEIRO/DUTRA'),
    ('HUGO/MOTTA', 'HUGO/MOTTA'),
    ('ANDRADE/LEONARDO', 'ANDRADE/LEONARDO'),
    ('ANDERSON/MARCIO', 'ANDERSON/MARCIO'),
    ('SILVIO ROMERO', 'SILVIO ROMERO'),
    ('ALEX SILVA', 'ALEX SILVA'),
    ('GABRIEL QUILANTE', 'GABRIEL QUILANTE'),
    ('VITOR ROGERIO', 'VITOR ROGERIO'),
    ('MARCIO JUNIOR', 'MARCIO JUNIOR'),
    ('TADEU', 'TADEU'),
    ('LEANDRO FERREIRA - RJ', 'LEANDRO FERREIRA - RJ'),
    ('NASCIMENTO/AMERSON', 'NASCIMENTO/AMERSON'),
    ('IZABEL/SAMPAIO', 'IZABEL/SAMPAIO'),
    ('ANDRE/TELES', 'ANDRE/TELES'),
    ('ALLAN/CRISTINA', 'ALLAN/CRISTINA'),
    ('CARLOS MAIA/FELIPE SOUSA', 'CARLOS MAIA/FELIPE SOUSA'),
    ('FELIPE SOUZA', 'FELIPE SOUZA'),
    ('ROBSON RAMIRO', 'ROBSON RAMIRO'),
    ('WASHINGTON FERNANDES - RJ', 'WASHINGTON FERNANDES - RJ'),
    ('CARLOS CARVALHO/DIOGO SENA', 'CARLOS CARVALHO/DIOGO SENA'),
    ('ROGERIO/ISMAEL', 'ROGERIO/ISMAEL'),
    ('JANDERSO FERNANDES', 'JANDERSO FERNANDES'),
    ('JOAO MARCOS', 'JOAO MARCOS'),
    ('ADRIANO GONÇALVES', 'ADRIANO GONÇALVES'),
    ('COUTINHO/SANTOS', 'COUTINHO/SANTOS'),
    ('NUNES/CRYSOSTOMO', 'NUNES/CRYSOSTOMO'),
    ('ESTEVAO/ULYSSES', 'ESTEVAO/ULYSSES'),
    ('ALCIDES', 'ALCIDES'),
    ('EZEQUIEL', 'EZEQUIEL'),
    ('NILDO', 'NILDO'),
    ('ALEX', 'ALEX'),
    ('ANDERSON', 'ANDERSON'),
    ('ANTONIEQUE', 'ANTONIEQUE'),
    ('OSNI', 'OSNI'),
    ('ELTON', 'ELTON'),
    ('NEY', 'NEY'),
    ('ANDRÉ', 'ANDRÉ'),
    ('RILDO', 'RILDO'),
    ('WELLINGTHON', 'WELLINGTHON'),
    ('GERSON WALACE', 'GERSON WALACE'),
    ('JUSTINO', 'JUSTINO'),
    ('ANTONIO', 'ANTONIO'),
    ('FRANCISCO', 'FRANCISCO'),
    ('OSMAN', 'OSMAN'),
    ('TONHARA', 'TONHARA'),
    ('EMERSON', 'EMERSON'),
    ('MARCELO', 'MARCELO'),
    ('JEFFERSON', 'JEFFERSON'),
    ('GUILHERME', 'GUILHERME'),
    ('MARCIO', 'MARCIO'),
    ('SAMPAIO', 'SAMPAIO'),
    ('DIOGO', 'DIOGO'),
    ('WESLEY', 'WESLEY'),
    ('EVERALDO / SAMUEL', 'EVERALDO / SAMUEL'),
    ('ERIK', 'ERIK'),
    ('LUCAS CARVALHO', 'LUCAS CARVALHO'),
    ('RODRIGO', 'RODRIGO'),
    ('PITTA', 'PITTA'),
    ('JUSTO', 'JUSTO'),
    ('PAULO HENRIQUE', 'PAULO HENRIQUE'),
    ('EDUARDO', 'EDUARDO'),
    ('YURI', 'YURI'),
    ('RAFAEL', 'RAFAEL'),
    ('MARLON', 'MARLON'),
    ('MALLONE ROCHA DA SILVA', 'MALLONE ROCHA DA SILVA'),
    ('Ian Carlos Severino', 'Ian Carlos Severino'), 
    ('RAY ALBINO -MOGIGUAÇU/SP','RAY ALBINO -MOGIGUAÇU/SP'),
   ('Barbosa - Nordeste Seguros de FORTALEZA','Barbosa - Nordeste Seguros de FORTALEZA'),
   ('Kelly - DeCaprio Seguros de Belo Horizonte','Kelly - DeCaprio Seguros de Belo Horizonte'),
   ('Gilmar Dutra - Natal / RN','Gilmar Dutra - Natal / RN'),
    ('Redvagner Schroeder Silva / Atibaia - SP', 'Redvagner Schroeder Silva / Atibaia - SP'),
    ('Marcio Raimundo da Silva / Pouso Alegre - MG', 'Marcio Raimundo da Silva / Pouso Alegre - MG'),
    ('osé Nilton Costa de Souza / Petrolina - PE', 'osé Nilton Costa de Souza / Petrolina - PE'),
    ('João Paulo Alexandre da Silva | Maceió - BA', 'João Paulo Alexandre da Silva | Maceió - BA'),
    ('Andrei Angelim Pinheiro - MANAUS - AM', 'Andrei Angelim Pinheiro - MANAUS - AM'),
    ('Valdeci Nunes Neto - Itajaí','Valdeci Nunes Neto - Itajaí'),
    ('Oscar Carneiro de Souza Junior','Oscar Carneiro de Souza Junior'),
]

    nome = models.ForeignKey(
        'Antenista', on_delete=models.SET_NULL, related_name='estoques', null=True, blank=True
    )
    # Guarda o nome textual do antenista no momento do registro para histórico.
    nome_texto = models.CharField(max_length=200, null=True, blank=True)
    tipo_produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='antenista_produto')
    endereco = models.CharField(max_length=255, blank=True, null=True)
    quantidade = models.IntegerField(null=True, blank=True)
    data = models.DateField(null=True, blank=True)
    

    def __str__(self):
        return f"{self.nome} - {self.tipo_produto}"

    def save(self, *args, **kwargs):
        # Preenche o campo textual com o nome atual do FK se disponível.
        try:
            if self.nome:
                # evita consultas extras se já estiver preenchido corretamente
                nome_str = str(self.nome)
                if not self.nome_texto:
                    self.nome_texto = nome_str
            super().save(*args, **kwargs)
        except Exception:
            # fallback simples para garantir que o save não quebre
            super().save(*args, **kwargs)



from django.contrib.auth.models import User
from django.db import models

class ControleModel(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    cliente = models.CharField(max_length=50, null=True, blank=True)
    requisicao_id = models.CharField(max_length=50, null=True, blank=True)
    iccid_equipamento1 = models.CharField(max_length=50, null=True, blank=True)
    id_equipamento1 = models.CharField(max_length=50, null=True, blank=True)
    iccid_equipamento2 = models.CharField(max_length=50, null=True, blank=True)
    id_equipamento2 = models.CharField(max_length=50, null=True, blank=True)
    iccid_equipamento3 = models.CharField(max_length=50, null=True, blank=True)
    id_equipamento3 = models.CharField(max_length=50, null=True, blank=True)
    iccid_equipamento4 = models.CharField(max_length=50, null=True, blank=True)
    id_equipamento4 = models.CharField(max_length=50, null=True, blank=True)
    iccid_equipamento5 = models.CharField(max_length=50, null=True, blank=True)
    id_equipamento5 = models.CharField(max_length=50, null=True, blank=True)
    iccid_equipamento6 = models.CharField(max_length=50, null=True, blank=True)
    id_equipamento6 = models.CharField(max_length=50, null=True, blank=True)
    iccid_equipamento7 = models.CharField(max_length=50, null=True, blank=True)
    id_equipamento7 = models.CharField(max_length=50, null=True, blank=True)
    iccid_equipamento8 = models.CharField(max_length=50, null=True, blank=True)
    id_equipamento8 = models.CharField(max_length=50, null=True, blank=True)
    iccid_equipamento9 = models.CharField(max_length=50, null=True, blank=True)
    id_equipamento9 = models.CharField(max_length=50, null=True, blank=True)
    iccid_equipamento10 = models.CharField(max_length=50, null=True, blank=True)
    id_equipamento10 = models.CharField(max_length=50, null=True, blank=True)
    data = models.DateField(auto_now_add=True, null=True)
    quantidade = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Controle {self.id} - Cliente {self.cliente}"




from .models import estoque_antenista

class antenista_CARD(models.Model):
    ANTENISTA_CHOICES =[
('RODRIGO SILVA', 'RODRIGO SILVA'),
('FELIPPE CAMELO', 'FELIPPE CAMELO'),
('FILIPPE CAMELO', 'FILIPPE CAMELO'),
('JOSÉ ANTONIO', 'JOSÉ ANTONIO'),
('CESAR RODRIGO - SPO', 'CESAR RODRIGO - SPO'),
('LUCIO', 'LUCIO'),
('FELIPE MACEDO - SPO', 'FELIPE MACEDO - SPO'),
('RAFAEL ALVES - SPO', 'RAFAEL ALVES - SPO'),
('ANDERSON COSTA / L', 'ANDERSON COSTA / L'),
('YURI NETTO', 'YURI NETTO'),
('HERCULES / FILIPE', 'HERCULES / FILIPE'),
('ALEXANDRE', 'ALEXANDRE'),
('AILTON - CURITIBA /PR', 'AILTON - CURITIBA /PR'),
('SATURNINO', 'SATURNINO'),
('CLEBSON ARANDU - SPO', 'CLEBSON ARANDU - SPO'),
('TENORIO', 'TENORIO'),
('WILSON JOSE', 'WILSON JOSE'),
('WESLEY RODRIGO', 'WESLEY RODRIGO'),
('WESLEY RODRIGO - SPO', 'WESLEY RODRIGO - SPO'),
('ANGELO/AGATHA', 'ANGELO/AGATHA'),
('STEVERSON ROGGER', 'STEVERSON ROGGER'),
('IGOR BARBOSA', 'IGOR BARBOSA'),
('CAIQUE GONÇALVES', 'CAIQUE GONÇALVES'),
('GIOVAN MENDES', 'GIOVAN MENDES'),
('RONALDO/SILVA', 'RONALDO/SILVA'),
('CARDOSO/PAULA', 'CARDOSO/PAULA'),
('BORGES / ALMEIDA - JONAS', 'BORGES / ALMEIDA - JONAS'),
('DINAYDER/CLEITON - JONAS', 'DINAYDER/CLEITON - JONAS'),
('IVAN/LEANDRO - ALEX', 'IVAN/LEANDRO - ALEX'),
('WILSON JOSE - SPO', 'WILSON JOSE - SPO'),
('VINICIUS SUHE', 'VINICIUS SUHE'),
('AURELIO ANDRADE - RJ', 'AURELIO ANDRADE - RJ'),
('THAISY/JOAO PEDRO', 'THAISY/JOAO PEDRO'),
('PAULO VICENTE/LUCIA - JONAS', 'PAULO VICENTE/LUCIA - JONAS'),
('ANDERSON NOGUEIRA', 'ANDERSON NOGUEIRA'),
('THIAGO MATHEUS - SPO', 'THIAGO MATHEUS - SPO'),
('SIMEI SANTANA - SPO', 'SIMEI SANTANA - SPO'),
('FLORIANO FERREIRA - SPO', 'FLORIANO FERREIRA - SPO'),
('AURELIO', 'AURELIO'),
('RAPHAEL/LIMA', 'RAPHAEL/LIMA'),
('RIBEIRO/DUTRA', 'RIBEIRO/DUTRA'),
('HUGO/MOTTA', 'HUGO/MOTTA'),
('ANDRADE/LEONARDO', 'ANDRADE/LEONARDO'),
('ANDERSON/MARCIO', 'ANDERSON/MARCIO'),
('SILVIO ROMERO', 'SILVIO ROMERO'),
('ALEX SILVA', 'ALEX SILVA'),
('GABRIEL QUILANTE', 'GABRIEL QUILANTE'),
('VITOR ROGERIO', 'VITOR ROGERIO'),
('MARCIO JUNIOR', 'MARCIO JUNIOR'),
('TADEU', 'TADEU'),
('LEANDRO FERREIRA - RJ', 'LEANDRO FERREIRA - RJ'),
('NASCIMENTO/AMERSON', 'NASCIMENTO/AMERSON'),
('IZABEL/SAMPAIO', 'IZABEL/SAMPAIO'),
('ANDRE/TELES', 'ANDRE/TELES'),
('ALLAN/CRISTINA', 'ALLAN/CRISTINA'),
('CARLOS MAIA/FELIPE SOUSA', 'CARLOS MAIA/FELIPE SOUSA'),
('FELIPE SOUZA', 'FELIPE SOUZA'),
('ROBSON RAMIRO', 'ROBSON RAMIRO'),
('WASHINGTON FERNANDES - RJ', 'WASHINGTON FERNANDES - RJ'),
('CARLOS CARVALHO/DIOGO SENA', 'CARLOS CARVALHO/DIOGO SENA'),
('ROGERIO/ISMAEL', 'ROGERIO/ISMAEL'),
('JANDERSO FERNANDES', 'JANDERSO FERNANDES'),
('JOAO MARCOS', 'JOAO MARCOS'),
('COUTINHO/SANTOS', 'COUTINHO/SANTOS'),
('NUNES/CRYSOSTOMO', 'NUNES/CRYSOSTOMO'),
('ESTEVAO/ULYSSES', 'ESTEVAO/ULYSSES'),
('ALCIDES - RIBEIRÃO PRETO/SP', 'ALCIDES - RIBEIRÃO PRETO/SP'),
('EZEQUIEL - GARANHUNS/PE', 'EZEQUIEL - GARANHUNS/PE'),
('NILDO LOPES - APARECIDA DE GOIANIA/GO', 'NILDO LOPES - APARECIDA DE GOIANIA/GO'),
('ALEX - ITAJAI/SC', 'ALEX - ITAJAI/SC'),
('ANDERSON', 'ANDERSON'),
('ANTONIEQUE - SALVADOR/BA', 'ANTONIEQUE - SALVADOR/BA'),
('OSNI', 'OSNI'),
('ELTON - GUARULHOS/SP', 'ELTON - GUARULHOS/SP'),
('NEY', 'NEY'),
('ANDRÉ', 'ANDRÉ'),
('RILDO', 'RILDO'),
('WELLINGTHON - TUCURUI/PA', 'WELLINGTHON - TUCURUI/PA'),
('GERSON WALACE - PARAGOMINAS/PA', 'GERSON WALACE - PARAGOMINAS/PA'),
('JUSTINO', 'JUSTINO'),
('ANTONIO - TERESINA/PI', 'ANTONIO - TERESINA/PI'),
('FRANCISCO', 'FRANCISCO'),
('OSMAN', 'OSMAN'),
('TONHARA', 'TONHARA'),
('EMERSON', 'EMERSON'),
('MARCELO', 'MARCELO'),
('JEFFERSON', 'JEFFERSON'),
('GUILHERME', 'GUILHERME'),
('MARCIO MENEZES - CONTAGEM/MG', 'MARCIO MENEZES - CONTAGEM/MG'),
('SAMPAIO - SERRA/ES', 'SAMPAIO - SERRA/ES'),
('DIOGO - SANTA ADELIA/SP', 'DIOGO - SANTA ADELIA/SP'),
('WESLEY - VARGINHA/MG', 'WESLEY - VARGINHA/MG'),
('EVERALDO / SAMUEL', 'EVERALDO / SAMUEL'),
('ERIK', 'ERIK'),
('LUCAS CARVALHO', 'LUCAS CARVALHO'),
('RODRIGO', 'RODRIGO'),
('PITTA', 'PITTA'),
('JUSTO', 'JUSTO'),
('PAULO HENRIQUE', 'PAULO HENRIQUE'),
('EDUARDO - CAXIAS DO SUL/RS', 'EDUARDO - CAXIAS DO SUL/RS'),
('YURI BATALHA - VIAMÃO/RS', 'YURI BATALHA - VIAMÃO/RS'),
('RAFAEL BERTOLLO - SANTA MARIA/RS', 'RAFAEL BERTOLLO - SANTA MARIA/RS'),
('MARLON', 'MARLON'),
('MALLONE ROCHA DA SILVA', 'MALLONE ROCHA DA SILVA'),
('Ian Carlos Severino', 'Ian Carlos Severino'),
('Matheus (Praia Grande)', 'Matheus (Praia Grande)'),
('André Tsubamoto | Uniforme Seguros', 'André Tsubamoto | Uniforme Seguros'),
('Fernandes - Nordeste Seguros', 'Fernandes - Nordeste Seguros'),
('Nordeste Seguros - Filial Recife', 'Nordeste Seguros - Filial Recife'),
('ALEX VIANA CAMPINAS /SP', 'ALEX VIANA - CAMPINAS /SP'),
('ANDREI MANAUS/AM', 'ANDREI MANAUS/AM'),
('ERIK- CAMPO DOS GOYTACAZES /RJ ','ERIK- CAMPO DOS GOYTACAZES /RJ '),
('SAMUEL - JUIZ DE FORA/MG', 'SAMUEL - JUIZ DE FORA/MG'), 
('JOÃO PAULO - MACEIO/AL', 'JOÃO PAULO - MACEIO/AL'),
('JOSÉ NILTON - PETROLINA/PE', 'JOSÉ NILTON - PETROLINA/PE'),
('JOSINEY - FEIRA DE SANTANA/BA', 'JOSINEY - FEIRA DE SANTANA/BA'),
('REDVAGNER -  ATIBAIA/SP', 'REDVAGNER -  ATIBAIA/SP'),
('RILDO LENNO -BELEM/PA', 'RILDO LENNO -BELEM/PA'),
('RODRIGO APARECIDO - JUNDIAI/SP', 'RODRIGO APARECIDO - JUNDIAI/SP'),
('CLEITON SILVA  - POÇOES/BA', 'CLEITON SILVA  - POÇOES/BA'),

]
    TIPO = [
     ('Retornavel','Retornavel'),
     ('Descartavel','Descartavel'),

     
 ]

    # Este campo deve referenciar o modelo `Antenista` (estrutura centralizada de antenistas)
    # mantendo compatibilidade com a UI de seleção.
    # Use SET_NULL para que, se um Antenista for removido da tabela central, os registros
    # históricos em `antenista_CARD` sejam preservados (FK ficará NULL). Para manter o
    # nome textual mesmo após remoção do Antenista, gravamos também em `nome_texto`.
    nome = models.ForeignKey('Antenista', on_delete=models.SET_NULL, related_name='cards', null=True, blank=True)
    # Campo textual que armazena o nome do antenista no momento do registro (histórico)
    nome_texto = models.CharField(max_length=200, null=True, blank=True)
    tipo_produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='antenista_card_produto')
    solicitante  = models.CharField(max_length=1000, blank=True, null=True)
    telefone = models.CharField(max_length=255, blank=True, null=True)
    cliente = models.CharField(max_length=1000, blank=True, null=True)
    quantidade = models.IntegerField(null=True, blank=True)
    equipamentos = models.CharField(max_length=1000, blank=True, null=True)
    contrato = models.CharField(choices=TIPO,max_length=1000, blank=True, null=True)
    valor_entrega  = models.CharField(max_length=1000, blank=True, null=True)
    # Valores financeiros
    valor_prestador = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    valor_isca = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    valor_cliente = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    lucro = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    # Valor total (prestador + isca)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    data_criacao = models.DateField(auto_now_add=True, null=True, blank=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ('Atualizado', 'Atualizado'),
            ('Reprovado', 'Reprovado'),
            ('Pendente', 'Pendente'),
            # Adicione outros status conforme necessário
        ],
        default='Pendente',
    )

    def __str__(self):
        return f"{self.nome} - {self.tipo_produto}"
    def save(self, *args, **kwargs):
        # Preenche nome_texto a partir do FK se disponível.
        try:
            if self.nome and not self.nome_texto:
                self.nome_texto = str(self.nome)
        except Exception:
            # continue mesmo que ocorra algum erro ao ler o FK
            pass

        # Calcula lucro antes de salvar: valor_cliente - valor_prestador - valor_isca
        try:
            vp = self.valor_prestador or 0
            vi = self.valor_isca or 0
            vc = self.valor_cliente or 0
            # calcula valor_total como soma de prestador + isca
            self.valor_total = (vp + vi)
            self.lucro = vc - vp - vi
        except Exception:
            # em caso de qualquer problema com tipos, garantir que não quebre o save
            self.lucro = self.lucro or 0
        super().save(*args, **kwargs)


class KanbanHistorico(models.Model):
    """
    Modelo para rastrear histórico de movimentações no Kanban.
    Registra quem moveu o card, quando e de qual status para qual status.
    """
    requisicao = models.ForeignKey(
        Requisicoes, 
        on_delete=models.CASCADE, 
        related_name='historico_kanban'
    )
    usuario = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='movimentacoes_kanban'
    )
    status_anterior = models.CharField(max_length=20, null=True, blank=True)
    status_novo = models.CharField(max_length=20)
    data_movimentacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-data_movimentacao']
        verbose_name = 'Histórico Kanban'
        verbose_name_plural = 'Históricos Kanban'
    
    def __str__(self):
        return f"Requisição {self.requisicao.id} - {self.status_anterior} → {self.status_novo}"


class KanbanAuditLog(models.Model):
    """
    Modelo para auditoria completa de ações no Kanban.
    Registra movimentações, expedições parciais e totais.
    """
    ACAO_CHOICES = [
        ('movimento', 'Movimento de Card'),
        ('expedicao_parcial', 'Expedição Parcial'),
        ('expedicao_total', 'Expedição Total'),
    ]
    
    requisicao = models.ForeignKey(
        Requisicoes,
        on_delete=models.CASCADE,
        related_name='logs_auditoria'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acoes_kanban'
    )
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    coluna_origem = models.CharField(max_length=20, null=True, blank=True)
    coluna_destino = models.CharField(max_length=20, null=True, blank=True)
    quantidade_expedida = models.IntegerField(null=True, blank=True)
    observacao = models.TextField(null=True, blank=True)
    data_acao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-data_acao']
        verbose_name = 'Log de Auditoria Kanban'
        verbose_name_plural = 'Logs de Auditoria Kanban'
    
    def __str__(self):
        return f"{self.get_acao_display()} - Req {self.requisicao.id} por {self.usuario}"


# Signal para registrar mudanças de status no Kanban
@receiver(post_save, sender=Requisicoes)
def registrar_mudanca_kanban(sender, instance, created, **kwargs):
    """
    Signal que registra no histórico quando o kanban_status de uma requisição muda.
    """
    if not created and hasattr(instance, '_kanban_status_anterior'):
        # Apenas registra se o status mudou
        try:
            status_anterior = instance._kanban_status_anterior
            status_novo = instance.kanban_status
            
            if status_anterior != status_novo:
                KanbanHistorico.objects.create(
                    requisicao=instance,
                    usuario=getattr(instance, '_usuario_mudanca', None),
                    status_anterior=status_anterior,
                    status_novo=status_novo
                )
        except Exception as e:
            # Não quebra o save se houver erro no histórico
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao registrar histórico Kanban: {e}")


# ============================================================================
# MODELOS DE AUDITORIA COMPLETA
# ============================================================================

class AuditLog(models.Model):
    """
    Modelo genérico para registrar todas as ações/mudanças em Requisições e Manutenções
    """
    ACAO_CHOICES = [
        # Requisições
        ('criacao', 'Criação'),
        ('aprovacao', 'Aprovação'),
        ('reprovacao', 'Reprovação'),
        ('atribuicao', 'Atribuição de Responsável'),
        ('status_change', 'Mudança de Status'),
        ('expedicao', 'Expedição'),
        ('envio_cliente', 'Envio ao Cliente'),
        ('edicao', 'Edição'),
        ('exclusao', 'Exclusão'),
        # Kanban
        ('kanban_movido', 'Card Movido no Kanban'),
        ('ids_incluidos', 'IDs Incluídos'),
        ('expedicao_parcial', 'Expedição Parcial'),
        # Manutenção
        ('manutencao_criacao', 'Criação de Manutenção'),
        ('manutencao_aprovacao', 'Aprovação de Manutenção'),
        ('manutencao_reprovacao', 'Reprovação de Manutenção'),
        ('manutencao_atribuicao', 'Atribuição de Responsável (Manutenção)'),
        ('manutencao_status', 'Mudança de Status (Manutenção)'),
        ('manutencao_expedicao', 'Expedição (Manutenção)'),
        ('manutencao_edicao', 'Edição (Manutenção)'),
        ('manutencao_exclusao', 'Exclusão (Manutenção)'),
    ]

    # Referência genérica para Requisicao ou Manutencao
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Dados da ação
    acao = models.CharField(max_length=50, choices=ACAO_CHOICES)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    usuario_nome = models.CharField(max_length=150, help_text="Nome do usuário no momento da ação")
    data_hora = models.DateTimeField(default=timezone.now)
    
    # Detalhes da mudança
    status_anterior = models.CharField(max_length=100, null=True, blank=True)
    status_novo = models.CharField(max_length=100, null=True, blank=True)
    
    # Campo para armazenar informações adicionais em JSON
    detalhes = models.JSONField(null=True, blank=True, help_text="Detalhes adicionais da ação")
    
    # Observações
    observacao = models.TextField(null=True, blank=True)
    
    # IP do usuário (opcional, para segurança)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-data_hora']
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['acao']),
            models.Index(fields=['data_hora']),
            models.Index(fields=['usuario']),
        ]

    def __str__(self):
        return f"{self.get_acao_display()} - {self.usuario_nome} - {self.data_hora.strftime('%d/%m/%Y %H:%M')}"

    @classmethod
    def registrar(cls, objeto, acao, usuario, status_anterior=None, status_novo=None, 
                  detalhes=None, observacao=None, request=None):
        """
        Método helper para registrar uma ação de auditoria
        """
        ip_address = None
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
        
        usuario_nome = usuario.username if usuario else "Sistema"
        
        content_type = ContentType.objects.get_for_model(objeto)
        
        return cls.objects.create(
            content_type=content_type,
            object_id=objeto.id,
            acao=acao,
            usuario=usuario,
            usuario_nome=usuario_nome,
            status_anterior=status_anterior,
            status_novo=status_novo,
            detalhes=detalhes,
            observacao=observacao,
            ip_address=ip_address
        )

class CampoAlterado(models.Model):
    """
    Modelo para registrar campos específicos que foram alterados em uma edição
    """
    audit_log = models.ForeignKey(AuditLog, on_delete=models.CASCADE, related_name='campos_alterados')
    nome_campo = models.CharField(max_length=100)
    valor_anterior = models.TextField(null=True, blank=True)
    valor_novo = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Campo Alterado'
        verbose_name_plural = 'Campos Alterados'

    def __str__(self):
        return f"{self.nome_campo}: {self.valor_anterior} → {self.valor_novo}"






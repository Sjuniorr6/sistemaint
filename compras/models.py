from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class CadastroTipoProduto(models.Model):
    """Modelo para cadastro de tipo de produto"""
    nome_produto = models.CharField(max_length=200, verbose_name="Nome do Produto")
    descricao = models.TextField(verbose_name="Descrição")
    fabricante = models.CharField(max_length=200, verbose_name="Fabricante")
    telefone_fabricante = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone")
    email_fabricante = models.EmailField(blank=True, null=True, verbose_name="E-mail")
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Valor Unitário")
    data_cadastro = models.DateTimeField(auto_now_add=True, verbose_name="Data de Cadastro")
    
    class Meta:
        verbose_name = "Cadastro de Tipo de Produto"
        verbose_name_plural = "Cadastros de Tipos de Produtos"
        ordering = ['-data_cadastro']
    
    def __str__(self):
        return f"{self.nome_produto} - {self.fabricante}"

class EntradaProduto(models.Model):
    """Modelo para entrada de produto"""
    codigo_produto = models.ForeignKey(CadastroTipoProduto, on_delete=models.CASCADE, verbose_name="Código do Produto (FK)")
    quantidade = models.PositiveIntegerField(verbose_name="Quantidade")
    id_equipamento = models.CharField(max_length=100, verbose_name="ID (Número do Equipamento)")
    data = models.DateTimeField(verbose_name="Data (datetime)")
    valor_nota = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor de Nota (Valor de Compra)")
    numero_nota_fiscal = models.CharField(max_length=50, verbose_name="Número de Nota Fiscal")
    data_entrada = models.DateTimeField(auto_now_add=True, verbose_name="Data de Entrada")
    
    class Meta:
        verbose_name = "Entrada de Produto"
        verbose_name_plural = "Entradas de Produtos"
        ordering = ['-data_entrada']
    
    def __str__(self):
        return f"{self.codigo_produto.nome_produto} - Qtd: {self.quantidade} - NF: {self.numero_nota_fiscal}"

class RecebimentoChip(models.Model):
    """Modelo para controle de recebimento de chips"""
    data_solicitacao_compra = models.DateField(verbose_name="Data de Solicitação da Compra")
    data_chegada_golden = models.DateField(verbose_name="Data de Chegada na Golden")
    operadora = models.CharField(max_length=100, verbose_name="Operadora")
    quantidade = models.PositiveIntegerField(verbose_name="Quantidade")
    iccid_inicial = models.CharField(max_length=50, verbose_name="ICCID Inicial")
    iccid_final = models.CharField(max_length=50, verbose_name="ICCID Final")
    data_ativacao = models.DateField(verbose_name="Data de Ativação")
    # Campos opcionais que serão preenchidos posteriormente
    data_envio_configuracao = models.DateField(blank=True, null=True, verbose_name="Data de Envio à Configuração")
    nome_recebedor = models.CharField(max_length=200, blank=True, null=True, verbose_name="Nome do Recebedor")
    quantidade_entregue = models.PositiveIntegerField(default=0, verbose_name="Quantidade Entregue")
    data_cadastro = models.DateTimeField(auto_now_add=True, verbose_name="Data de Cadastro")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")
    
    class Meta:
        verbose_name = "Recebimento de Chip"
        verbose_name_plural = "Recebimentos de Chips"
        ordering = ['-data_cadastro']
    
    def __str__(self):
        return f"{self.operadora} - Qtd: {self.quantidade} - {self.data_chegada_golden.strftime('%d/%m/%Y')}"
    
    @property
    def quantidade_restante(self):
        """Retorna a quantidade de chips ainda disponíveis"""
        return self.quantidade - self.quantidade_entregue
    
    @property
    def percentual_entregue(self):
        """Retorna o percentual de chips já entregues"""
        if self.quantidade == 0:
            return 0
        return round((self.quantidade_entregue / self.quantidade) * 100, 1)

class EntregaChip(models.Model):
    """Modelo para registrar entregas parciais de chips"""
    recebimento = models.ForeignKey(RecebimentoChip, on_delete=models.CASCADE, related_name='entregas', verbose_name="Recebimento")
    quantidade_entregue = models.PositiveIntegerField(verbose_name="Quantidade Entregue")
    responsavel = models.CharField(max_length=200, verbose_name="Responsável pela Entrega")
    data_entrega = models.DateTimeField(auto_now_add=True, verbose_name="Data da Entrega")
    observacao = models.TextField(blank=True, null=True, verbose_name="Observação")
    
    class Meta:
        verbose_name = "Entrega de Chip"
        verbose_name_plural = "Entregas de Chips"
        ordering = ['-data_entrega']
    
    def __str__(self):
        return f"Entrega de {self.quantidade_entregue} chips - {self.responsavel} - {self.data_entrega.strftime('%d/%m/%Y %H:%M')}"

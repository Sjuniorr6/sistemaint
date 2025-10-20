from django.core.mail import EmailMessage

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import os
from django.conf import settings
from django.http import HttpResponse
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import os
from django.conf import settings
from .models import registrodemanutencao
from django.views.generic import ListView, CreateView, DetailView, DeleteView, UpdateView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.mixins import  PermissionRequiredMixin,LoginRequiredMixin
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json 
# Importações dos modelos e formulários
from .models import registrodemanutencao, ImagemRegistro,retorno
from requisicao.models import Requisicoes
from .forms import FormulariosForm, FormulariosUpdateForm,ImagemRegistroFormSet, registrodemanutencao
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import HttpResponse
from.forms import RetornoForm
# View para listar todos os registros de manutenção com paginação.4
#-----------------------------------------------------------------------
class entradasListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = registrodemanutencao
    template_name = "registro_das_entradas.html"
    context_object_name = 'dasentradas'
    
    permission_required = 'registrodemanutencao.view_registrodemanutencao'

    def get_queryset(self):
        # Primeiro, busca todos os registros que correspondem ao filtro de equipamento
        equipamentos_param = self.request.GET.get('numero_equipamento')
        if equipamentos_param:
            queryset = registrodemanutencao.objects.filter(numero_equipamento__icontains=equipamentos_param)
        else:
            # Se não houver filtro de equipamento, aplica o filtro de status normal
            queryset = registrodemanutencao.objects.filter(
                status__in=['Pendente', 'Manutenção', 'Aguardando Aprovação', 'Aprovado pela Diretoria']
            )

        # Aplica os outros filtros
        id_param = self.request.GET.get('id')
        nome_param = self.request.GET.get('nome')
        status_param = self.request.GET.get('status')

        if id_param:
            queryset = queryset.filter(id=id_param)
        if nome_param:
            queryset = queryset.filter(nome__nome__icontains=nome_param)
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        queryset = queryset.order_by('-id')
        return queryset
#----------------------------------------------------------------------------

class FormularioListView( PermissionRequiredMixin,LoginRequiredMixin , ListView):
    model = registrodemanutencao
    template_name = "registrodemanutencaolist.html"
    context_object_name = 'registrodemanutencao'
    paginate_by = 6
    permission_required = 'registrodemanutencao.view_registrodemanutencao'  # Substitua 'registrodemanutencao' pelo nome do seu aplicativo

    def get_queryset(self):
        queryset = super().get_queryset()
        nome = self.request.GET.get('nome', '')
        status = self.request.GET.get('status', '')
        
        if nome:
            queryset = queryset.filter(nome__icontains=nome)
        if status:
            queryset = queryset.filter(status=status)
       
        return queryset

#------------------------------------------------------------------------------
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from .models import registrodemanutencao
from .forms import FormulariosForm

class FormulariosCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = registrodemanutencao
    form_class = FormulariosForm
    template_name = 'registrodemanutencao_create.html'
    success_url = reverse_lazy('FormulariosCreateView')
    permission_required = 'registrodemanutencao.add_registrodemanutencao'

    def form_valid(self, form):
        form.instance.quantidade = self.request.POST.get('quantidade', 0)
        return super().form_valid(form)




# View para atualizar um registro de manutenção existente.
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic.edit import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import registrodemanutencao
from .forms import FormulariosUpdateForm, ImagemRegistroFormSet

# View para atualizar um registro de manutenção existente.
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import UpdateView

# Importar seu modelo, form e formset:
from .models import registrodemanutencao
from .forms import FormulariosUpdateForm, ImagemRegistroFormSet


class FormulariosUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = registrodemanutencao
    form_class = FormulariosUpdateForm
    template_name = 'registrodemanutencao_update.html'
    success_url = reverse_lazy('entradasListView')
    permission_required = 'registrodemanutencao.change_registrodemanutencao'  # Ajuste conforme seu app

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.form_class(request.POST, request.FILES, instance=self.object)
        imagens_formset = ImagemRegistroFormSet(request.POST, request.FILES, instance=self.object)

        if form.is_valid() and imagens_formset.is_valid():
            return self.form_valid(form, imagens_formset)
        else:
            # Para depuração, adicione mais informações
            print("Form errors:", form.errors)
            print("Formset errors:", imagens_formset.errors)
            return self.form_invalid(form, imagens_formset)

    def form_valid(self, form, imagens_formset):
        self.object = form.save()
        imagens_formset.instance = self.object
        imagens_formset.save()
        
        # Verificar se veio da página de histórico e manter os filtros
        referer = self.request.META.get('HTTP_REFERER', '')
        if 'historico' in referer:
            # Manter os filtros aplicados no redirecionamento
            params = self.request.GET.copy()
            if params:
                return redirect(f"{reverse('historico_manutencaoListView')}?{params.urlencode()}")
            return redirect('historico_manutencaoListView')
        
        return redirect(self.success_url)

    def form_invalid(self, form, imagens_formset):
        context = self.get_context_data(form=form, imagens_formset=imagens_formset)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['imagens_formset'] = ImagemRegistroFormSet(
                self.request.POST, self.request.FILES, instance=self.object
            )
        else:
            context['imagens_formset'] = ImagemRegistroFormSet(instance=self.object)
        return context
    
    

class FormularioDetailView(LoginRequiredMixin,  DetailView):
    model = registrodemanutencao
    template_name = 'registrodemanutencao_detail.html'
    context_object_name = 'registrodemanutencao_detail'
     # Substitua 'registrodemanutencao' pelo nome do seu aplicativo

# View para deletar um registro de manutenção.
#-------------------------------------------------------------------------

def aprovar_manut(request, id):
    registro = get_object_or_404(registrodemanutencao, id=id)
    registro.status = 'Aprovado Inteligência'
    registro.save()
    
    subject = f"Manutenção Aprovada: {registro.id}"
    message = f"A manutenção {registro.id} foi aprovada com sucesso. segue pdf para tratativa "
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['comercial@grupogoldensat.com.br']
    
    try:
        send_mail(subject, message, from_email, recipient_list)
        print("Email enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
    
    return redirect('entradasListView')

def reprovar_manut(request, id):
    registro = get_object_or_404(registrodemanutencao, id=id)
    registro.status = 'Manutenção'
    registro.save()
    return redirect('entradasListView')

# View para listar registros de manutenção filtrados pelo status 'Aprovado', 'Reprovado' ou 'Pendente'.

#--------------------------------------

class ConfiguracaoListView(PermissionRequiredMixin,LoginRequiredMixin, ListView):
    model = Requisicoes
    template_name = 'configuracao_list.html'
    context_object_name = 'registros'
    paginate_by = 6
    success_url = reverse_lazy('configuracao_list')
    permission_required = 'registrodemanutencao.view_registrodemanutencao' 
     # Substitua 'registrodemanutencao' pelo nome do seu aplicativo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formulario'] = registrodemanutencao()
        return context
#--------------------------------------

class expedicaoListView( PermissionRequiredMixin,LoginRequiredMixin , ListView):
    model = Requisicoes
    template_name = 'expedicao_list.html'  # Nome do seu template para status "configuração"
    context_object_name = 'requisicoes'
    permission_required = 'registrodemanutencao.view_registrodemanutencao'  # Substitua 'registrodemanutencao' pelo nome do seu aplicativo

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            Q(status__iexact='Expedido') | Q(status__iexact='Aprovado')
        )
        print(queryset.query)  # Isso imprimirá a consulta SQL no console
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Adicione os registros de manutenção ao contexto
        context['registros_manutencao'] = registrodemanutencao.objects.filter(
            Q(status__iexact='Expedido') | Q(status__iexact='Aprovado')
        )
        return context

#-----------------------------------------------------------------------------------

# View para exibir os detalhes de uma expedição específica.
class expedicaoDetailView( PermissionRequiredMixin,LoginRequiredMixin , DetailView):
    model = ImagemRegistro
    template_name = 'expedicao_detail.html'
    context_object_name = 'expedicoes'
    permission_required = 'registrodemanutencao.view_registrodemanutencao'  # Substitua 'registrodemanutencao' pelo nome do seu aplicativo

# View para exibir os detalhes de uma configuração específica.
class configDetailView(LoginRequiredMixin, DetailView):
    model = registrodemanutencao
    template_name = 'config_detail.html'
    context_object_name = 'config_detail'
      # Substitua 'registrodemanutencao' pelo nome do seu aplicativo





# protocolo de entrada(manutenção)
from io import BytesIO
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import Paragraph, Table, SimpleDocTemplate, Spacer, Image, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
import os
from django.conf import settings

def download_protocolo_entrada(request, pk):
    try:
        registro = registrodemanutencao.objects.get(pk=pk)
    except registrodemanutencao.DoesNotExist:
        return HttpResponse("Registro não encontrado.", status=404)

    # Resposta do PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="registro-manutencao-{pk}.pdf"'

    # Criar o documento PDF
    buffer = BytesIO()  # Corrigido aqui
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # Estilos de texto (do primeiro código)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Header", fontSize=14, alignment=1, spaceAfter=10, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="Body", fontSize=9, alignment=0, spaceAfter=6))
    styles.add(ParagraphStyle(name="Footer", fontSize=8, alignment=1, spaceBefore=20))

    elements = []

    # Cabeçalho com Logotipo e QR Code
    try:
        logo_path = os.path.join(settings.MEDIA_ROOT, 'imagens_registros/SIDNEISIDNEISIDNEI.png')
        qr_code_path = os.path.join(settings.MEDIA_ROOT, 'imagens_registros/qrcode.png')

        logo = Image(logo_path, width=60, height=60)
        qr_code = Image(qr_code_path, width=60, height=60)

        header_table = Table([[logo, Paragraph("<b>PROTOCOLO DE ENTRADA</b>", styles["Header"]), qr_code]],
                             colWidths=[80, 380, 60])
        header_table.setStyle(TableStyle([
            ("SPAN", (1, 0), (1, 0)),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(header_table)
    except FileNotFoundError:
        elements.append(Paragraph("<b>PROTOCOLO DE ENTRADA</b>", styles["Header"]))

    elements.append(Spacer(1, 12))

    # Informações de registro
    fields = [
        ["Nº REGISTRO:", str(registro.id), "DATA:", registro.data_criacao.strftime("%d/%m/%Y")],
        ["NOME:", str(registro.nome), "TIPO ENTRADA:", registro.tipo_entrada],
        ["MOTIVO:", registro.motivo, "TIPO PRODUTO:", registro.tipo_produto],
        ["CUSTOMIZAÇÃO:", registro.tipo_customizacao, "ENTREGUE POR:", registro.entregue_por_retirado_por],
        ["QUANTIDADE", registro.quantidade],
    ]

    # Aplique o fundo amarelo nos títulos
    table = Table(fields, colWidths=[100, 250, 100, 100])
    table.setStyle(TableStyle([ 
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#FFFACD")),  # Fundo amarelo suave para a primeira coluna (títulos)
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#FFFACD")),  # Fundo amarelo suave para a terceira coluna (títulos)
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 12))

    # Título para ID Equipamentos
    title_style = ParagraphStyle(
        name="CenteredTitle",
        parent=styles["Body"],
        alignment=1,  # Centraliza horizontalmente
        fontName="Helvetica-Bold",
        fontSize=9,
        spaceAfter=10
    )
    elements.append(Paragraph("<b>ID - EQUIPAMENTOS:</b>", title_style))

    # Tabela de equipamentos
    equipamentos = sorted(map(int, (num.strip() for num in registro.numero_equipamento.split() if num.strip())))
    equipment_grid = [equipamentos[i:i+8] for i in range(0, len(equipamentos), 8)]
    equipment_table_data = []
    for group in equipment_grid:
        row = [str(num) for num in group]
        equipment_table_data.append(row)

    equipment_table = Table(equipment_table_data)
    equipment_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    elements.append(equipment_table)

    # Geração do PDF sem rodapé
    doc.build(elements)

    buffer.seek(0)
    response.write(buffer.read())
    buffer.close()

    return response





# protocolo de manutenção
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os
from io import BytesIO
from django.http import HttpResponse

def format_numero_equipamento(numero_equipamento):
    # Adiciona quebras de linha a cada 25 caracteres para o Número Equipamento
    return '\n'.join([numero_equipamento[i:i+25] for i in range(0, len(numero_equipamento), 25)])
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Image, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
import os
from django.conf import settings
from .models import registrodemanutencao

def find_image_path(filename):
    """
    Localiza a imagem nos diretórios conhecidos.
    Se o valor do filename for um caminho relativo, ajusta para buscar na pasta MEDIA_ROOT.
    """
    # Se o caminho for relativo, ajusta para MEDIA_ROOT
    if not os.path.isabs(filename):
        filename = os.path.join(settings.MEDIA_ROOT, filename)

    # Verifica se o arquivo existe
    if os.path.exists(filename) and os.path.isfile(filename):
        print(f"Imagem encontrada: {filename}")
        return filename

    print(f"Imagem não encontrada: {filename}")
    return None

from reportlab.lib.pagesizes import A4
from reportlab.platypus import PageBreak

from io import BytesIO
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
def download_pdf(request, pk):
    try:
        registro = registrodemanutencao.objects.get(pk=pk)
    except registrodemanutencao.DoesNotExist:
        return HttpResponse("Registro não encontrado.", status=404)

    # Configuração do PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="registro-manutencao-{pk}.pdf"'

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=10,
        leftMargin=50,
        rightMargin=50,
        bottomMargin=50
    )
    elements = []

    # Caminhos das imagens principais (logo e QR Code)
    logo_path = find_image_path('imagens_registros/SIDNEISIDNEISIDNEI.png')
    qr_code_path = find_image_path('imagens_registros/qrcode.png')

    logo_path = logo_path if logo_path else ""
    qr_code_path = qr_code_path if qr_code_path else ""

    # Estilos
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        name="Header",
        fontSize=16,
        alignment=1,
        textColor=colors.HexColor("#004B87")
    )
    body_style = ParagraphStyle(
        name="Body",
        fontSize=9,
        alignment=0,
        wordWrap='LTR'
    )

    # Cabeçalho com logo, título e QR Code
    header_table_data = [
        [
            Image(logo_path, width=80, height=50) if logo_path else "",
            Paragraph("Relatório de Manutenção", header_style),
            Image(qr_code_path, width=80, height=50) if qr_code_path else ""
        ]
    ]

    header_table = Table(header_table_data, colWidths=[120, 300, 120])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # Informações principais na tabela
    data = [
        ["Registro #", Paragraph(str(registro.id), body_style)],
        ["Data", Paragraph(registro.data_criacao.strftime("%d/%m/%Y"), body_style)],
        ["Nome", Paragraph(str(registro.nome or "Não informado"), body_style)],
        ["Tipo de Entrada", Paragraph(registro.tipo_entrada or "Não informado", body_style)],
        ["Tipo de Produto", Paragraph(str(registro.tipo_produto or "Não informado"), body_style)],
        ["Motivo", Paragraph(registro.motivo or "Não informado", body_style)],
        ["Customização", Paragraph(registro.customizacaoo or "Não informado", body_style)],
        ["Número Equipamento", Paragraph(registro.numero_equipamento or "Não informado", body_style)],
        ["Observações", Paragraph(registro.observacoes or "Não informado", body_style)],
        ["Quantidade", Paragraph(str(registro.quantidade or "Não informado"), body_style)],
    ]

    table = Table(data, colWidths=[150, 350])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#D3D3D3")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Dicionário de tratativas
    tratativas = {
        "Oxidação": """
        Gostaríamos de informá-lo(a) que, após a análise técnica da Isca de Carga que nos foi encaminhada para manutenção, foi identificada a presença de oxidação nos componentes do equipamento. Após uma inspeção detalhada, concluímos que a causa principal dessa oxidação é a má utilização do equipamento.
        A oxidação ocorreu devido à exposição inadequada do equipamento a condições ambientais adversas. Essa situação comprometeu a integridade dos componentes internos da isca, o que afeta o seu desempenho e pode levar a falhas técnicas.
        Destacamos que, para evitar danos semelhantes no futuro, é fundamental que o equipamento seja utilizado de acordo com as orientações de uso e armazenamento, conforme descrito no manual do usuário. O armazenamento em ambiente seco e arejado é essencial para prolongar a vida útil da Isca de Carga e evitar a corrosão dos seus componentes.
        Informamos também que, em função da oxidação causada pelo uso inadequado, será necessário realizar a troca do equipamento com custo adicional, o qual será informado antes da execução do serviço, conforme a política de manutenção.
        Recomendamos que, após a conclusão da situação, seja seguido rigorosamente o manual de cuidados e utilização do equipamento para evitar problemas semelhantes.
    """,
        "Placa Danificada": """
        Após uma análise técnica detalhada da Isca de Carga que foi enviada para manutenção, identificamos que a placa do equipamento sofreu danos físicos significativos. O diagnóstico aponta que esses danos foram causados por uso inadequado e condições operacionais impróprias.
        A placa danificada foi exposta a fatores que não estão em conformidade com as orientações do fabricante, como sobrecarga de corrente e choques, o que resultou em falhas nos componentes da placa, prejudicando a operação do equipamento.
        Gostaríamos de destacar que, para garantir o funcionamento correto e prolongar a vida útil da Isca de Carga, é fundamental seguir as recomendações de uso e manutenção descritas no manual do usuário. O uso adequado do equipamento, sem exposição a condições extremas, é crucial para evitar esse tipo de dano.
        Devido à natureza do dano e ao uso inadequado, será necessário realizar a troca do equipamento, com custos adicionais associados, conforme nossa política de manutenção. Antes de iniciarmos qualquer serviço, o valor será comunicado e acordado com o cliente.
        Estamos à disposição para fornecer mais informações sobre o processo. Reforçamos a importância de seguir as orientações de uso para evitar problemas semelhantes no futuro.
    """,
        "Placa danificada SEM CUSTO": """Após a análise técnica realizada em sua Isca de Carga, identificamos que a placa do equipamento sofreu danos físicos durante o uso. No entanto, após avaliação detalhada, concluímos que o dano foi causado por fatores fora do controle do usuário ou devido a falhas de fabricação, e não por uso inadequado.
Dessa forma, gostaríamos de informar que, devido à natureza do problema, não será cobrado nenhum custo pela placa danificada. A substituição do equipamento será realizada sem custos adicionais para o cliente, conforme nossa política de garantia.
Agradecemos a confiança e garantimos que o equipamento será trocado por um novo equipamento em perfeito estado de funcionamento. Continuamos à disposição para esclarecer qualquer dúvida ou fornecer mais informações.
""",
        "USB Danificado": """Após a análise técnica da Isca de Carga que foi enviada para manutenção, identificamos que o USB do equipamento sofreu danos físicos. O diagnóstico indica que o problema foi causado por uso inadequado, inserção incorreta do cabo e exposição a condições externas que comprometem a integridade do conector.
Dado que o dano foi causado por fatores relacionados ao uso inadequado do equipamento, o reparo do USB será realizado com custo adicional. O valor para a substituição do componente será informado previamente, conforme nossa política de manutenção.
Gostaríamos de ressaltar a importância de seguir as recomendações de uso descritas no manual do usuário para evitar danos futuros ao equipamento. Armazenar e manusear o USB de forma adequada, evitando forçar o conector e expô-lo a condições adversas, ajuda a garantir a longevidade do dispositivo.
Estamos à disposição para fornecer o orçamento detalhado e esclarecer qualquer dúvida sobre o processo de reparo.
""",
        "USB Danificado SEM CUSTO": """Após a análise técnica da Isca de Carga que nos foi enviada para manutenção, identificamos que o USB do equipamento não sofreu danos físicos. Contudo, após uma investigação detalhada, concluímos que o problema foi causado por fatores fora do controle do usuário ou devido a uma falha de fabricação.
Dessa forma, gostaríamos de informar que a troca do equipamento será realizada sem custo adicional para o cliente, conforme nossa política de garantia. 
Agradecemos a confiança depositada em nossos serviços e reforçamos que estamos à disposição para quaisquer dúvidas ou para fornecer mais informações sobre o processo de manutenção.
""",
        "Botão de acionamento Danificado": """Gostaríamos de informá-lo(a) que, após a análise técnica do equipamento que nos foi encaminhado para manutenção, foi identificado um dano no botão de acionamento. Após uma inspeção detalhada, concluímos que a causa principal desse dano pode estar associada ao uso inadequado, aplicação de excesso de força durante o acionamento.
O dano identificado compromete o funcionamento normal do equipamento, podendo ocasionar interrupções no uso e possíveis sobrecargas em componentes internos, o que pode levar a falhas secundárias. Essas consequências reforçam a importância de uma utilização cuidadosa do equipamento.
Destacamos que, para evitar danos semelhantes no futuro, é essencial que sejam seguidas as orientações de uso descritas no manual do usuário. Recomenda-se evitar o uso de força excessiva e manusear o equipamento com cuidado para prolongar sua vida útil e garantir seu pleno funcionamento.
Informamos também que, em função do dano causado, será necessário realizar reparos com custo adicional. O valor será informado antes da execução do serviço, conforme nossa política de manutenção.
Estamos à disposição para fornecer qualquer esclarecimento adicional e garantir que o equipamento funcione adequadamente. Recomendamos que, seja seguido rigorosamente o manual de cuidados e utilização para evitar problemas semelhantes.
""",
        "Botão de acionamento Danificado SEM CUSTO": "O botão será reparado sem custo adicional.",
        "Antena LoRa Danificada": """Gostaríamos de informá-lo(a) que, após a análise técnica do equipamento que nos foi encaminhado para manutenção, foi identificado um dano na antena LoRa. Após uma inspeção detalhada, concluímos que o dano compromete a comunicação sem fio e a performance geral do sistema.
A análise indica que a causa principal do dano pode estar relacionada a manuseio inadequado, como impactos acidentais e aplicação de força excessiva.
O dano identificado pode ocasionar interrupções na comunicação do equipamento, resultando em falhas na transmissão ou recepção de dados. Essas falhas impactam diretamente a funcionalidade do sistema e podem comprometer sua eficiência em operações críticas.
Destacamos que, para evitar problemas semelhantes no futuro, é essencial que o equipamento seja manuseado com cuidado, evitando impactos ou a aplicação de força excessiva. Seguir as orientações de uso descritas no manual do usuário contribui significativamente para a preservação da antena e do desempenho geral do sistema.
Informamos também que, em função do dano identificado, será necessário realizar a troca do equipamento com custo adicional. O valor será informado antes da execução do serviço, em conformidade com nossa política de manutenção.
Estamos à disposição para fornecer qualquer esclarecimento adicional. Recomendamos que, após a conclusão da tratativa, sejam seguidas rigorosamente as orientações de cuidados e utilização para evitar problemas semelhantes.
""",
        "Antena 4G danificada":"""Gostaríamos de informá-lo(a) que, após a análise técnica do equipamento que nos foi encaminhado para manutenção, foi constatado que a antena 4G apresenta danos físicos e funcionais. Essa situação impossibilita a transmissão e recepção de dados de forma adequada, comprometendo o desempenho do sistema.
Após uma inspeção detalhada, concluímos que o dano à antena pode ter sido causado por manuseio inadequado, como quedas ou impactos. Esses fatores contribuíram para a degradação da funcionalidade da antena e, consequentemente, do equipamento.
Uma antena 4G danificada pode resultar em perda total ou parcial de conectividade, comprometendo o acesso à rede móvel, além de causar interrupções na comunicação de dados. Isso impacta diretamente o desempenho de sistemas dependentes de conectividade e limita as funcionalidades do equipamento.
Destacamos que, para evitar problemas semelhantes no futuro, é fundamental manusear o equipamento com cuidado, evitando quedas ou impactos. Seguir as orientações de uso descritas no manual do usuário é essencial para preservar a funcionalidade e prolongar a vida útil do equipamento.
Informamos também que, em função do dano identificado, será necessário a troca do equipamento com custo adicional. O valor será informado antes da execução do serviço, em conformidade com nossa política de manutenção.
Estamos à disposição para fornecer qualquer esclarecimento adicional. Recomendamos que, após a conclusão da tratativa , sejam seguidas rigorosamente as orientações de cuidados e utilização para prevenir problemas semelhantes
 """,
        "Sem problemas Identificados": "Nenhum problema identificado no equipamento após a análise.",
"Avarias Fisicas Graves" : """
        Durante a inspeção técnica constatou-se que os equipamentos apresentam avarias físicas de caráter grave, evidenciadas por fraturas estruturais, deformações mecânicas e desprendimento de componentes internos e externos. Tais danos comprometem integralmente a integridade funcional dos dispositivos,
        impedindo sua correta operação e colocando em risco a segurança de usuários e processos. Diante do estado atual de deterioração, os equipamentos são considerados irrecuperáveis para fins de uso operacional, sendo recomendada sua imediata condenação e retirada de serviço, bem como o descarte ou substituição conforme as normas vigentes de gestão de ativos e resíduos eletrônicos.
        """
    }

    # Adicionar imagens e tratativas
    for imagem in registro.imagens.all():
        tipo_problema = imagem.tipo_problema or "Não informado"
        info_text = f"ID : {imagem.id_equipamento or 'Não informado'} - Tipo de Problema: {tipo_problema} - Faturamento: {imagem.faturamento or 'Não informado'}"
        elements.append(Paragraph(info_text, body_style))
        elements.append(Spacer(1, 10))

        # Processar imagens
        image_path1 = find_image_path(str(imagem.imagem)) if imagem.imagem else None
        image_path2 = find_image_path(str(imagem.imagem2)) if imagem.imagem2 else None

        image_path1 = image_path1 or ""
        image_path2 = image_path2 or ""

        images_data = []
        img1 = Image(image_path1, width=200, height=100) if image_path1 else Paragraph("", body_style)
        img2 = Image(image_path2, width=200, height=100) if image_path2 else Paragraph("", body_style)

        images_data.append([img1, img2])

        images_table = Table(images_data, colWidths=[220, 220])
        images_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))

        elements.append(images_table)
        elements.append(Spacer(1, 10))

        # Tratativa
        texto_tratativa = tratativas.get(tipo_problema, "Problemas não especificados.")
        elements.append(Paragraph(f"Tratativa: {texto_tratativa}", body_style))
        elements.append(Spacer(1, 20))

    # Geração do PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response

class CriarRetornoView(CreateView):
    model = retorno
    form_class = RetornoForm
    template_name = 'criar_retorno.html'
    

    def form_valid(self, form):
        self.object = form.save()
        return redirect('download_pdf', pk=self.object.pk)

class DownloadPDFView(DetailView):
    model = retorno

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="registro-manutencao-{self.object.pk}.pdf"'

        p = canvas.Canvas(response, pagesize=letter)
        p.setTitle(f'Registro de Manutenção - {self.object.pk}')

        # Defina as fontes e cores
        p.setFont("Helvetica-Bold", 16)
        p.setFillColor(colors.HexColor("#004B87"))

        # Cabeçalho
        y_position = 750
        p.drawString(100, y_position, "Relatório de Manutenção")
        y_position -= 30

        # Adicionar as imagens lado a lado com fundo branco
        imagem_padrao = os.path.join(settings.MEDIA_ROOT, 'imagens_registros/SIDNEISIDNEISIDNEI.png')
        imagem_qrcode = os.path.join(settings.MEDIA_ROOT, 'imagens_registros/qrcode.png')
        image_width = 200
        image_height = 100
        page_width, page_height = letter
        total_width = image_width * 2 + 20  # Largura total das duas imagens com um espaço entre elas
        x_position = (page_width - total_width) / 2

        # Desenhar um retângulo branco como fundo para as imagens
        p.setFillColor(colors.white)
        p.rect(x_position - 10, y_position - image_height - 10, total_width + 20, image_height + 20, fill=1)

        # Desenhar a primeira imagem
        p.drawImage(imagem_padrao, x_position, y_position - image_height, width=image_width, height=image_height)
        # Desenhar a segunda imagem ao lado da primeira
        p.drawImage(imagem_qrcode, x_position + image_width + 20, y_position - image_height, width=image_width, height=image_height)
        y_position -= (image_height + 20)

        # Adicionar a imagem do campo 'imagem' do modelo 'retorno'
        if self.object.imagem:
            image_path = os.path.join(settings.MEDIA_ROOT, str(self.object.imagem))
            p.drawImage(image_path, 100, y_position - 200, width=200, height=200)
            y_position -= 220

        # Restaurar a fonte para o conteúdo principal
        p.setFont("Helvetica", 12)
        p.setFillColor(colors.black)

        #   # Desenhe o conteúdo do PDF
        p.drawString(100, y_position, f"Cliente: {self.object.cliente}")
        y_position -= 20
        p.drawString(100, y_position, f"Produto: {self.object.produto}")
        y_position -= 20
        p.drawString(100, y_position, f"Tipo de Problema: {self.object.tipo_problema}")
        y_position -= 20
        p.drawString(100, y_position, f"ID Equipamentos: {self.object.id_equipamentos}")
        y_position -= 20
       

        # Feche o objeto PDF e entregue o PDF ao navegador.
        p.showPage()
        p.save()
        return response


class ListaRetornosView(ListView):
    model = retorno
    template_name = 'lista_retornos.html'
    context_object_name = 'retornos'





def minha_view(request):
    if request.method == 'POST':
        form = FormulariosUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('alguma_url_de_sucesso')
    else:
        form = FormulariosUpdateForm()
    return render(request, 'meu_template.html', {'form': form})
# Função para aprovar um registro de manutenção.


class historico_manutencaoListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = registrodemanutencao
    template_name = 'historico_manutencao.html'  # Nome do seu template para status "configuração"
    context_object_name = 'dasentradas'
    paginate_by = 13  # Adicionar paginação
    
    permission_required = 'registrodemanutencao.view_registrodemanutencao'  # Substitua 'registrodemanutencao' pelo nome do seu aplicativo
    
    def get_queryset(self):
        queryset = registrodemanutencao.objects.all().order_by('-id')  # Ordenar por ID decrescente
        
        # Filtros existentes
        nome = self.request.GET.get('nome')
        retornoequipamentos = self.request.GET.get('retornoequipamentos')
        status_tratativa = self.request.GET.get('status_tratativa')
        
        # Novos filtros
        id_registro = self.request.GET.get('id_registro')
        tipo_entrada = self.request.GET.get('tipo_entrada')
        status = self.request.GET.get('status')
        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        
        # Aplicar filtros existentes
        if nome:
            queryset = queryset.filter(nome__nome__icontains=nome)
        
        if retornoequipamentos:
            queryset = queryset.filter(retornoequipamentos=retornoequipamentos)
        
        if status_tratativa:
            queryset = queryset.filter(status_tratativa=status_tratativa)
        
        # Aplicar novos filtros
        if id_registro:
            queryset = queryset.filter(id=id_registro)
        
        if tipo_entrada:
            queryset = queryset.filter(tipo_entrada=tipo_entrada)
        
        if status:
            queryset = queryset.filter(status=status)
        
        # Filtro de range de datas
        if data_inicio and data_fim:
            queryset = queryset.filter(data_criacao__date__range=[data_inicio, data_fim])
        elif data_inicio:
            queryset = queryset.filter(data_criacao__date__gte=data_inicio)
        elif data_fim:
            queryset = queryset.filter(data_criacao__date__lte=data_fim)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Manter os filtros aplicados no contexto para a paginação
        context['filtros_aplicados'] = {
            'nome': self.request.GET.get('nome', ''),
            'retornoequipamentos': self.request.GET.get('retornoequipamentos', ''),
            'status_tratativa': self.request.GET.get('status_tratativa', ''),
            'id_registro': self.request.GET.get('id_registro', ''),
            'tipo_entrada': self.request.GET.get('tipo_entrada', ''),
            'status': self.request.GET.get('status', ''),
            'data_inicio': self.request.GET.get('data_inicio', ''),
            'data_fim': self.request.GET.get('data_fim', ''),
        }
        
        # Adicionar as escolhas dos filtros
        context['status_tratativa_choices'] = registrodemanutencao.STATUS_TRATATIVA_CHOICES
        context['tipo_entrada_choices'] = registrodemanutencao.ENTRADA
        context['status_choices'] = registrodemanutencao.STATUS_CHOICES
        
        return context


@csrf_exempt
def atualizar_status_tratativa(request, registro_id):
    if request.method == 'POST':
        try:
            registro = get_object_or_404(registrodemanutencao, id=registro_id)
            data = json.loads(request.body)
            novo_status = data.get('status_tratativa')
            
            if novo_status:
                registro.status_tratativa = novo_status
                registro.save()
                return JsonResponse({'success': True, 'message': 'Status atualizado com sucesso'})
            else:
                return JsonResponse({'success': False, 'error': 'Status não fornecido'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})


def clean_id_equipamentos(self):
        data = self.cleaned_data['id_equipamentos']
        if len(data) > 6:
            data = data[6:]  # Remove os primeiros 6 caracteres
        return data



from django.core.mail import EmailMessage
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

from django.core.mail import EmailMessage
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from io import BytesIO
import os


def aprovar_manutencao(request, id):
    registro = get_object_or_404(registrodemanutencao, id=id)
    registro.status = 'Comercial'
    registro.save()

    # Configuração do PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=10,
        leftMargin=50,
        rightMargin=50,
        bottomMargin=50
    )
    elements = []

    # Caminhos das imagens principais (logo e QR Code)
    logo_path = find_image_path('imagens_registros/SIDNEISIDNEISIDNEI.png')
    qr_code_path = find_image_path('imagens_registros/qrcode.png')

    logo_path = logo_path if logo_path else ""
    qr_code_path = qr_code_path if qr_code_path else ""

    # Estilos
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        name="Header",
        fontSize=16,
        alignment=1,
        textColor=colors.HexColor("#004B87")
    )
    body_style = ParagraphStyle(
        name="Body",
        fontSize=9,
        alignment=0,
        wordWrap='LTR'
    )

    # Cabeçalho com logo, título e QR Code
    header_table_data = [
        [
            Image(logo_path, width=80, height=50) if logo_path else "",
            Paragraph("Relatório de Manutenção", header_style),
            Image(qr_code_path, width=80, height=50) if qr_code_path else ""
        ]
    ]

    header_table = Table(header_table_data, colWidths=[120, 300, 120])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # Informações principais na tabela
    data = [
        ["Registro #", Paragraph(str(registro.id), body_style)],
        ["Data", Paragraph(registro.data_criacao.strftime("%d/%m/%Y"), body_style)],
        ["Nome", Paragraph(str(registro.nome or "Não informado"), body_style)],
        ["Tipo de Entrada", Paragraph(registro.tipo_entrada or "Não informado", body_style)],
        ["Tipo de Produto", Paragraph(str(registro.tipo_produto or "Não informado"), body_style)],
        ["Motivo", Paragraph(registro.motivo or "Não informado", body_style)],
        ["Customização", Paragraph(registro.customizacaoo or "Não informado", body_style)],
        ["Número Equipamento", Paragraph(registro.numero_equipamento or "Não informado", body_style)],
        ["Observações", Paragraph(registro.observacoes or "Não informado", body_style)],
        ["Quantidade", Paragraph(str(registro.quantidade or "Não informado"), body_style)],
    ]

    table = Table(data, colWidths=[150, 350])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#D3D3D3")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    # Dicionário de tratativas
    tratativas = {
        "Oxidação": """
        Gostaríamos de informá-lo(a) que, após a análise técnica da Isca de Carga que nos foi encaminhada para manutenção, foi identificada a presença de oxidação nos componentes do equipamento. Após uma inspeção detalhada, concluímos que a causa principal dessa oxidação é a má utilização do equipamento.
        A oxidação ocorreu devido à exposição inadequada do equipamento a condições ambientais adversas. Essa situação comprometeu a integridade dos componentes internos da isca, o que afeta o seu desempenho e pode levar a falhas técnicas.
        Destacamos que, para evitar danos semelhantes no futuro, é fundamental que o equipamento seja utilizado de acordo com as orientações de uso e armazenamento, conforme descrito no manual do usuário. O armazenamento em ambiente seco e arejado é essencial para prolongar a vida útil da Isca de Carga e evitar a corrosão dos seus componentes.
        Informamos também que, em função da oxidação causada pelo uso inadequado, será necessário realizar a troca do equipamento com custo adicional, o qual será informado antes da execução do serviço, conforme a política de manutenção.
        Recomendamos que, após a conclusão da situação, seja seguido rigorosamente o manual de cuidados e utilização do equipamento para evitar problemas semelhantes.
    """,
        "Placa Danificada": """
        Após uma análise técnica detalhada da Isca de Carga que foi enviada para manutenção, identificamos que a placa do equipamento sofreu danos físicos significativos. O diagnóstico aponta que esses danos foram causados por uso inadequado e condições operacionais impróprias.
        A placa danificada foi exposta a fatores que não estão em conformidade com as orientações do fabricante, como sobrecarga de corrente e choques, o que resultou em falhas nos componentes da placa, prejudicando a operação do equipamento.
        Gostaríamos de destacar que, para garantir o funcionamento correto e prolongar a vida útil da Isca de Carga, é fundamental seguir as recomendações de uso e manutenção descritas no manual do usuário. O uso adequado do equipamento, sem exposição a condições extremas, é crucial para evitar esse tipo de dano.
        Devido à natureza do dano e ao uso inadequado, será necessário realizar a troca do equipamento, com custos adicionais associados, conforme nossa política de manutenção. Antes de iniciarmos qualquer serviço, o valor será comunicado e acordado com o cliente.
        Estamos à disposição para fornecer mais informações sobre o processo. Reforçamos a importância de seguir as orientações de uso para evitar problemas semelhantes no futuro.
    """,
        "Placa danificada SEM CUSTO": """Após a análise técnica realizada em sua Isca de Carga, identificamos que a placa do equipamento sofreu danos físicos durante o uso. No entanto, após avaliação detalhada, concluímos que o dano foi causado por fatores fora do controle do usuário ou devido a falhas de fabricação, e não por uso inadequado.
Dessa forma, gostaríamos de informar que, devido à natureza do problema, não será cobrado nenhum custo pela placa danificada. A substituição do equipamento será realizada sem custos adicionais para o cliente, conforme nossa política de garantia.
Agradecemos a confiança e garantimos que o equipamento será trocado por um novo equipamento em perfeito estado de funcionamento. Continuamos à disposição para esclarecer qualquer dúvida ou fornecer mais informações.
""",
        "USB Danificado": """Após a análise técnica da Isca de Carga que foi enviada para manutenção, identificamos que o USB do equipamento sofreu danos físicos. O diagnóstico indica que o problema foi causado por uso inadequado, inserção incorreta do cabo e exposição a condições externas que comprometem a integridade do conector.
Dado que o dano foi causado por fatores relacionados ao uso inadequado do equipamento, o reparo do USB será realizado com custo adicional. O valor para a substituição do componente será informado previamente, conforme nossa política de manutenção.
Gostaríamos de ressaltar a importância de seguir as recomendações de uso descritas no manual do usuário para evitar danos futuros ao equipamento. Armazenar e manusear o USB de forma adequada, evitando forçar o conector e expô-lo a condições adversas, ajuda a garantir a longevidade do dispositivo.
Estamos à disposição para fornecer o orçamento detalhado e esclarecer qualquer dúvida sobre o processo de reparo.
""",
        "USB Danificado SEM CUSTO": """Após a análise técnica da Isca de Carga que nos foi enviada para manutenção, identificamos que o USB do equipamento não sofreu danos físicos. Contudo, após uma investigação detalhada, concluímos que o problema foi causado por fatores fora do controle do usuário ou devido a uma falha de fabricação.
Dessa forma, gostaríamos de informar que a troca do equipamento será realizada sem custo adicional para o cliente, conforme nossa política de garantia. 
Agradecemos a confiança depositada em nossos serviços e reforçamos que estamos à disposição para quaisquer dúvidas ou para fornecer mais informações sobre o processo de manutenção.
""",
        "Botão de acionamento Danificado": """Gostaríamos de informá-lo(a) que, após a análise técnica do equipamento que nos foi encaminhado para manutenção, foi identificado um dano no botão de acionamento. Após uma inspeção detalhada, concluímos que a causa principal desse dano pode estar associada ao uso inadequado, aplicação de excesso de força durante o acionamento.
O dano identificado compromete o funcionamento normal do equipamento, podendo ocasionar interrupções no uso e possíveis sobrecargas em componentes internos, o que pode levar a falhas secundárias. Essas consequências reforçam a importância de uma utilização cuidadosa do equipamento.
Destacamos que, para evitar danos semelhantes no futuro, é essencial que sejam seguidas as orientações de uso descritas no manual do usuário. Recomenda-se evitar o uso de força excessiva e manusear o equipamento com cuidado para prolongar sua vida útil e garantir seu pleno funcionamento.
Informamos também que, em função do dano causado, será necessário realizar reparos com custo adicional. O valor será informado antes da execução do serviço, conforme nossa política de manutenção.
Estamos à disposição para fornecer qualquer esclarecimento adicional e garantir que o equipamento funcione adequadamente. Recomendamos que, seja seguido rigorosamente o manual de cuidados e utilização para evitar problemas semelhantes.
""",
        "Botão de acionamento Danificado SEM CUSTO": "O botão será reparado sem custo adicional.",
        "Antena LoRa Danificada": """Gostaríamos de informá-lo(a) que, após a análise técnica do equipamento que nos foi encaminhado para manutenção, foi identificado um dano na antena LoRa. Após uma inspeção detalhada, concluímos que o dano compromete a comunicação sem fio e a performance geral do sistema.
A análise indica que a causa principal do dano pode estar relacionada a manuseio inadequado, como impactos acidentais e aplicação de força excessiva.
O dano identificado pode ocasionar interrupções na comunicação do equipamento, resultando em falhas na transmissão ou recepção de dados. Essas falhas impactam diretamente a funcionalidade do sistema e podem comprometer sua eficiência em operações críticas.
Destacamos que, para evitar problemas semelhantes no futuro, é essencial que o equipamento seja manuseado com cuidado, evitando impactos ou a aplicação de força excessiva. Seguir as orientações de uso descritas no manual do usuário contribui significativamente para a preservação da antena e do desempenho geral do sistema.
Informamos também que, em função do dano identificado, será necessário realizar a troca do equipamento com custo adicional. O valor será informado antes da execução do serviço, em conformidade com nossa política de manutenção.
Estamos à disposição para fornecer qualquer esclarecimento adicional. Recomendamos que, após a conclusão da tratativa, sejam seguidas rigorosamente as orientações de cuidados e utilização para evitar problemas semelhantes.
""", "Antena 4G danificada":"""Gostaríamos de informá-lo(a) que, após a análise técnica do equipamento que nos foi encaminhado para manutenção, foi constatado que a antena 4G apresenta danos físicos e funcionais. Essa situação impossibilita a transmissão e recepção de dados de forma adequada, comprometendo o desempenho do sistema.
Após uma inspeção detalhada, concluímos que o dano à antena pode ter sido causado por manuseio inadequado, como quedas ou impactos. Esses fatores contribuíram para a degradação da funcionalidade da antena e, consequentemente, do equipamento.
Uma antena 4G danificada pode resultar em perda total ou parcial de conectividade, comprometendo o acesso à rede móvel, além de causar interrupções na comunicação de dados. Isso impacta diretamente o desempenho de sistemas dependentes de conectividade e limita as funcionalidades do equipamento.
Destacamos que, para evitar problemas semelhantes no futuro, é fundamental manusear o equipamento com cuidado, evitando quedas ou impactos. Seguir as orientações de uso descritas no manual do usuário é essencial para preservar a funcionalidade e prolongar a vida útil do equipamento.
Informamos também que, em função do dano identificado, será necessário a troca do equipamento com custo adicional. O valor será informado antes da execução do serviço, em conformidade com nossa política de manutenção.
Estamos à disposição para fornecer qualquer esclarecimento adicional. Recomendamos que, após a conclusão da tratativa , sejam seguidas rigorosamente as orientações de cuidados e utilização para prevenir problemas semelhantes
 """,
        "Sem problemas Identificados": "Nenhum problema identificado no equipamento após a análise.",
"Avarias Fisicas Graves" : """
        Durante a inspeção técnica constatou-se que os equipamentos apresentam avarias físicas de caráter grave, evidenciadas por fraturas estruturais, deformações mecânicas e desprendimento de componentes internos e externos. Tais danos comprometem integralmente a integridade funcional dos dispositivos,
        impedindo sua correta operação e colocando em risco a segurança de usuários e processos. Diante do estado atual de deterioração, os equipamentos são considerados irrecuperáveis para fins de uso operacional, sendo recomendada sua imediata condenação e retirada de serviço, bem como o descarte ou substituição conforme as normas vigentes de gestão de ativos e resíduos eletrônicos.
        """
    }

    # Adicionar imagens e tratativas
    for imagem in registro.imagens.all():
        tipo_problema = imagem.tipo_problema or "Não informado"
        info_text = f"ID : {imagem.id_equipamento or 'Não informado'} - Tipo de Problema: {tipo_problema} - Faturamento: {imagem.faturamento or 'Não informado'}"
        elements.append(Paragraph(info_text, body_style))
        elements.append(Spacer(1, 10))

        # Processar imagens
        image_path1 = find_image_path(str(imagem.imagem)) if imagem.imagem else None
        image_path2 = find_image_path(str(imagem.imagem2)) if imagem.imagem2 else None

        image_path1 = image_path1 or ""
        image_path2 = image_path2 or ""

        images_data = []
        img1 = Image(image_path1, width=200, height=100) if image_path1 else Paragraph("", body_style)
        img2 = Image(image_path2, width=200, height=100) if image_path2 else Paragraph("", body_style)

        images_data.append([img1, img2])

        images_table = Table(images_data, colWidths=[220, 220])
        images_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))

        elements.append(images_table)
        elements.append(Spacer(1, 10))

        # Tratativa
        texto_tratativa = tratativas.get(tipo_problema, "Problemas não especificados.")
        elements.append(Paragraph(f"Tratativa: {texto_tratativa}", body_style))
        elements.append(Spacer(1, 20))

    # Geração do PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    # Enviar o email com o PDF em anexo
    subject = f"Manutenção Aprovada: {registro.id}"
    message = f"A manutenção {registro.id} foi aprovada com sucesso. Em anexo está o relatório detalhado da manutenção."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['financeiro@grupogoldensat.com.br','comercial@grupogoldensat.com.br','comercial@grupogoldensat.com.br']

    email = EmailMessage(subject, message, from_email, recipient_list)
    email.attach(f'relatorio-manutencao-{registro.id}.pdf', pdf, 'application/pdf')
    
    try:
        email.send()
        messages.success(request, "Manutenção aprovada e relatório enviado com sucesso!")
    except Exception as e:
        messages.error(request, f"Erro ao enviar email: {str(e)}")
    
    return redirect('entradasListView')   

    

@login_required
def reprovar_manutencao(request, id):  # Alterar o nome da função para corresponder ao URL
    requisicao = get_object_or_404(registrodemanutencao, id=id)
    requisicao.status = 'Manutenção'  # Certifique-se de que este é o status correto
    requisicao.save()
    return redirect('entradasListView')
def editado_manutencao(request, pk):  # O nome da função está correto
    requisicao = get_object_or_404(registrodemanutencao, id=pk)  # Use 'pk' aqui
    requisicao.status = 'Aguardando Aprovação'  # Verifique se este é o status correto
    requisicao.save()
    return redirect('entradasListView') 


@login_required
def reprovar_manutencao2(request, id):  # Alterar o nome da função para corresponder ao URL
    requisicao = get_object_or_404(registrodemanutencao, id=id)
    requisicao.status = 'Reprovado pela Inteligência'  # Certifique-se de que este é o status correto
    requisicao.save()
    return redirect('entradasListView')

# Função decorada com @login_required para garantir que apenas usuários autenticados possam acessá-la.
@login_required
def rejeitadas(request, id):
    manutencao = get_object_or_404(registrodemanutencao, id=id)
    manutencao.status = 'Aprovado'
    manutencao.save()
    return redirect('rejeitadas')

# Função para renderizar o formulário de manutenção.
@login_required
def formulariom_view(request):
    return render(request, 'registrodemanutencao.html')

# Função para listar registros de manutenção.
@login_required
def manutencaolist(request):
    return render(request, 'manutencao_list.html')

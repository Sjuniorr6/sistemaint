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
from .models import registrodemanutencao


def aprovar_manutencao(request, id):
    registro = get_object_or_404(registrodemanutencao, id=id)
    registro.status = 'Comercial'
    registro.save()

    # Geração do PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=10,
        leftMargin=50,
        rightMargin=50,
        bottomMargin=50
    )
    elements = []

    # Caminhos das imagens
    logo_path = os.path.join(settings.MEDIA_ROOT, 'imagens_registros/SIDNEISIDNEISIDNEI.png')
    qr_code_path = os.path.join(settings.MEDIA_ROOT, 'imagens_registros/qrcode.png')

    # Estilos
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(name="Header", fontSize=16, alignment=1, textColor=colors.HexColor("#004B87"))
    body_style = ParagraphStyle(name="Body", fontSize=9, alignment=0)
    centered_style = ParagraphStyle(name="Centered", fontSize=12, alignment=1)

    # Cabeçalho
    header_table_data = [
        [Image(logo_path, width=80, height=50) if os.path.exists(logo_path) else "",
         Paragraph("Relatório de Manutenção", header_style),
         Image(qr_code_path, width=80, height=50) if os.path.exists(qr_code_path) else ""]
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

    # Informações principais
    data = [
        ["Registro #", str(registro.id)],
        ["Data", registro.data_criacao.strftime("%d/%m/%Y")],
        ["Nome", registro.nome],
        ["Tipo de Entrada", registro.tipo_entrada],
        ["Tipo de Produto", registro.tipo_produto],
        ["Motivo", registro.motivo],
        ["Customização", registro.customizacaoo],
        ["Entregue por/Retirado por", registro.entregue_por_retirado_por],
        ["Recebimento", registro.recebimento],
        ["Número Equipamento", registro.numero_equipamento],
        ["Observações", registro.observacoes],
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

    # Adicionar imagens e tratativas
    for imagem in registro.imagens.all():
        elements.append(Paragraph(f"ID equipamento: {imagem.id_equipamento} - Tipo Problema: {imagem.tipo_problema}", centered_style))
        elements.append(Spacer(1, 10))

        image_path = os.path.join(settings.MEDIA_ROOT, str(imagem.imagem))
        if os.path.exists(image_path):
            elements.append(Image(image_path, width=200, height=100))
            elements.append(Spacer(1, 10))

        texto_tratativa = "Descrição genérica para problemas não especificados."
        elements.append(Paragraph(f"Tratativa: {texto_tratativa}", body_style))
        elements.append(Spacer(1, 20))

    # Geração do PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    # Enviar o email com o PDF em anexo
    subject = f"Manutenção Aprovada: {registro.id}"
    message = f"A manutenção {registro.id} foi aprovada com sucesso. Segue PDF para tratativa."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['comercial@grupogoldensat.com.br', 'atendimento@grupogoldensat.com.br', 'julio.cesar@grupogoldensat.com.br']

    email = EmailMessage(subject, message, from_email, recipient_list)
    email.attach(f"registro-manutencao-{registro.id}.pdf", pdf, "application/pdf")
    email.send()

    # Retorna uma resposta ao usuário
    return HttpResponse("Manutenção aprovada e email enviado com sucesso.")

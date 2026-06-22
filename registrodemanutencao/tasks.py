import logging
from io import BytesIO

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

TRATATIVAS = {
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
    "Antena 4G danificada": """Gostaríamos de informá-lo(a) que, após a análise técnica do equipamento que nos foi encaminhado para manutenção, foi constatado que a antena 4G apresenta danos físicos e funcionais. Essa situação impossibilita a transmissão e recepção de dados de forma adequada, comprometendo o desempenho do sistema.
Após uma inspeção detalhada, concluímos que o dano à antena pode ter sido causado por manuseio inadequado, como quedas ou impactos. Esses fatores contribuíram para a degradação da funcionalidade da antena e, consequentemente, do equipamento.
Uma antena 4G danificada pode resultar em perda total ou parcial de conectividade, comprometendo o acesso à rede móvel, além de causar interrupções na comunicação de dados. Isso impacta diretamente o desempenho de sistemas dependentes de conectividade e limita as funcionalidades do equipamento.
Destacamos que, para evitar problemas semelhantes no futuro, é fundamental manusear o equipamento com cuidado, evitando quedas ou impactos. Seguir as orientações de uso descritas no manual do usuário é essencial para preservar a funcionalidade e prolongar a vida útil do equipamento.
Informamos também que, em função do dano identificado, será necessário a troca do equipamento com custo adicional. O valor será informado antes da execução do serviço, em conformidade com nossa política de manutenção.
Estamos à disposição para fornecer qualquer esclarecimento adicional. Recomendamos que, após a conclusão da tratativa, sejam seguidas rigorosamente as orientações de cuidados e utilização para prevenir problemas semelhantes.
""",
    "Sem problemas Identificados": "Nenhum problema identificado no equipamento após a análise.",
    "Avarias Fisicas Graves": """
        Durante a inspeção técnica constatou-se que os equipamentos apresentam avarias físicas de caráter grave, evidenciadas por fraturas estruturais, deformações mecânicas e desprendimento de componentes internos e externos. Tais danos comprometem integralmente a integridade funcional dos dispositivos,
        impedindo sua correta operação e colocando em risco a segurança de usuários e processos. Diante do estado atual de deterioração, os equipamentos são considerados irrecuperáveis para fins de uso operacional, sendo recomendada sua imediata condenação e retirada de serviço, bem como o descarte ou substituição conforme as normas vigentes de gestão de ativos e resíduos eletrônicos.
        """,
}


def _find_image_path(relative_path):
    """Busca o caminho absoluto de uma imagem nas pastas de media configuradas."""
    media_root = settings.MEDIA_ROOT
    candidate = os.path.join(media_root, relative_path)
    if os.path.exists(candidate):
        return candidate
    return None


def _gerar_pdf_manutencao(registro):
    """Gera o PDF do relatório de manutenção e retorna os bytes."""
    import os

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=10,
        leftMargin=50,
        rightMargin=50,
        bottomMargin=50,
    )
    elements = []

    logo_path = _find_image_path("imagens_registros/SIDNEISIDNEISIDNEI.png") or ""
    qr_code_path = _find_image_path("imagens_registros/qrcode.png") or ""

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        name="Header",
        fontSize=16,
        alignment=1,
        textColor=colors.HexColor("#004B87"),
    )
    body_style = ParagraphStyle(
        name="Body",
        fontSize=9,
        alignment=0,
        wordWrap="LTR",
    )

    header_table_data = [
        [
            Image(logo_path, width=80, height=50) if logo_path else "",
            Paragraph("Relatório de Manutenção", header_style),
            Image(qr_code_path, width=80, height=50) if qr_code_path else "",
        ]
    ]
    header_table = Table(header_table_data, colWidths=[120, 300, 120])
    header_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    data = [
        ["Registro #", Paragraph(str(registro.id), body_style)],
        ["Data", Paragraph(registro.data_criacao.strftime("%d/%m/%Y"), body_style)],
        ["Nome", Paragraph(str(registro.nome or "Não informado"), body_style)],
        ["Tipo de Entrada", Paragraph(registro.tipo_entrada or "Não informado", body_style)],
        ["Tipo de Produto", Paragraph(str(registro.tipo_produto or "Não informado"), body_style)],
        ["Customização", Paragraph(registro.customizacaoo or "Não informado", body_style)],
        ["Número Equipamento", Paragraph(registro.numero_equipamento or "Não informado", body_style)],
        ["Observações", Paragraph(registro.observacoes or "Não informado", body_style)],
        ["Quantidade", Paragraph(str(registro.quantidade or "Não informado"), body_style)],
    ]
    table = Table(data, colWidths=[150, 350])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D3D3D3")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 20))

    for imagem in registro.imagens.all():
        tipo_problema = imagem.tipo_problema or "Não informado"
        info_text = (
            f"ID : {imagem.id_equipamento or 'Não informado'} "
            f"- Tipo de Problema: {tipo_problema} "
            f"- Faturamento: {imagem.faturamento or 'Não informado'}"
        )
        elements.append(Paragraph(info_text, body_style))
        elements.append(Spacer(1, 10))

        image_path1 = _find_image_path(str(imagem.imagem)) if imagem.imagem else None
        image_path2 = _find_image_path(str(imagem.imagem2)) if imagem.imagem2 else None

        img1 = Image(image_path1, width=200, height=100) if image_path1 else Paragraph("", body_style)
        img2 = Image(image_path2, width=200, height=100) if image_path2 else Paragraph("", body_style)

        images_table = Table([[img1, img2]], colWidths=[220, 220])
        images_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        elements.append(images_table)
        elements.append(Spacer(1, 10))

        texto_tratativa = TRATATIVAS.get(tipo_problema, "Problemas não especificados.")
        elements.append(Paragraph(f"Tratativa: {texto_tratativa}", body_style))
        elements.append(Spacer(1, 20))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def enviar_relatorio_aprovacao_task(self, registro_id, recipient_list):
    """Gera o PDF de manutenção e envia por email de forma assíncrona."""
    from .models import registrodemanutencao

    registro = registrodemanutencao.objects.get(id=registro_id)
    pdf = _gerar_pdf_manutencao(registro)

    subject = f"Manutenção Aprovada: {registro.id}"
    message = (
        f"A manutenção {registro.id} foi aprovada com sucesso. "
        f"Em anexo está o relatório detalhado da manutenção."
    )

    email = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
    email.attach(f"relatorio-manutencao-{registro.id}.pdf", pdf, "application/pdf")
    email.send()

    logger.info("task=enviar_relatorio_aprovacao_task registro_id=%s destinatarios=%s", registro_id, recipient_list)

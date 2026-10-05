import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from .models import Requisicoes

#receiver(post_save, sender=Requisicoes)
#def enviar_email_requisicao_criada(sender, instance, created, **kwargs):
 #   if created:
  #      subject = f"Reativação solicitada ID :  {instance.id}"
   #     message = f"Reativação Criada com sucesso {instance.id} {instance.nome} "
    #    from_email = 'sysggoldensat@gmail.com'
     #   recipient_list = ['faturamento@grupogoldensat.com.br','comercial@grupogoldensat.com.br','inteligencia@grupogoldensat.com.br',
      #                    'aux_financeiro@grupogoldensat.com.br']
        
       # send_mail(subject, message, from_email, recipient_list)
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from .models import Requisicoes
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas
import os
from requisicao.views import gerar_pdf_requisicao



logger = logging.getLogger(__name__)


@receiver(post_save, sender=Requisicoes)
def enviar_email_requisicao_criada(sender, instance, created, **kwargs):
    # Pula signal se foi marcado (ex: expedição parcial, ou a criação pela tela,
    # que notifica só depois de gravar os itens — ver services.criar_requisicao).
    if getattr(instance, '_skip_signals', False):
        return

    if created:
        notificar_requisicao_criada(instance)


def notificar_requisicao_criada(instance):
    """E-mail de requisição criada, com o PDF do protocolo em anexo.

    Efeito colateral: falha de SMTP/PDF é registrada no log e não derruba a
    tela — a requisição já está gravada quando a notificação roda.
    """
    try:
        _enviar_emails_requisicao_criada(instance)
    except Exception:  # noqa: BLE001 — qualquer falha de e-mail/PDF só é logada
        logger.exception("[notificar_requisicao_criada] falha ao notificar a requisição %s", instance.pk)


def _enviar_emails_requisicao_criada(instance):
    if instance.comercial == "MAYRA":
        subject = f"Requisiçao solicitada ID :  {instance.id}"
        message = f"Requisição {instance.id} {instance.nome} .Realizada com sucesso "
        from_email = 'sysggoldensat@gmail.com'
        recipient_list = ['inteligencia@grupogoldensat.com.br']
        send_mail(subject, message, from_email, recipient_list)

    pdf_path = gerar_pdf_requisicao(instance)
    subject = f"Requisiçao solicitada ID :  {instance.id}"
    message = f"Requisição {instance.id} {instance.nome} .Realizada com sucesso "
    from_email = 'sysggoldensat@gmail.com'
    
    if instance.comercial == "MAYRA":
                   recipient_list = [
            
            'comercial@grupogoldensat.com.br',
            'inteligencia@grupogoldensat.com.br',
            'aux_financeiro@grupogoldensat.com.br',
            'mayra.monteiro@grupogoldensat.com.br',
            'comercial@grupogoldensat.com.br'#--- retirar
        ]
    else:
        recipient_list = [
            'faturamento@grupogoldensat.com.br',
            'comercial@grupogoldensat.com.br',
            'inteligencia@grupogoldensat.com.br',
            'comercial2@grupogoldensat.com.br',
            'aux_financeiro@grupogoldensat.com.br'
        ]
    
    email = EmailMessage(subject, message, from_email, recipient_list)
    email.attach_file(pdf_path)
    
    try:
        email.send()
        print("Email enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")

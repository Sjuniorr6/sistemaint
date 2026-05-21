# signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from ticket.models import ticketmodel

@receiver(post_save, sender=ticketmodel)
def enviar_email_tiket_criada(sender, instance, created, **kwargs):
    if created:
        subject = f"Tiket: {instance.id}"
        message = f"um novo tiket {instance.id} foi criado. {instance.usuario} Status: {instance.status}"
        from_email = 'sysggoldensat@gmail.com'
        recipient_list = ['julio.cesar@grupogoldensat.com.br']
        
        send_mail(subject, message, from_email, recipient_list)

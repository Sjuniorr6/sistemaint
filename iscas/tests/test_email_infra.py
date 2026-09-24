"""O backend de e-mail em teste é o de memória, não o SMTP de produção.

Sem esta garantia, todos os testes de notificação poderiam passar porque o
envio sumiu por outro motivo — e um deles poderia entregar e-mail de verdade.
"""
import pytest
from django.conf import settings
from django.core import mail
from django.core.mail import EmailMessage


def test_backend_e_de_memoria():
    assert "locmem" in settings.EMAIL_BACKEND


def test_envio_cai_no_outbox():
    EmailMessage("assunto", "corpo", "de@x.com", ["para@x.com"]).send()

    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "assunto"


def test_envio_com_bcc_e_sem_to_funciona():
    """O service manda só por bcc — confirmar que o Django entrega assim."""
    EmailMessage("assunto", "corpo", "de@x.com", [], bcc=["oculto@x.com"]).send()

    assert len(mail.outbox) == 1
    assert mail.outbox[0].recipients() == ["oculto@x.com"]

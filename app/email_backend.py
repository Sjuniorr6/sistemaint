import ssl

from django.core.mail.backends.smtp import EmailBackend


class UnverifiedSSLEmailBackend(EmailBackend):
    @property
    def ssl_context(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

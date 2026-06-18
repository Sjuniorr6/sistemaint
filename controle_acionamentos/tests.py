import pytest

from controle_acionamentos.services import validar_cpf
from controle_acionamentos.services import validar_cpf, validar_cnpj
from controle_acionamentos.services import validar_cpf, validar_cnpj, validar_cnh
from controle_acionamentos.models import ResponsavelAgente

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

def test_cpf_valido_retorna_true():
    """Um CPF válido conhecido deve ser aceito."""
    assert validar_cpf('529.982.247-25') is True

def test_cpf_digito_invalido_retorna_false():
    """Um CPF com dígito verificador errado deve ser rejeitado."""
    assert validar_cpf('529.982.247-26') is False


def test_cpf_digitos_repetidos_retorna_false():
    """CPF com todos os dígitos iguais é inválido (RN-01), mesmo passando na conta."""
    assert validar_cpf('111.111.111-11') is False

def test_cpf_tamanho_errado_retorna_false():
    """CPF com número de dígitos diferente de 11 é inválido."""
    assert validar_cpf('123') is False
    assert validar_cpf('') is False

def test_cnpj_valido_retorna_true():
    """Um CNPJ válido conhecido deve ser aceito (§11.2)."""
    assert validar_cnpj('04.252.011/0001-10') is True


def test_cnpj_digito_invalido_retorna_false():
    """Um CNPJ com dígito verificador errado deve ser rejeitado."""
    assert validar_cnpj('04.252.011/0001-11') is False


def test_cnpj_digitos_repetidos_retorna_false():
    """CNPJ com todos os dígitos iguais é inválido (RN-02), mesmo passando na conta."""
    assert validar_cnpj('00.000.000/0000-00') is False


def test_cnpj_tamanho_errado_retorna_false():
    """CNPJ com número de dígitos diferente de 14 é inválido."""
    assert validar_cnpj('123') is False
    assert validar_cnpj('') is False

def test_cnh_valido_retorna_true():
    """Uma CNH válida conhecida deve ser aceita (RN-03)."""
    assert validar_cnh('19960271686') is True


def test_cnh_digito_invalido_retorna_false():
    """Uma CNH com dígito verificador errado deve ser rejeitada."""
    assert validar_cnh('19960271687') is False


def test_cnh_digitos_repetidos_retorna_false():
    """CNH com todos os dígitos iguais é inválida, mesmo passando na conta."""
    assert validar_cnh('11111111111') is False


def test_cnh_tamanho_errado_retorna_false():
    """CNH com número de dígitos diferente de 11 é inválida."""
    assert validar_cnh('123') is False
    assert validar_cnh('') is False


@pytest.mark.django_db
def test_responsavel_agente_persiste_com_nome_valido():
    responsavel = ResponsavelAgente.objects.create(nome="João Supervisor")

    assert responsavel.pk is not None
    assert ResponsavelAgente.objects.count() == 1
    assert ResponsavelAgente.objects.get(pk=responsavel.pk).nome == "João Supervisor"

@pytest.mark.django_db
def test_responsavel_agente_nome_vazio_e_rejeitado():
    with pytest.raises(ValidationError):
        ResponsavelAgente(nome="   ").full_clean()


@pytest.mark.django_db
def test_responsavel_agente_lista_ordenada_por_criacao_desc():
    antigo = ResponsavelAgente.objects.create(nome="Antigo")
    recente = ResponsavelAgente.objects.create(nome="Recente")
    ResponsavelAgente.objects.filter(pk=antigo.pk).update(
        criado_em=timezone.now() - timedelta(hours=1)
    )

    assert list(ResponsavelAgente.objects.all()) == [recente, antigo]
from controle_acionamentos.services import validar_cpf


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
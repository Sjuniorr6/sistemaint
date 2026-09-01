"""O CSV do extrato abre com acento correto no Excel (ISC-RF-37).

O conteudo sempre foi UTF-8 e o `content_type` declarava o charset. O Excel
IGNORA esse cabecalho ao abrir um .csv de disco e assume a codepage ANSI do
Windows — o BOM e o unico sinal que ele le nesse caminho.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import GRUPO_OPERADORES
from iscas.services import entrada as entrada_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


@pytest.fixture
def entrada_com_acento(deposito, modelo_descartavel, operador):
    """Uma movimentacao cuja justificativa tem acento e cedilha."""
    return entrada_service.registrar_entrada(
        modelo=modelo_descartavel,
        identificadores=["CSV001", "CSV002"],
        destino=deposito,
        autor=operador,
        nota_fiscal="NF-Ção",
    )


def _baixar(client):
    resposta = client.get(reverse("iscas:extrato_csv"))
    return b"".join(resposta.streaming_content)


def test_comeca_com_bom_utf8(client, operador_logado, entrada_com_acento):
    """Sem o BOM, o Excel decodifica como ANSI e quebra todo acento."""
    # sabotagem: remover `yield BOM_UTF8` da view → vermelho
    assert _baixar(client).startswith(b"\xef\xbb\xbf")


def test_acentos_sobrevivem_a_leitura_do_excel(
    client, operador_logado, entrada_com_acento, deposito
):
    """O teste que importa: decodificar como o Excel faz e conferir o texto.

    Afirmar `b"Solicita\\xc3\\xa7\\xe3o" in conteudo` provaria so que os bytes
    sao UTF-8 — o que ja era verdade antes da correcao, com o arquivo abrindo
    errado mesmo assim.
    """
    conteudo = _baixar(client)

    # `utf-8-sig` e exatamente o que o Excel faz ao encontrar o BOM: consome a
    # marca e le o resto como UTF-8.
    texto = conteudo.decode("utf-8-sig")

    assert "Solicitação" in texto          # cabeçalho da coluna
    assert "NF-Ção" in texto               # dado gravado pelo operador
    assert str(deposito) in texto
    # O BOM nao pode virar lixo na primeira celula.
    assert texto.splitlines()[0].startswith("ID;")


def test_continua_utf8_valido_para_quem_nao_usa_excel(
    client, operador_logado, entrada_com_acento
):
    """LibreOffice, pandas e `csv` do Python leem os dois formatos; o BOM nao
    pode ter trocado a codificacao do corpo."""
    conteudo = _baixar(client)

    corpo = conteudo[3:]  # sem o BOM
    assert corpo.decode("utf-8")  # nao levanta
    assert "Solicitação".encode("utf-8") in corpo


def test_o_cabecalho_http_continua_declarando_utf8(client, operador_logado):
    """Quem consome por HTTP (fetch, requests) usa o cabecalho, nao o BOM."""
    resposta = client.get(reverse("iscas:extrato_csv"))

    assert "charset=utf-8" in resposta["Content-Type"]
    assert "attachment" in resposta["Content-Disposition"]

"""Código do modelo de isca é opcional, mas continua único quando informado."""
import pytest

from iscas.enums import TipoModelo
from iscas.forms.cadastro import ModeloForm
from iscas.models.cadastro import ModeloEquipamento
from iscas.services import entrada as entrada_service

pytestmark = pytest.mark.django_db


def _dados(nome, codigo=""):
    return {"nome": nome, "codigo": codigo, "tipo": TipoModelo.DESCARTAVEL}


def test_dois_modelos_sem_codigo_convivem():
    """O caso que o `unique` quebraria: "" colide com "", NULL não colide com NULL."""
    primeiro = ModeloForm(data=_dados("Isca Sem Código A"))
    assert primeiro.is_valid(), primeiro.errors
    primeiro.save()

    segundo = ModeloForm(data=_dados("Isca Sem Código B"))
    assert segundo.is_valid(), segundo.errors
    segundo.save()

    # Gravado como NULL, nunca "" — é o que mantém o UNIQUE compatível com
    # o campo opcional.
    assert ModeloEquipamento.objects.filter(codigo__isnull=True).count() == 2


@pytest.mark.parametrize("codigo_enviado", ["", "   "])
def test_codigo_em_branco_vira_none(codigo_enviado):
    form = ModeloForm(data=_dados("Isca Branca", codigo_enviado))
    assert form.is_valid(), form.errors

    assert form.cleaned_data["codigo"] is None
    assert form.save().codigo is None


def test_codigo_informado_continua_unico(modelo_descartavel):
    """Opcional não é o mesmo que sem regra: código repetido segue recusado."""
    form = ModeloForm(data=_dados("Outra Isca", modelo_descartavel.codigo))

    assert not form.is_valid()
    assert "codigo" in form.errors


def test_str_e_rotulo_nao_mostram_parenteses_vazio():
    modelo = ModeloEquipamento.objects.create(
        nome="Isca Sem Código", tipo=TipoModelo.DESCARTAVEL
    )

    assert str(modelo) == "Isca Sem Código"
    # As telas compactas (badge de saldo, item do pedido) mostram o nome no
    # lugar do código: badge vazio não diz de qual modelo é o saldo.
    assert modelo.codigo_ou_nome == "Isca Sem Código"


def test_identificadores_de_modelos_sem_codigo_nao_colidem_entre_si():
    """Interpolar código vazio daria `GS--000001` igual para TODO modelo sem código."""
    primeiro = ModeloEquipamento.objects.create(
        nome="Isca Sem Código A", tipo=TipoModelo.DESCARTAVEL
    )
    segundo = ModeloEquipamento.objects.create(
        nome="Isca Sem Código B", tipo=TipoModelo.DESCARTAVEL
    )

    de_um = entrada_service.gerar_identificadores_internos(modelo=primeiro, quantidade=2)
    de_outro = entrada_service.gerar_identificadores_internos(modelo=segundo, quantidade=2)

    assert not set(de_um) & set(de_outro)
    assert de_um[0] == f"GS-M{primeiro.pk}-000001"

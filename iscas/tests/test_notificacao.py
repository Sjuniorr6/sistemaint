"""E-mail quando a cobertura da solicitação fecha.

O gatilho é a VINCULAÇÃO do último equipamento, não a entrega: no exemplo do
usuário, 7 + 3 de um pedido de 10 → o e-mail sai ao vincular o segundo agente.
"""
from decimal import Decimal

import pytest
from django.core import mail

from iscas.models.config import DestinatarioNotificacao
from iscas.services import notificacao
from iscas.services import solicitacao as service

pytestmark = pytest.mark.django_db


@pytest.fixture
def destinatario(db):
    return DestinatarioNotificacao.objects.create(
        email="operacao@golden.com", nome="Operação"
    )


@pytest.fixture
def pedido(cliente, operador, modelo_descartavel):
    def _criar(quantidade=2, preco="450.00"):
        return service.abrir_solicitacao(
            cliente=cliente, autor=operador,
            itens=[(modelo_descartavel, quantidade, Decimal(preco))],
            solicitante_nome="Elson Vilas Boas",
        )

    return _criar


class TestDisparo:
    # sabotagem: mover o gancho para confirmar_entrega → vermelho
    def test_vinculacao_completa_envia(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente,
        destinatario, django_capture_on_commit_callbacks,
    ):
        solicitacao = pedido(quantidade=2)

        with django_capture_on_commit_callbacks(execute=True):
            service.criar_atribuicao(
                solicitacao=solicitacao, agente=agente,
                itens=[(modelo_descartavel, 2)], autor=operador,
            )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].recipients() == ["operacao@golden.com"]
        assert f"#{solicitacao.pk}" in mail.outbox[0].subject

    def test_vinculacao_parcial_nao_envia(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente,
        destinatario, django_capture_on_commit_callbacks,
    ):
        """As duas asserções juntas: sem a segunda o teste passa vacuamente."""
        solicitacao = pedido(quantidade=5)

        with django_capture_on_commit_callbacks(execute=True):
            service.criar_atribuicao(
                solicitacao=solicitacao, agente=agente,
                itens=[(modelo_descartavel, 3)], autor=operador,
            )

        assert service.cobertura_total(solicitacao) is False
        assert mail.outbox == []

    def test_dois_agentes_fecham_e_envia_uma_vez(
        self, pedido, operador, agente, agente2, modelo_descartavel,
        unidades_com_agente, destinatario, django_capture_on_commit_callbacks,
    ):
        """O caso do usuário, na escala da fixture: 5 + 3 de um pedido de 8."""
        from iscas.services import transferencia as transferencia_service

        solicitacao = pedido(quantidade=8)
        transferencia_service.transferir(
            origem=agente, destino=agente2, modelo=modelo_descartavel,
            quantidade=3, autor=operador,
        )

        with django_capture_on_commit_callbacks(execute=True):
            service.criar_atribuicao(
                solicitacao=solicitacao, agente=agente,
                itens=[(modelo_descartavel, 5)], autor=operador,
            )
        assert mail.outbox == [], "não fecha com 5 de 8"

        with django_capture_on_commit_callbacks(execute=True):
            service.criar_atribuicao(
                solicitacao=solicitacao, agente=agente2,
                itens=[(modelo_descartavel, 3)], autor=operador,
            )

        assert len(mail.outbox) == 1

    def test_destinatario_desativado_nao_recebe(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente,
        destinatario, django_capture_on_commit_callbacks,
    ):
        destinatario.desativar()
        solicitacao = pedido(quantidade=2)

        with django_capture_on_commit_callbacks(execute=True):
            service.criar_atribuicao(
                solicitacao=solicitacao, agente=agente,
                itens=[(modelo_descartavel, 2)], autor=operador,
            )

        assert mail.outbox == []

    def test_sem_destinatario_nao_levanta(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente,
        django_capture_on_commit_callbacks,
    ):
        solicitacao = pedido(quantidade=2)

        with django_capture_on_commit_callbacks(execute=True):
            service.criar_atribuicao(
                solicitacao=solicitacao, agente=agente,
                itens=[(modelo_descartavel, 2)], autor=operador,
            )

        assert solicitacao.atribuicoes.count() == 1


class TestBlindagem:
    # sabotagem: remover o try/except de notificar_cobertura_fechada → vermelho
    def test_smtp_quebrado_nao_derruba_a_vinculacao(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente,
        destinatario, monkeypatch, django_capture_on_commit_callbacks,
    ):
        """O mais importante: a reserva já aconteceu quando o e-mail sai."""
        def explodir(*args, **kwargs):
            raise OSError("smtp fora do ar")

        monkeypatch.setattr("django.core.mail.EmailMessage.send", explodir)
        solicitacao = pedido(quantidade=2)

        with django_capture_on_commit_callbacks(execute=True):
            atribuicao = service.criar_atribuicao(
                solicitacao=solicitacao, agente=agente,
                itens=[(modelo_descartavel, 2)], autor=operador,
            )

        assert atribuicao.pk
        assert atribuicao.reservas_ativas().count() == 2

    def test_service_devolve_false_em_falha(self, pedido, destinatario, monkeypatch):
        def explodir(*args, **kwargs):
            raise OSError("smtp fora do ar")

        monkeypatch.setattr("django.core.mail.EmailMessage.send", explodir)

        assert notificacao.notificar_cobertura_fechada(pedido().pk) is False


class TestTexto:
    def test_traz_os_campos_do_modelo(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        solicitacao = pedido(quantidade=2, preco="450.00")
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("50.00"),
        )
        texto = notificacao.montar_texto_entrega(solicitacao)

        assert "Entrega" in texto
        assert "Solicitante: Elson Vilas Boas" in texto
        assert f"Cliente: {solicitacao.cliente.nome_razao_social}" in texto
        assert "Comercial da conta (se possuir):" in texto
        assert "Quantidade: 02" in texto
        assert "Valor isca: 450,00" in texto
        assert "Valor total: 900,00" in texto
        assert f"Modelo: {modelo_descartavel}" in texto
        assert f"Agente: {agente.nome}" in texto
        assert "Valor frete/agente: 50,00" in texto
        assert f"Contato: {agente.telefone}" in texto

    def test_marca_descartavel_e_nao_retornavel(self, pedido):
        texto = notificacao.montar_texto_entrega(pedido())

        assert "Descartável: (x) SIM" in texto
        assert "Retornável: () NÃO" in texto

    def test_omite_valor_isca_sem_unitario(
        self, cliente, operador, modelo_descartavel
    ):
        """Solicitações anteriores ao preço por item."""
        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador,
            valor_cliente=Decimal("900.00"),
        )
        texto = notificacao.montar_texto_entrega(solicitacao)

        assert "Valor isca" not in texto
        assert "Valor total: 900,00" in texto

    def test_omite_obs_quando_vazia(self, pedido):
        assert "obs:" not in notificacao.montar_texto_entrega(pedido())

    # sabotagem: usar atribuicao.agente.telefone sem o guard → vermelho
    def test_retirada_na_base_sem_contato(
        self, pedido, operador, deposito, modelo_descartavel, unidades_no_deposito
    ):
        """Depósito não tem telefone — seria AttributeError em produção."""
        solicitacao = pedido(quantidade=2)
        service.criar_atribuicao(
            solicitacao=solicitacao, deposito=deposito,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        texto = notificacao.montar_texto_entrega(solicitacao)

        assert f"Agente: {deposito.nome}" in texto
        assert "Contato:" not in texto

    def test_dois_agentes_dois_blocos(
        self, pedido, operador, agente, agente2, modelo_descartavel,
        unidades_com_agente,
    ):
        from iscas.services import transferencia as transferencia_service

        solicitacao = pedido(quantidade=8)
        transferencia_service.transferir(
            origem=agente, destino=agente2, modelo=modelo_descartavel,
            quantidade=3, autor=operador,
        )
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente2,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        texto = notificacao.montar_texto_entrega(solicitacao)

        assert texto.count("Agente: ") == 2

    def test_lista_os_identificadores(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        solicitacao = pedido(quantidade=2)
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        texto = notificacao.montar_texto_entrega(solicitacao)

        linha = [l for l in texto.split("\n") if l.startswith("ID: ")][0]
        assert " / " in linha

    @pytest.mark.parametrize("valor,esperado", [
        ("450.00", "450,00"),
        ("1234.50", "1.234,50"),
        ("1000000.00", "1.000.000,00"),
        ("0.50", "0,50"),
    ])
    def test_formato_de_moeda_brasileiro(self, valor, esperado):
        assert notificacao._moeda(Decimal(valor)) == esperado


class TestTotalComEntrega:
    """O e-mail mostra o que o cliente paga de fato: material + entrega."""

    # sabotagem: remover a linha do receita_total → vermelho
    def test_soma_material_e_entrega(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        solicitacao = pedido(quantidade=2, preco="350.00")
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_entrega_cliente=Decimal("100.00"),
        )
        texto = notificacao.montar_texto_entrega(solicitacao)

        assert "Valor total: 700,00" in texto
        assert "Valor da entrega: 100,00" in texto
        assert "Valor total com entrega: 800,00" in texto

    def test_soma_entrega_de_dois_agentes(
        self, pedido, operador, agente, agente2, modelo_descartavel,
        unidades_com_agente,
    ):
        from iscas.services import transferencia as transferencia_service

        solicitacao = pedido(quantidade=8, preco="100.00")
        transferencia_service.transferir(
            origem=agente, destino=agente2, modelo=modelo_descartavel,
            quantidade=3, autor=operador,
        )
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
            valor_entrega_cliente=Decimal("60.00"),
        )
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente2,
            itens=[(modelo_descartavel, 3)], autor=operador,
            valor_entrega_cliente=Decimal("40.00"),
        )
        texto = notificacao.montar_texto_entrega(solicitacao)

        assert "Valor total: 800,00" in texto
        assert "Valor da entrega: 100,00" in texto
        assert "Valor total com entrega: 900,00" in texto

    def test_sem_frete_nao_repete_a_linha(
        self, pedido, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        """Sem entrega cobrada, o total com entrega seria igual ao total."""
        solicitacao = pedido(quantidade=2, preco="350.00")
        service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        texto = notificacao.montar_texto_entrega(solicitacao)

        assert "Valor total: 700,00" in texto
        assert "Valor da entrega" not in texto
        assert "Valor total com entrega" not in texto

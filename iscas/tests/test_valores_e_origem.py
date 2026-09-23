"""Invariantes de dinheiro e de origem da atribuição, no banco.

As constraints vivem no banco e não só no form porque os services escrevem com
`objects.create()`, que NÃO roda `full_clean()` — validator sozinho aqui seria
decoração. Por isso todo teste abaixo chama `objects.create` direto: é o
caminho real da escrita.
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from iscas.enums import OrigemAtribuicao, StatusAtribuicao, StatusSolicitacao
from iscas.models.operacao import Atribuicao, Solicitacao

pytestmark = pytest.mark.django_db


def _solicitacao(cliente, operador, **extra):
    from django.utils import timezone

    dados = {
        "cliente": cliente,
        "aberta_em": timezone.now(),
        "aberta_por": operador,
        "status": StatusSolicitacao.ABERTA,
    }
    dados.update(extra)
    return Solicitacao.objects.create(**dados)


def _atribuicao(solicitacao, operador, **extra):
    dados = {
        "solicitacao": solicitacao,
        "criada_por": operador,
        "status": StatusAtribuicao.RESERVADA,
    }
    dados.update(extra)
    return Atribuicao.objects.create(**dados)


class TestOrigemXor:
    """Uma atribuição sai de um agente OU de um depósito — nunca dos dois."""

    # sabotagem: remover iscas_atrib_origem_xor → vermelho
    def test_recusa_agente_e_deposito_juntos(
        self, cliente, operador, agente, deposito
    ):
        solicitacao = _solicitacao(cliente, operador)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _atribuicao(
                    solicitacao, operador,
                    origem_tipo=OrigemAtribuicao.AGENTE,
                    agente=agente, deposito=deposito,
                )

    def test_recusa_sem_agente_e_sem_deposito(self, cliente, operador):
        solicitacao = _solicitacao(cliente, operador)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _atribuicao(
                    solicitacao, operador,
                    origem_tipo=OrigemAtribuicao.AGENTE,
                    agente=None, deposito=None,
                )

    def test_recusa_tipo_agente_com_deposito_preenchido(
        self, cliente, operador, deposito
    ):
        """O tipo tem de concordar com o campo — senão o rótulo mente."""
        solicitacao = _solicitacao(cliente, operador)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _atribuicao(
                    solicitacao, operador,
                    origem_tipo=OrigemAtribuicao.AGENTE,
                    agente=None, deposito=deposito,
                )

    def test_recusa_tipo_retirada_com_agente_preenchido(
        self, cliente, operador, agente
    ):
        solicitacao = _solicitacao(cliente, operador)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _atribuicao(
                    solicitacao, operador,
                    origem_tipo=OrigemAtribuicao.RETIRADA_BASE,
                    agente=agente, deposito=None,
                )

    def test_aceita_agente(self, cliente, operador, agente):
        solicitacao = _solicitacao(cliente, operador)
        atribuicao = _atribuicao(
            solicitacao, operador,
            origem_tipo=OrigemAtribuicao.AGENTE, agente=agente,
        )
        assert atribuicao.pk

    def test_aceita_retirada_na_base(self, cliente, operador, deposito):
        solicitacao = _solicitacao(cliente, operador)
        atribuicao = _atribuicao(
            solicitacao, operador,
            origem_tipo=OrigemAtribuicao.RETIRADA_BASE, deposito=deposito,
        )
        assert atribuicao.pk


class TestValoresNaoNegativos:
    # sabotagem: remover iscas_sol_valor_cliente_nao_negativo → vermelho
    def test_recusa_valor_cliente_negativo(self, cliente, operador):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _solicitacao(cliente, operador, valor_cliente=Decimal("-1.00"))

    def test_recusa_valor_agente_negativo(self, cliente, operador, agente):
        solicitacao = _solicitacao(cliente, operador)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _atribuicao(
                    solicitacao, operador,
                    origem_tipo=OrigemAtribuicao.AGENTE, agente=agente,
                    valor_agente=Decimal("-0.01"),
                )

    def test_aceita_nulo(self, cliente, operador, agente):
        """O caso que prova que a migration roda sobre o histórico.

        Solicitações abertas antes deste campo existir têm valor NULL. Se a
        constraint recusasse NULL, a migration falharia em produção — e só lá.
        """
        solicitacao = _solicitacao(cliente, operador, valor_cliente=None)
        atribuicao = _atribuicao(
            solicitacao, operador,
            origem_tipo=OrigemAtribuicao.AGENTE, agente=agente, valor_agente=None,
        )

        assert solicitacao.valor_cliente is None
        assert atribuicao.valor_agente is None

    def test_aceita_zero(self, cliente, operador):
        """Zero é valor de negócio legítimo (cortesia), diferente de ausência."""
        solicitacao = _solicitacao(cliente, operador, valor_cliente=Decimal("0.00"))
        assert solicitacao.valor_cliente == Decimal("0.00")

    @pytest.mark.parametrize("valor", ["0.01", "1234.56", "99999999.99"])
    def test_aceita_valores_validos(self, cliente, operador, valor):
        solicitacao = _solicitacao(cliente, operador, valor_cliente=Decimal(valor))
        solicitacao.refresh_from_db()
        assert solicitacao.valor_cliente == Decimal(valor)


class TestRetiradaNaoTemCustoDeAgente:
    """Requisito do usuário vira invariante de banco, não convenção de tela."""

    # sabotagem: remover iscas_atrib_retirada_sem_valor → vermelho
    def test_recusa_valor_agente_em_retirada(self, cliente, operador, deposito):
        solicitacao = _solicitacao(cliente, operador)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _atribuicao(
                    solicitacao, operador,
                    origem_tipo=OrigemAtribuicao.RETIRADA_BASE,
                    deposito=deposito, valor_agente=Decimal("50.00"),
                )

    def test_aceita_retirada_sem_valor(self, cliente, operador, deposito):
        atribuicao = _atribuicao(
            _solicitacao(cliente, operador), operador,
            origem_tipo=OrigemAtribuicao.RETIRADA_BASE, deposito=deposito,
        )
        assert atribuicao.valor_agente is None


class TestOrigemPolimorfica:
    """As properties que os 7 pontos de acoplamento vão passar a usar."""

    def test_origem_devolve_o_agente(self, cliente, operador, agente):
        atribuicao = _atribuicao(
            _solicitacao(cliente, operador), operador,
            origem_tipo=OrigemAtribuicao.AGENTE, agente=agente,
        )

        assert atribuicao.origem == agente
        assert atribuicao.origem_nome == agente.nome
        assert atribuicao.eh_retirada_base is False

    def test_origem_devolve_o_deposito(self, cliente, operador, deposito):
        atribuicao = _atribuicao(
            _solicitacao(cliente, operador), operador,
            origem_tipo=OrigemAtribuicao.RETIRADA_BASE, deposito=deposito,
        )

        assert atribuicao.origem == deposito
        assert atribuicao.origem_nome == deposito.nome
        assert atribuicao.eh_retirada_base is True

    @pytest.mark.parametrize("tipo,campo", [
        (OrigemAtribuicao.AGENTE, "agente"),
        (OrigemAtribuicao.RETIRADA_BASE, "deposito"),
    ])
    def test_str_nao_levanta_em_nenhum_dos_dois(
        self, cliente, operador, agente, deposito, tipo, campo
    ):
        """`__str__` usava self.agente — com agente None seria AttributeError."""
        entidade = agente if campo == "agente" else deposito
        atribuicao = _atribuicao(
            _solicitacao(cliente, operador), operador,
            origem_tipo=tipo, **{campo: entidade},
        )

        assert entidade.nome in str(atribuicao)


class TestServiceAbrirSolicitacao:
    """Os campos novos precisam ser parâmetros NOMEADOS no service."""

    # sabotagem: passar valor_cliente via **dados_entrega → vermelho
    def test_valor_e_solicitante_persistem(
        self, cliente, operador, modelo_descartavel
    ):
        """Trava o descarte silencioso de `dados_de_entrega`.

        Aquela função itera só `_CAMPOS_DO_CLIENTE` e engole kwargs extras sem
        erro: um campo novo passado por ali nasceria NULL e ninguém saberia.
        """
        from iscas.services import solicitacao as service

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador,
            valor_cliente=Decimal("250.00"), solicitante_nome="Maria Compras",
        )
        solicitacao.refresh_from_db()

        assert solicitacao.valor_cliente == Decimal("250.00")
        assert solicitacao.solicitante_nome == "Maria Compras"

    def test_sem_valor_continua_funcionando(
        self, cliente, operador, modelo_descartavel
    ):
        """Os ~100 testes antigos não passam valor — precisam seguir válidos."""
        from iscas.services import solicitacao as service

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador,
        )

        assert solicitacao.valor_cliente is None

    def test_exigir_valor_recusa_sem_valor(
        self, cliente, operador, modelo_descartavel
    ):
        from iscas.services.exceptions import MovimentacaoInvalida
        from iscas.services import solicitacao as service

        with pytest.raises(MovimentacaoInvalida):
            service.abrir_solicitacao(
                cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador,
                exigir_valor=True,
            )

    def test_solicitante_nao_vem_do_cadastro_do_cliente(
        self, cliente, operador, modelo_descartavel
    ):
        """Prova que NÃO entrou em _CAMPOS_DO_CLIENTE.

        `contato_nome` é preenchido do cadastro quando vem vazio; o solicitante
        não pode ser — senão o dado que o usuário pediu some sob o contato.
        """
        from iscas.services import solicitacao as service

        cliente.contato_nome = "Recepção do Cliente"
        cliente.save(update_fields=["contato_nome"])

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador,
        )

        assert solicitacao.contato_nome == "Recepção do Cliente"
        assert solicitacao.solicitante_nome == ""


class TestServiceCriarAtribuicao:
    def test_retirada_na_base_reserva_do_deposito_e_conta_na_cobertura(
        self, cliente, operador, deposito, modelo_descartavel, unidades_no_deposito
    ):
        """Valida a decisão arquitetural inteira.

        Se a retirada não contasse na cobertura, a solicitação ficaria
        eternamente ABERTA com estoque preso — era o risco do desenho.
        """
        from iscas.services import solicitacao as service

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador,
        )
        atribuicao = service.criar_atribuicao(
            solicitacao=solicitacao, deposito=deposito,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )

        assert atribuicao.eh_retirada_base
        assert atribuicao.origem == deposito
        assert atribuicao.reservas_ativas().count() == 3
        assert service.cobertura_total(solicitacao) is True

    def test_valor_do_agente_persiste(
        self, cliente, operador, agente, modelo_descartavel, unidades_com_agente
    ):
        from iscas.services import solicitacao as service

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador,
        )
        atribuicao = service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("75.50"),
        )
        atribuicao.refresh_from_db()

        assert atribuicao.valor_agente == Decimal("75.50")

    @pytest.mark.parametrize("kwargs,motivo", [
        ({"agente": "AGENTE", "deposito": "DEPOSITO"}, "os dois"),
        ({}, "nenhum"),
    ])
    def test_xor_recusa(
        self, cliente, operador, agente, deposito, modelo_descartavel,
        kwargs, motivo,
    ):
        from iscas.services.exceptions import MovimentacaoInvalida
        from iscas.services import solicitacao as service

        resolvido = {
            k: (agente if v == "AGENTE" else deposito) for k, v in kwargs.items()
        }
        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador,
        )

        with pytest.raises(MovimentacaoInvalida):
            service.criar_atribuicao(
                solicitacao=solicitacao, itens=[(modelo_descartavel, 1)],
                autor=operador, **resolvido,
            )

    def test_recusa_valor_de_agente_em_retirada(
        self, cliente, operador, deposito, modelo_descartavel, unidades_no_deposito
    ):
        from iscas.services.exceptions import MovimentacaoInvalida
        from iscas.services import solicitacao as service

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador,
        )

        with pytest.raises(MovimentacaoInvalida):
            service.criar_atribuicao(
                solicitacao=solicitacao, deposito=deposito,
                itens=[(modelo_descartavel, 1)], autor=operador,
                valor_agente=Decimal("50.00"),
            )

    def test_recusa_deposito_desativado(
        self, cliente, operador, deposito, modelo_descartavel
    ):
        """Prova que a checagem de is_active virou polimórfica (ISC-RN-18)."""
        from iscas.services.exceptions import MovimentacaoInvalida
        from iscas.services import solicitacao as service

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador,
        )
        deposito.desativar()

        with pytest.raises(MovimentacaoInvalida):
            service.criar_atribuicao(
                solicitacao=solicitacao, deposito=deposito,
                itens=[(modelo_descartavel, 1)], autor=operador,
            )


class TestEntregaNaRetiradaBase:
    """A entrega sai do depósito quando o cliente retira na base."""

    def _retirada(self, cliente, operador, deposito, modelo, quantidade):
        from iscas.services import solicitacao as service

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo, quantidade)], autor=operador,
        )
        atribuicao = service.criar_atribuicao(
            solicitacao=solicitacao, deposito=deposito,
            itens=[(modelo, quantidade)], autor=operador,
        )
        return solicitacao, atribuicao

    # sabotagem: origem=atribuicao.agente em confirmar_entrega → vermelho
    def test_lancamento_sai_do_deposito(
        self, cliente, operador, deposito, modelo_descartavel, unidades_no_deposito
    ):
        """Afere a ORIGEM do lançamento, não só o efeito final.

        Contar unidades no cliente no fim passaria mesmo com a origem errada;
        é o de onde saiu que prova o desenho polimórfico.
        """
        from iscas.services import custodia as custodia_service
        from iscas.services import solicitacao as service

        _, atribuicao = self._retirada(
            cliente, operador, deposito, modelo_descartavel, 2
        )
        movimentacao = service.confirmar_entrega(
            atribuicao=atribuicao, autor=operador, recebido_por="Cliente"
        )

        assert movimentacao.origem == custodia_service.custodia_de(deposito)
        assert movimentacao.destino == custodia_service.custodia_de(cliente)

    def test_solicitacao_fecha_como_entregue(
        self, cliente, operador, deposito, modelo_descartavel, unidades_no_deposito
    ):
        """Fecha o loop: a cobertura conta a retirada e o status avança."""
        from iscas.services import solicitacao as service

        solicitacao, atribuicao = self._retirada(
            cliente, operador, deposito, modelo_descartavel, 2
        )
        service.confirmar_entrega(atribuicao=atribuicao, autor=operador)
        solicitacao.refresh_from_db()

        assert solicitacao.status == StatusSolicitacao.ENTREGUE

    def test_solicitacao_mista_agente_e_retirada(
        self, cliente, operador, deposito, agente, modelo_descartavel,
        unidades_no_deposito, unidades_com_agente,
    ):
        """Decisão do usuário: uma solicitação pode misturar as duas formas."""
        from iscas.services import solicitacao as service

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 4)], autor=operador,
        )
        por_agente = service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 2)], autor=operador,
            valor_agente=Decimal("30.00"),
        )
        por_base = service.criar_atribuicao(
            solicitacao=solicitacao, deposito=deposito,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        service.confirmar_entrega(atribuicao=por_agente, autor=operador)
        service.confirmar_entrega(atribuicao=por_base, autor=operador)
        solicitacao.refresh_from_db()

        assert solicitacao.status == StatusSolicitacao.ENTREGUE
        assert solicitacao.atribuicoes.count() == 2

    def test_cancelar_retirada_libera_as_reservas(
        self, cliente, operador, deposito, modelo_descartavel, unidades_no_deposito
    ):
        from iscas.services import solicitacao as service

        _, atribuicao = self._retirada(
            cliente, operador, deposito, modelo_descartavel, 2
        )
        service.cancelar_atribuicao(
            atribuicao=atribuicao, motivo="cliente desistiu", autor=operador
        )

        assert atribuicao.reservas_ativas().count() == 0


class TestAcoplamentosComAgenteNulo:
    """Os pontos que liam `.agente.nome` e quebrariam com agente None.

    São AttributeError/NoReverseMatch — erro 500 na cara do operador, não
    falha silenciosa. Cada teste aqui cobre um ponto que foi convertido.
    """

    @pytest.fixture
    def retirada(self, cliente, operador, deposito, modelo_descartavel,
                 unidades_no_deposito):
        from iscas.services import solicitacao as service

        solicitacao = service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 2)], autor=operador,
        )
        atribuicao = service.criar_atribuicao(
            solicitacao=solicitacao, deposito=deposito,
            itens=[(modelo_descartavel, 2)], autor=operador,
        )
        return solicitacao, atribuicao

    # sabotagem: voltar a.agente.nome em excluir_solicitacao → vermelho
    def test_excluir_solicitacao_nomeia_o_deposito(self, retirada, operador):
        """O crash mais provável: set comprehension sobre `a.agente.nome`."""
        from iscas.services import solicitacao as service
        from iscas.services.exceptions import MovimentacaoInvalida

        solicitacao, _ = retirada

        with pytest.raises(MovimentacaoInvalida) as erro:
            service.excluir_solicitacao(solicitacao=solicitacao, autor=operador)

        assert "Depósito" in str(erro.value) or "deposito" in str(erro.value).lower()

    def test_link_whatsapp_vazio_na_retirada(self, retirada):
        """Não há a quem mandar: o cliente vem buscar."""
        from iscas.services.mensagem import link_whatsapp

        _, atribuicao = retirada

        assert link_whatsapp(atribuicao) == ""

    def test_texto_da_atribuicao_nao_levanta(self, retirada, deposito):
        from iscas.services.mensagem import montar_texto_atribuicao

        _, atribuicao = retirada
        texto = montar_texto_atribuicao(atribuicao)

        assert deposito.nome in texto
        assert "Retirada na base" in texto

    def test_geojson_de_solicitacoes_nao_levanta(self, retirada, operador):
        from iscas import selectors

        dados = selectors.solicitacoes_geojson()

        assert dados["type"] == "FeatureCollection"

    def test_detalhe_renderiza_com_retirada(self, client, operador_logado, retirada):
        from django.urls import reverse

        solicitacao, _ = retirada
        resposta = client.get(
            reverse("iscas:solicitacao_detalhe", args=[solicitacao.pk])
        )

        assert resposta.status_code == 200

    def test_unidade_detalhe_renderiza_com_retirada(
        self, client, operador_logado, retirada
    ):
        from django.urls import reverse

        _, atribuicao = retirada
        unidade = atribuicao.unidades_reservadas().first()
        resposta = client.get(
            reverse("iscas:unidade_detalhe", args=[unidade.identificador])
        )

        assert resposta.status_code == 200

    def test_painel_renderiza_com_retirada_em_rota(
        self, client, operador_logado, retirada, operador
    ):
        from django.urls import reverse

        from iscas.services import solicitacao as service

        _, atribuicao = retirada
        service.marcar_em_rota(atribuicao=atribuicao, autor=operador)

        assert client.get(reverse("iscas:painel")).status_code == 200

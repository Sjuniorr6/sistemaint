"""Testes das regras de negócio restantes: estorno, retornáveis, baixa, LGPD.

Cobre os "Testes Críticos Específicos" do ARCHITECTURE que não couberam em
test_custodia/test_reserva/test_geo/test_solicitacao.
"""
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from iscas.enums import (
    MotivoBaixa,
    SituacaoUnidade,
    TipoCustodia,
    TipoModelo,
    TipoMovimentacao,
)
from iscas.models.custodia import Movimentacao, Unidade
from iscas.services import baixa as baixa_service
from iscas.services import cadastro as cadastro_service
from iscas.services import custodia as custodia_service
from iscas.services import entrada as entrada_service
from iscas.services import estorno as estorno_service
from iscas.services import retorno as retorno_service
from iscas.services import saldo as saldo_service
from iscas.services import solicitacao as solicitacao_service
from iscas.services import transferencia as transferencia_service
from iscas.services.exceptions import (
    AgenteComSaldo,
    EstornoInvalido,
    MovimentacaoInvalida,
    TipoModeloImutavel,
    UnidadeIndisponivel,
    UnidadeTerminal,
)

pytestmark = pytest.mark.django_db


class TestEstorno:
    """ISC-ADR-16: o erro é informação; original intacto, correção visível."""

    def test_original_permanece_inalterado(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        """O original continua campo a campo como foi gravado."""
        def _campos(pk):
            # `__dict__` traria `_state`, objeto interno que nunca é igual
            # entre duas instâncias — comparamos os campos persistidos.
            movimentacao = Movimentacao.objects.get(pk=pk)
            return {
                campo.attname: getattr(movimentacao, campo.attname)
                for campo in Movimentacao._meta.concrete_fields
            }

        original = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito, destino=agente,
            unidades=unidades_no_deposito[:3], autor=operador,
        )
        antes = _campos(original.pk)
        linhas_antes = set(
            original.linhas.values_list("unidade_id", flat=True)
        )

        estorno_service.estornar(
            movimentacao=original, autor=operador, justificativa="Lançado por engano"
        )

        assert _campos(original.pk) == antes
        assert set(original.linhas.values_list("unidade_id", flat=True)) == linhas_antes

    def test_saldo_volta_ao_estado_anterior(
        self, unidades_no_deposito, deposito, agente, modelo_descartavel, operador
    ):
        antes = saldo_service.saldo_em_custodia(deposito, modelo=modelo_descartavel)
        original = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito, destino=agente,
            unidades=unidades_no_deposito[:3], autor=operador,
        )
        assert saldo_service.saldo_em_custodia(deposito, modelo=modelo_descartavel) == antes - 3

        estorno_service.estornar(
            movimentacao=original, autor=operador, justificativa="Engano"
        )
        assert saldo_service.saldo_em_custodia(deposito, modelo=modelo_descartavel) == antes

    def test_unidade_volta_a_custodia_anterior(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        original = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito, destino=agente,
            unidades=unidades_no_deposito[:2], autor=operador,
        )
        estorno_service.estornar(
            movimentacao=original, autor=operador, justificativa="Engano"
        )
        conta_deposito = custodia_service.custodia_de(deposito)
        for unidade in Unidade.objects.filter(
            pk__in=[u.pk for u in unidades_no_deposito[:2]]
        ):
            assert unidade.custodia_atual_id == conta_deposito.pk

    def test_estorno_referencia_o_original(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        original = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito, destino=agente,
            unidades=unidades_no_deposito[:1], autor=operador,
        )
        estorno = estorno_service.estornar(
            movimentacao=original, autor=operador, justificativa="Engano"
        )
        assert estorno.tipo == TipoMovimentacao.ESTORNO
        assert estorno.estorno_de_id == original.pk
        assert original.foi_estornada

    def test_estorno_de_baixa_tira_unidade_do_estado_terminal(
        self, unidades_no_deposito, deposito, modelo_descartavel, operador
    ):
        """O único caminho legítimo para sair de um estado terminal."""
        movimentacao = baixa_service.dar_baixa(
            origem=deposito, motivo=MotivoBaixa.PERDA,
            justificativa="Achei que tinha sumido",
            autor=operador, modelo=modelo_descartavel, quantidade=2,
        )
        unidade = Unidade.objects.com_situacao().get(
            pk=movimentacao.linhas.first().unidade_id
        )
        assert unidade.situacao == SituacaoUnidade.BAIXADA

        estorno_service.estornar(
            movimentacao=movimentacao, autor=operador,
            justificativa="As iscas apareceram",
        )
        unidade = Unidade.objects.com_situacao().get(pk=unidade.pk)
        assert unidade.situacao == SituacaoUnidade.EM_DEPOSITO

    def test_nao_estorna_duas_vezes(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        original = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito, destino=agente,
            unidades=unidades_no_deposito[:1], autor=operador,
        )
        estorno_service.estornar(
            movimentacao=original, autor=operador, justificativa="Engano"
        )
        with pytest.raises(EstornoInvalido, match="já foi estornada"):
            estorno_service.estornar(
                movimentacao=original, autor=operador, justificativa="De novo"
            )

    def test_nao_estorna_unidade_ja_movimentada_depois(
        self, unidades_no_deposito, deposito, agente, agente2, operador
    ):
        """Estornar fora de ordem inventaria uma posse que não existe."""
        original = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito, destino=agente,
            unidades=unidades_no_deposito[:2], autor=operador,
        )
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=agente, destino=agente2,
            unidades=unidades_no_deposito[:2], autor=operador,
        )
        with pytest.raises(EstornoInvalido, match="já foram movimentadas"):
            estorno_service.estornar(
                movimentacao=original, autor=operador, justificativa="Engano"
            )

    def test_estorno_exige_justificativa(
        self, unidades_no_deposito, deposito, agente, operador
    ):
        original = custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            origem=deposito, destino=agente,
            unidades=unidades_no_deposito[:1], autor=operador,
        )
        with pytest.raises(EstornoInvalido, match="justificativa"):
            estorno_service.estornar(
                movimentacao=original, autor=operador, justificativa="   "
            )


class TestRetornaveis:
    """ISC-RN-06 e ISC-RN-05: retornável volta, descartável não."""

    @pytest.fixture
    def retornaveis_com_cliente(
        self, retornaveis_com_agente, agente, cliente, operador
    ):
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.ENTREGA,
            origem=agente, destino=cliente,
            unidades=retornaveis_com_agente, autor=operador,
        )
        return retornaveis_com_agente

    def test_lista_retornaveis_em_posse(self, retornaveis_com_cliente, cliente):
        em_posse = retorno_service.retornaveis_em_posse(cliente=cliente)
        assert em_posse.count() == 5

    def test_tempo_em_posse_cresce(self, retornaveis_com_cliente, cliente):
        unidade = retorno_service.retornaveis_em_posse(cliente=cliente).first()
        dias = (timezone.now() - unidade.custodia_desde).days
        assert dias >= 0
        assert unidade.custodia_desde is not None

    def test_retorno_devolve_ao_deposito(
        self, retornaveis_com_cliente, deposito, modelo_retornavel, operador
    ):
        movimentacao = retorno_service.registrar_retorno(
            unidades=retornaveis_com_cliente[:3], destino=deposito, autor=operador
        )
        assert movimentacao.tipo == TipoMovimentacao.RETORNO
        assert saldo_service.saldo_em_custodia(deposito, modelo=modelo_retornavel) == 3

    def test_retorno_devolve_ao_agente(
        self, retornaveis_com_cliente, agente, modelo_retornavel, operador
    ):
        retorno_service.registrar_retorno(
            unidades=retornaveis_com_cliente[:2], destino=agente, autor=operador
        )
        assert saldo_service.saldo_disponivel(agente, modelo=modelo_retornavel) == 2

    def test_descartavel_entregue_nao_pode_retornar(
        self, unidades_com_agente, agente, cliente, deposito, operador
    ):
        """ISC-RN-05: rejeita mesmo por id direto, não só na UI."""
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.ENTREGA,
            origem=agente, destino=cliente,
            unidades=unidades_com_agente[:3], autor=operador,
        )
        with pytest.raises(UnidadeTerminal, match="descartável"):
            retorno_service.registrar_retorno(
                unidades=unidades_com_agente[:3], destino=deposito, autor=operador
            )

    def test_descartavel_nao_aparece_na_lista_de_retornaveis(
        self, unidades_com_agente, agente, cliente, operador
    ):
        custodia_service.registrar_movimentacao(
            tipo=TipoMovimentacao.ENTREGA,
            origem=agente, destino=cliente,
            unidades=unidades_com_agente[:3], autor=operador,
        )
        assert retorno_service.retornaveis_em_posse(cliente=cliente).count() == 0


class TestManutencao:
    """ISC-RN-14: manutenção é ciclo reversível, não baixa."""

    def test_envio_tira_do_saldo_disponivel(
        self, unidades_no_deposito, deposito, modelo_descartavel, operador
    ):
        antes = saldo_service.saldo_disponivel(deposito, modelo=modelo_descartavel)
        transferencia_service.enviar_para_manutencao(
            origem=deposito, modelo=modelo_descartavel, quantidade=2, autor=operador
        )
        assert saldo_service.saldo_disponivel(deposito, modelo=modelo_descartavel) == antes - 2

    def test_retorno_de_manutencao_recoloca_no_deposito(
        self, unidades_no_deposito, deposito, modelo_descartavel, operador
    ):
        movimentacao = transferencia_service.enviar_para_manutencao(
            origem=deposito, modelo=modelo_descartavel, quantidade=2, autor=operador
        )
        unidades = [linha.unidade for linha in movimentacao.linhas.all()]

        transferencia_service.retornar_de_manutencao(
            unidades=unidades, destino=deposito, autor=operador
        )
        assert saldo_service.saldo_em_custodia(deposito, modelo=modelo_descartavel) == 10


class TestBaixa:
    """ISC-RN-13: baixa sem motivo é buraco no inventário."""

    def test_baixa_tira_do_saldo(
        self, unidades_no_deposito, deposito, modelo_descartavel, operador
    ):
        baixa_service.dar_baixa(
            origem=deposito, motivo=MotivoBaixa.AVARIA,
            justificativa="Carcaça trincada", autor=operador,
            modelo=modelo_descartavel, quantidade=3,
        )
        assert saldo_service.saldo_em_custodia(deposito, modelo=modelo_descartavel) == 7

    def test_baixa_exige_justificativa(
        self, unidades_no_deposito, deposito, modelo_descartavel, operador
    ):
        with pytest.raises(MovimentacaoInvalida, match="justificativa"):
            baixa_service.dar_baixa(
                origem=deposito, motivo=MotivoBaixa.PERDA, justificativa="",
                autor=operador, modelo=modelo_descartavel, quantidade=1,
            )

    def test_baixa_registra_autor_e_motivo(
        self, unidades_no_deposito, deposito, modelo_descartavel, operador
    ):
        movimentacao = baixa_service.dar_baixa(
            origem=deposito, motivo=MotivoBaixa.PERDA,
            justificativa="Extraviada no transporte", autor=operador,
            modelo=modelo_descartavel, quantidade=1,
        )
        assert movimentacao.autor_id == operador.pk
        assert movimentacao.motivo_baixa == MotivoBaixa.PERDA
        assert movimentacao.justificativa == "Extraviada no transporte"

    def test_nao_baixa_unidade_reservada(
        self, unidades_com_agente, agente, cliente, modelo_descartavel, operador
    ):
        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 8)], autor=operador
        )
        solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 8)], autor=operador,
        )
        with pytest.raises(UnidadeIndisponivel):
            baixa_service.dar_baixa(
                origem=agente, motivo=MotivoBaixa.PERDA, justificativa="Sumiu",
                autor=operador, unidades=unidades_com_agente[:1],
            )


class TestDesativacao:
    """ISC-RN-18: desativação não pode evaporar estoque."""

    def test_desativar_agente_com_saldo_e_bloqueado(
        self, agente, unidades_com_agente
    ):
        with pytest.raises(AgenteComSaldo, match="em custódia"):
            cadastro_service.desativar_agente(agente)
        agente.refresh_from_db()
        assert agente.is_active

    def test_desativar_agente_sem_saldo_e_permitido(self, agente):
        cadastro_service.desativar_agente(agente)
        agente.refresh_from_db()
        assert not agente.is_active

    def test_agente_desativado_mantem_historico(
        self, agente, unidades_com_agente, deposito, modelo_descartavel, operador
    ):
        transferencia_service.transferir(
            origem=agente, destino=deposito, modelo=modelo_descartavel,
            quantidade=8, autor=operador,
        )
        cadastro_service.desativar_agente(agente)

        assert Movimentacao.objects.filter(
            destino=custodia_service.custodia_de(agente)
        ).exists()

    def test_agente_desativado_sai_do_manager_padrao(self, agente):
        from iscas.models.cadastro import Agente

        cadastro_service.desativar_agente(agente)
        assert not Agente.objects.filter(pk=agente.pk).exists()
        assert Agente.todos.filter(pk=agente.pk).exists()


class TestImutabilidadeDoTipo:
    """ISC-RN-04: mudar o tipo reescreveria o significado do histórico."""

    def test_bloqueia_troca_com_movimentacao(
        self, modelo_descartavel, unidades_no_deposito
    ):
        with pytest.raises(TipoModeloImutavel):
            cadastro_service.alterar_modelo(
                modelo_descartavel, tipo=TipoModelo.RETORNAVEL
            )

    def test_permite_troca_sem_movimentacao(self, modelo_descartavel):
        cadastro_service.alterar_modelo(modelo_descartavel, tipo=TipoModelo.RETORNAVEL)
        modelo_descartavel.refresh_from_db()
        assert modelo_descartavel.tipo == TipoModelo.RETORNAVEL

    def test_clean_tambem_bloqueia(self, modelo_descartavel, unidades_no_deposito):
        modelo_descartavel.tipo = TipoModelo.RETORNAVEL
        with pytest.raises(ValidationError):
            modelo_descartavel.clean()


class TestCpfLgpd:
    """ISC-RN-16 e ISC-ADR-14: CPF cifrado, mascarado nas listagens."""

    def test_cpf_e_cifrado_em_repouso(self, agente):
        from iscas.models.cadastro import Agente

        bruto = Agente.todos.filter(pk=agente.pk).values("cpf_cifrado").first()
        assert "39053344705" not in bruto["cpf_cifrado"]

    def test_cpf_decifra_corretamente(self, agente):
        agente.refresh_from_db()
        assert agente.cpf == "39053344705"

    def test_mascara_nao_expoe_cpf_completo(self, agente):
        mascarado = agente.cpf_mascarado
        assert "39053344705" not in mascarado
        assert mascarado.startswith("***")
        assert mascarado.endswith("**")

    def test_hash_garante_unicidade(self, agente):
        from django.db import IntegrityError, transaction

        from iscas.models.cadastro import Agente

        duplicado = Agente(
            nome="Clone", telefone="11900000000",
            logradouro="Rua Y", cidade="São Paulo", uf="SP",
        )
        duplicado.cpf = "39053344705"
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                duplicado.save()

    def test_cpf_invalido_e_rejeitado(self):
        from iscas.models.cadastro import Agente

        agente = Agente(
            nome="Inválido", telefone="11900000000",
            logradouro="Rua Z", cidade="São Paulo", uf="SP",
        )
        agente.cpf = "11111111111"
        with pytest.raises(ValidationError):
            agente.clean()


class TestEntradaEmLote:
    """ISC-RF-07, ISC-RF-08, ISC-RF-09."""

    def test_parse_identificadores_aceita_varios_separadores(self):
        texto = "ISC001\nISC002\r\nISC003, ISC004; ISC005"
        assert entrada_service.parse_identificadores(texto) == [
            "ISC001", "ISC002", "ISC003", "ISC004", "ISC005"
        ]

    def test_parse_remove_duplicatas_preservando_ordem(self):
        assert entrada_service.parse_identificadores("A\nB\nA\nC") == ["A", "B", "C"]

    def test_gerar_faixa_sequencial(self):
        assert entrada_service.gerar_faixa(prefixo="ISC", inicio=1, quantidade=3) == [
            "ISC000001", "ISC000002", "ISC000003"
        ]

    def test_entrada_rejeita_identificador_ja_cadastrado(
        self, modelo_descartavel, deposito, unidades_no_deposito, operador
    ):
        with pytest.raises(MovimentacaoInvalida, match="já cadastrado"):
            entrada_service.registrar_entrada(
                modelo=modelo_descartavel, identificadores=["D001"],
                destino=deposito, autor=operador,
            )

    def test_entrada_rejeita_duplicata_na_propria_lista(
        self, modelo_descartavel, deposito, operador
    ):
        with pytest.raises(MovimentacaoInvalida, match="repetidos"):
            entrada_service.registrar_entrada(
                modelo=modelo_descartavel, identificadores=["Z1", "Z1"],
                destino=deposito, autor=operador,
            )

    def test_gera_identificador_interno(self, modelo_descartavel, deposito, operador):
        """ISC-RF-09."""
        _, unidades = entrada_service.registrar_entrada(
            modelo=modelo_descartavel, identificadores=[], destino=deposito,
            autor=operador, gerar_internos=True, quantidade=3,
        )
        assert len(unidades) == 3
        assert all(u.identificador_gerado for u in unidades)
        assert unidades[0].identificador.startswith(f"GS-{modelo_descartavel.codigo}-")

    def test_entrada_gera_lancamento_de_entrada(
        self, modelo_descartavel, deposito, operador
    ):
        """Nenhuma unidade existe no estoque sem constar no livro."""
        movimentacao, unidades = entrada_service.registrar_entrada(
            modelo=modelo_descartavel, identificadores=["W1", "W2"],
            destino=deposito, autor=operador, nota_fiscal="NF-99",
        )
        assert movimentacao.tipo == TipoMovimentacao.ENTRADA
        assert movimentacao.origem.tipo == TipoCustodia.EXTERNO
        assert movimentacao.nota_fiscal == "NF-99"
        assert movimentacao.linhas.count() == 2


class TestMensagemWhatsApp:
    """ISC-RF-29: o sistema monta o texto; quem envia é o operador."""

    def test_texto_tem_cliente_endereco_e_quantidade(
        self, cliente, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        from iscas.services import mensagem as mensagem_service

        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 3)], autor=operador
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 3)], autor=operador,
        )
        texto = mensagem_service.montar_texto_atribuicao(atribuicao)

        assert cliente.nome_razao_social in texto
        assert cliente.cidade in texto
        assert "3x" in texto
        assert agente.nome in texto

    def test_link_wa_me_com_ddi(self, cliente, agente, unidades_com_agente,
                                modelo_descartavel, operador):
        from iscas.services import mensagem as mensagem_service

        solicitacao = solicitacao_service.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 1)], autor=operador
        )
        atribuicao = solicitacao_service.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 1)], autor=operador,
        )
        link = mensagem_service.link_whatsapp(atribuicao)
        assert link.startswith("https://wa.me/5511999990000?text=")

    def test_telefone_ja_com_ddi_nao_duplica(self):
        from iscas.services import mensagem as mensagem_service

        assert mensagem_service.telefone_para_wa("+55 (11) 99999-0000") == "5511999990000"

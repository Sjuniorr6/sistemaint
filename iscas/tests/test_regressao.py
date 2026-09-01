"""Regressões de bugs que chegaram ao operador.

Cada teste aqui corresponde a um erro 500 visto em uso real. Ficam juntos, e
não espalhados pelos arquivos de tema, para que a origem seja explícita: são
casos que a suíte não pegou e que não podem voltar.
"""
import os
import re

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from iscas.enums import (
    GRUPO_OPERADORES,
    GeoOrigem,
    StatusAtribuicao,
    StatusSolicitacao,
)
from iscas.models.cadastro import Agente, Cliente
from iscas.models.custodia import Custodia
from iscas.services.custodia import custodia_de
from iscas.services.geo import ajustar_pin, coordenada_valida

pytestmark = pytest.mark.django_db


@pytest.fixture
def operador_logado(client, operador):
    grupo, _ = Group.objects.get_or_create(name=GRUPO_OPERADORES)
    operador.groups.add(grupo)
    client.force_login(operador)
    return operador


class TestPinSemCoordenada:
    """`InvalidOperation` ao salvar posição de agente sem pin.

    A ficha só mostrava o mapa quando já havia coordenada, então um agente
    PENDENTE não tinha como ganhar uma — e o POST ia com campos vazios, que
    `Decimal("")` transformava em erro 500.
    """

    @pytest.mark.parametrize(
        "latitude,longitude",
        [
            ("", ""),
            (None, None),
            ("", "-46.6"),
            ("abc", "def"),
            ("-23.5", ""),
            ("999", "-46.6"),      # latitude fora do intervalo
            ("-23.5", "999"),      # longitude fora do intervalo
        ],
    )
    def test_coordenada_invalida_devolve_none(self, latitude, longitude):
        assert coordenada_valida(latitude, longitude) is None

    @pytest.mark.parametrize(
        "latitude,longitude",
        [("-23.550520", "-46.633308"), (-23.55, -46.63), ("0", "0")],
    )
    def test_coordenada_valida_converte(self, latitude, longitude):
        assert coordenada_valida(latitude, longitude) is not None

    def test_ajustar_pin_vazio_levanta_valueerror(self, agente):
        with pytest.raises(ValueError, match="Coordenada inválida"):
            ajustar_pin(agente, latitude="", longitude="")

    def test_view_nao_estoura_com_campos_vazios(
        self, client, operador_logado, agente_sem_coordenada
    ):
        """O erro que o operador viu: 500 virou mensagem e redirect."""
        resposta = client.post(
            reverse("iscas:agente_ajustar_pin", args=[agente_sem_coordenada.pk]),
            {"latitude": "", "longitude": ""},
        )
        assert resposta.status_code == 302
        agente_sem_coordenada.refresh_from_db()
        assert agente_sem_coordenada.latitude is None

    def test_view_sem_os_campos_no_post(self, client, operador_logado, agente):
        """POST sem as chaves não pode virar KeyError."""
        resposta = client.post(reverse("iscas:agente_ajustar_pin", args=[agente.pk]), {})
        assert resposta.status_code == 302

    def test_cliente_tambem_protegido(self, client, operador_logado, cliente):
        resposta = client.post(
            reverse("iscas:cliente_ajustar_pin", args=[cliente.pk]),
            {"latitude": "", "longitude": ""},
        )
        assert resposta.status_code == 302

    def test_pin_valido_continua_funcionando(self, client, operador_logado, agente):
        client.post(
            reverse("iscas:agente_ajustar_pin", args=[agente.pk]),
            {"latitude": "-23.600000", "longitude": "-46.700000"},
        )
        agente.refresh_from_db()
        assert float(agente.latitude) == pytest.approx(-23.6)
        assert agente.geo_origem == GeoOrigem.MANUAL

    def test_ficha_de_agente_sem_coordenada_mostra_o_mapa(
        self, client, operador_logado, agente_sem_coordenada
    ):
        """Sem mapa, não havia como posicionar o pin — o beco sem saída."""
        conteudo = client.get(
            reverse("iscas:agente_detalhe", args=[agente_sem_coordenada.pk])
        ).content.decode()

        assert "mapaAgente" in conteudo
        assert "Clique no mapa para posicionar" in conteudo


class TestEntidadeSemCustodia:
    """Página de cliente derrubada por falta de conta de custódia.

    A conta nasce por signal, mas dado importado, criado com `bulk_create` ou
    afetado por limpeza manual pode ficar sem — e a ficha inteira quebrava.
    """

    def test_custodia_de_cria_conta_faltante(self, cliente):
        Custodia.todos.filter(cliente=cliente).delete()
        assert not Custodia.todos.filter(cliente=cliente).exists()

        conta = custodia_de(cliente)

        assert conta.pk is not None
        assert conta.cliente_id == cliente.pk

    def test_conta_criada_nasce_vazia(self, cliente):
        """Criar a conta não inventa estoque: o saldo derivado é zero."""
        from iscas.services.saldo import saldo_em_custodia

        Custodia.todos.filter(cliente=cliente).delete()
        assert saldo_em_custodia(cliente) == 0

    def test_ficha_de_cliente_sem_custodia_carrega(
        self, client, operador_logado, cliente
    ):
        """O erro que o operador viu."""
        Custodia.todos.filter(cliente=cliente).delete()

        resposta = client.get(reverse("iscas:cliente_detalhe", args=[cliente.pk]))

        assert resposta.status_code == 200

    def test_ficha_de_agente_sem_custodia_carrega(
        self, client, operador_logado, agente
    ):
        Custodia.todos.filter(agente=agente).delete()
        assert client.get(
            reverse("iscas:agente_detalhe", args=[agente.pk])
        ).status_code == 200

    def test_nao_duplica_conta_existente(self, cliente):
        primeira = custodia_de(cliente)
        assert custodia_de(cliente).pk == primeira.pk
        assert Custodia.todos.filter(cliente=cliente).count() == 1

    def test_seed_custodias_repara_em_lote(self, cliente, agente):
        from django.core.management import call_command

        Custodia.todos.filter(cliente=cliente).delete()
        Custodia.todos.filter(agente=agente).delete()

        call_command("seed_custodias", verbosity=0)

        assert Custodia.todos.filter(cliente=cliente).exists()
        assert Custodia.todos.filter(agente=agente).exists()


class TestCoordenadaNoJavaScript:
    """Locale pt-br renderiza float com vírgula e quebra o JS.

    `{{ agente.latitude }}` dentro de `<script>` vira `-23,55052` — vírgula —,
    que é `SyntaxError: Unexpected number`. O erro mata o `<script>` inteiro,
    o Alpine não encontra `enderecoComMapa()` e o mapa some da tela. Aparecia
    só na EDIÇÃO, porque no cadastro novo o valor é `null` e não tem vírgula.
    """

    #: Coordenada com vírgula decimal (`-23,55` em vez de `-23.55`).
    VIRGULA_DECIMAL = re.compile(r"-?\d+,\d+")

    #: Comentários JS; a busca é sobre código executável, e um comentário
    #: explicando o bug não é o bug.
    COMENTARIO = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)

    def _scripts(self, html):
        # Só blocos com corpo: `<script src=...></script>` não tem o que checar.
        return [
            bloco
            for bloco in re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
            if bloco.strip()
        ]

    def _sem_virgula_decimal(self, html, contexto):
        for bloco in self._scripts(html):
            codigo = self.COMENTARIO.sub("", bloco)
            achado = self.VIRGULA_DECIMAL.search(codigo)
            assert achado is None, (
                f"{contexto}: número com vírgula decimal dentro de <script> "
                f"({achado.group()}) — quebra o JS sob locale pt-br."
            )

    def test_edicao_de_agente_com_coordenada(self, client, operador_logado, agente):
        html = client.get(
            reverse("iscas:agente_editar", args=[agente.pk])
        ).content.decode()
        self._sem_virgula_decimal(html, "form de edição do agente")

    def test_edicao_de_cliente_com_coordenada(self, client, operador_logado, cliente):
        html = client.get(
            reverse("iscas:cliente_editar", args=[cliente.pk])
        ).content.decode()
        self._sem_virgula_decimal(html, "form de edição do cliente")

    def test_ficha_do_agente_com_coordenada(self, client, operador_logado, agente):
        html = client.get(
            reverse("iscas:agente_detalhe", args=[agente.pk])
        ).content.decode()
        self._sem_virgula_decimal(html, "ficha do agente")

    def test_cadastro_novo_usa_null(self, client, operador_logado):
        html = client.get(reverse("iscas:agente_criar")).content.decode()
        self._sem_virgula_decimal(html, "cadastro novo")
        assert "const latSalva = null;" in html

    def test_coordenada_chega_com_ponto_decimal(
        self, client, operador_logado, agente
    ):
        """O valor precisa ser utilizável, não só sintaticamente válido."""
        html = client.get(
            reverse("iscas:agente_editar", args=[agente.pk])
        ).content.decode()
        assert "const latSalva = -23.550520;" in html

    def test_campos_ocultos_da_ficha_usam_ponto(
        self, client, operador_logado, agente
    ):
        """Vírgula aqui faria o POST ser rejeitado como coordenada inválida."""
        html = client.get(
            reverse("iscas:agente_detalhe", args=[agente.pk])
        ).content.decode()
        assert 'id="pinLat"' in html
        assert 'value="-23.550520"' in html

    def test_pin_da_ficha_volta_pelo_post(self, client, operador_logado, agente):
        """Ida e volta: o valor renderizado é aceito de volta pelo servidor."""
        html = client.get(
            reverse("iscas:agente_detalhe", args=[agente.pk])
        ).content.decode()
        valor = re.search(r'id="pinLat"\s*\n?\s*value="([^"]*)"', html).group(1)

        resposta = client.post(
            reverse("iscas:agente_ajustar_pin", args=[agente.pk]),
            {"latitude": valor, "longitude": valor},
        )
        agente.refresh_from_db()
        assert resposta.status_code == 302
        assert agente.geo_origem == GeoOrigem.MANUAL

    def test_alpine_encontra_a_funcao(self, client, operador_logado, agente):
        """A definição precisa estar íntegra — era o efeito do SyntaxError."""
        html = client.get(
            reverse("iscas:agente_editar", args=[agente.pk])
        ).content.decode()
        assert "function enderecoComMapa()" in html
        assert 'x-data="enderecoComMapa()"' in html

    def test_nao_vaza_comentario_de_template_no_javascript(
        self, client, operador_logado, agente
    ):
        """`{# … #}` dentro de `<script>` de um include vaza para o HTML.

        Erro que cometi ao documentar a correção: o comentário de template
        sobrevive ao include e chega ao navegador como sintaxe inválida,
        derrubando o script exatamente como a vírgula fazia.
        """
        for rota, args in [
            ("iscas:agente_editar", [agente.pk]),
            ("iscas:agente_criar", []),
            ("iscas:agente_detalhe", [agente.pk]),
        ]:
            html = client.get(reverse(rota, args=args)).content.decode()
            for bloco in self._scripts(html):
                assert "{#" not in bloco, f"{rota}: comentário de template no <script>"
                assert "{%" not in bloco, f"{rota}: tag de template não resolvida no <script>"

    @pytest.mark.parametrize(
        "rota,com_agente",
        [
            ("iscas:agente_editar", True),
            ("iscas:agente_criar", False),
            ("iscas:agente_detalhe", True),
            ("iscas:cliente_criar", False),
            ("iscas:mapa", False),
        ],
    )
    def test_javascript_servido_e_sintaticamente_valido(
        self, client, operador_logado, agente, rota, com_agente
    ):
        """Valida o JS com um parser de verdade (`node --check`).

        A checagem por regex não basta: ela não pegou o vazamento de `{# #}`.
        Um parser real pega qualquer sintaxe inválida, seja qual for a origem.
        Se o Node não estiver instalado, o teste é pulado — não é dependência
        do app, é ferramenta de verificação.
        """
        import shutil
        import subprocess
        import tempfile

        node = shutil.which("node")
        if not node:
            pytest.skip("node não disponível para validar sintaxe JS")

        html = client.get(
            reverse(rota, args=[agente.pk] if com_agente else [])
        ).content.decode()
        codigo = "\n".join(self._scripts(html))
        if not codigo.strip():
            pytest.skip(f"{rota} não tem JavaScript inline")

        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as arquivo:
            arquivo.write(codigo)
            caminho = arquivo.name

        try:
            resultado = subprocess.run(
                [node, "--check", caminho], capture_output=True, text=True
            )
            assert resultado.returncode == 0, (
                f"{rota}: JavaScript servido tem erro de sintaxe.\n"
                f"{resultado.stderr[:600]}"
            )
        finally:
            os.unlink(caminho)


class TestEntregaComAtribuicaoEmRota:
    """`EM_ROTA → ABERTA não é permitida` ao confirmar entrega.

    Faltava a transição na tabela. Quando a última atribuição ativa de uma
    solicitação EM_ROTA sai de cena — entregue sem cobrir o pedido inteiro, ou
    cancelada — o recálculo precisa devolver a solicitação para ABERTA, o mesmo
    caminho que já existia a partir de ATRIBUIDA.

    Sintoma exato relatado: a entrega só funcionava se o operador NÃO marcasse
    a atribuição como em rota antes.
    """

    def _solicitacao_em_rota(self, cliente, agente, modelo, operador, *, pedido, leva):
        from iscas.services import solicitacao as ss

        solicitacao = ss.abrir_solicitacao(
            cliente=cliente, itens=[(modelo, pedido)], autor=operador
        )
        atribuicao = ss.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo, leva)], autor=operador,
        )
        ss.marcar_em_rota(atribuicao=atribuicao, autor=operador)
        solicitacao.refresh_from_db()
        assert solicitacao.status == StatusSolicitacao.EM_ROTA
        return solicitacao, atribuicao

    def test_entrega_parcial_a_partir_de_em_rota(
        self, cliente, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """O caso do operador: pediu 10, um agente leva 5, entrega em rota."""
        from iscas.services import solicitacao as ss

        solicitacao, atribuicao = self._solicitacao_em_rota(
            cliente, agente, modelo_descartavel, operador, pedido=10, leva=5
        )

        ss.confirmar_entrega(atribuicao=atribuicao, autor=operador)

        solicitacao.refresh_from_db()
        atribuicao.refresh_from_db()
        assert atribuicao.status == StatusAtribuicao.ENTREGUE
        # Sem cobertura total, volta a ser pedido em aberto — não fica travada.
        assert solicitacao.status == StatusSolicitacao.ABERTA

    def test_entrega_total_a_partir_de_em_rota(
        self, cliente, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """Cobertura total continua fechando em ENTREGUE."""
        from iscas.services import solicitacao as ss

        solicitacao, atribuicao = self._solicitacao_em_rota(
            cliente, agente, modelo_descartavel, operador, pedido=5, leva=5
        )

        ss.confirmar_entrega(atribuicao=atribuicao, autor=operador)

        solicitacao.refresh_from_db()
        assert solicitacao.status == StatusSolicitacao.ENTREGUE

    def test_cancelar_unica_atribuicao_em_rota(
        self, cliente, agente, unidades_com_agente, modelo_descartavel, operador
    ):
        """Mesmo beco pelo cancelamento — também estourava."""
        from iscas.services import solicitacao as ss

        solicitacao, atribuicao = self._solicitacao_em_rota(
            cliente, agente, modelo_descartavel, operador, pedido=5, leva=5
        )

        ss.cancelar_atribuicao(
            atribuicao=atribuicao, motivo="agente desistiu", autor=operador
        )

        solicitacao.refresh_from_db()
        assert solicitacao.status == StatusSolicitacao.ABERTA

    def test_fluxo_completo_com_duas_rodadas(
        self, cliente, agente, modelo_descartavel, operador
    ):
        """Entrega parcial, nova atribuição e fechamento — de ponta a ponta."""
        from iscas.services import entrada as es
        from iscas.services import solicitacao as ss

        es.registrar_entrada(
            modelo=modelo_descartavel,
            identificadores=[f"RG{i:03d}" for i in range(1, 11)],
            destino=agente, autor=operador,
        )
        solicitacao = ss.abrir_solicitacao(
            cliente=cliente, itens=[(modelo_descartavel, 10)], autor=operador
        )

        primeira = ss.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        ss.marcar_em_rota(atribuicao=primeira, autor=operador)
        ss.confirmar_entrega(atribuicao=primeira, autor=operador)
        solicitacao.refresh_from_db()
        assert solicitacao.status == StatusSolicitacao.ABERTA

        segunda = ss.criar_atribuicao(
            solicitacao=solicitacao, agente=agente,
            itens=[(modelo_descartavel, 5)], autor=operador,
        )
        ss.marcar_em_rota(atribuicao=segunda, autor=operador)
        ss.confirmar_entrega(atribuicao=segunda, autor=operador)

        solicitacao.refresh_from_db()
        assert solicitacao.status == StatusSolicitacao.ENTREGUE
        assert ss.cobertura_total(solicitacao)

    def test_entrega_pela_view_com_atribuicao_em_rota(
        self, client, operador_logado, cliente, agente,
        unidades_com_agente, modelo_descartavel, operador,
    ):
        """Pela tela, que é como o operador encontrou o erro."""
        from iscas.services import solicitacao as ss

        solicitacao, atribuicao = self._solicitacao_em_rota(
            cliente, agente, modelo_descartavel, operador, pedido=10, leva=5
        )

        resposta = client.post(
            reverse("iscas:atribuicao_entregar", args=[atribuicao.pk]),
            {"entregue_em": "", "recebido_por": "Portaria"},
        )

        atribuicao.refresh_from_db()
        assert resposta.status_code == 302
        assert atribuicao.status == StatusAtribuicao.ENTREGUE
        assert atribuicao.recebido_por == "Portaria"

    def test_recalculo_alcanca_todo_estado_que_precisa(self):
        """Guarda estrutural: a tabela cobre o que o recálculo pode pedir.

        `_recalcular_status_solicitacao` deriva o status do estado das
        atribuições. Se ele puder concluir um destino que a tabela não permite,
        o resultado é exceção na cara do operador — foi o que aconteceu.
        """
        from iscas.services.solicitacao import TRANSICOES_SOLICITACAO

        # A partir de ATRIBUIDA ou EM_ROTA, o recálculo pode concluir qualquer
        # um destes três, conforme entregas e cancelamentos.
        for origem in (StatusSolicitacao.ATRIBUIDA, StatusSolicitacao.EM_ROTA):
            for destino in (
                StatusSolicitacao.ABERTA,
                StatusSolicitacao.ATRIBUIDA,
                StatusSolicitacao.EM_ROTA,
                StatusSolicitacao.ENTREGUE,
            ):
                if origem == destino:
                    continue
                assert destino in TRANSICOES_SOLICITACAO[origem], (
                    f"O recálculo pode pedir {origem} → {destino}, "
                    "mas a tabela não permite."
                )


class TestContrasteDoLayout:
    """O CSS do app precisa neutralizar os padrões ilegíveis do Bootstrap.

    `text-muted` (#6c757d) sobre as superfícies escuras do app dá ~2.8:1,
    abaixo do mínimo AA de 4.5:1 — foi o que o operador reportou como
    "letras ruins de enxergar".
    """

    def test_wrapper_envolve_o_conteudo(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:painel")).content.decode()
        assert "iscas-app" in conteudo

    def test_text_muted_e_sobrescrito(self, client, operador_logado):
        conteudo = client.get(reverse("iscas:painel")).content.decode()
        assert ".iscas-app .text-muted" in conteudo

    @pytest.mark.parametrize(
        "rota",
        ["iscas:painel", "iscas:agente_lista", "iscas:unidade_lista", "iscas:extrato"],
    )
    def test_paginas_carregam_o_tema(self, client, operador_logado, rota):
        conteudo = client.get(reverse(rota)).content.decode()
        assert "--iscas-texto" in conteudo

"""Regras de negócio do app Chamados (camada de Services — fat services).

Concentra: abertura do chamado (gera protocolo, grava evento inicial), a
máquina de estados (ponto único de mudança de status, ADR-004) e a geração
concorrente-safe do protocolo (ADR-006). Views são finas e sempre passam por
aqui; nenhuma view muda status direto.

Toda transição é atômica: a mudança de status e o ChamadoEvento ocorrem na
mesma transação (falha em um reverte o outro).
"""
from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from chamados.enums import Acao, Status
from chamados.permissions import is_inteligencia, is_quality


# ---------------------------------------------------------------------------
# Protocolo AAAA-NNNNNN reiniciado por ano (RN-07, ADR-006)
# ---------------------------------------------------------------------------


def gerar_protocolo(ano: int) -> str:
    """Gera o próximo protocolo `AAAA-NNNNNN` do ano, concorrente-safe.

    Sob concorrência, dois chamados poderiam derivar o mesmo sequencial. A
    proteção final é a constraint UNIQUE de `protocolo`: o service de abertura
    roda dentro de `transaction.atomic` e faz retry quando o UNIQUE estoura.
    Aqui derivamos o próximo sequencial a partir do maior protocolo já gravado
    no ano (o prefixo `AAAA-` ordena lexicograficamente igual ao numérico).
    """
    from chamados.models import Chamado

    prefixo = f"{ano}-"
    ultimo = (
        Chamado.objects.filter(protocolo__startswith=prefixo)
        .aggregate(maior=Max("protocolo"))
        .get("maior")
    )
    proximo = 1 if not ultimo else int(ultimo.split("-", 1)[1]) + 1
    return f"{prefixo}{proximo:06d}"


# ---------------------------------------------------------------------------
# Abertura do chamado (RN-01, RN-06, RN-08 — ADR-003)
# ---------------------------------------------------------------------------


def abrir_chamado(
    *,
    autor,
    cliente,
    categoria,
    numero_equipamento,
    modelo_equipamento,
    problema_relatado,
    responsavel,
    contato_nome,
    contato_meio,
    contato_telefone="",
    contato_email="",
    encaminhar=False,
    procedimento_realizado=None,
    tratativa=None,
    responsavel_inteligencia=None,
):
    """Cria um chamado em ABERTO ou, quando `encaminhar`, direto em ENCAMINHADO.

    Só Quality abre (RN-01). O `responsavel` deve ser do grupo quality (RN-02).
    `aberto_em` é NOW() do servidor (RN-06). Abrindo já encaminhado (RN-08),
    exige procedimento, tratativa e um responsável do grupo inteligencia. Grava
    o evento inicial (ABRIR) — a criação também entra no log (RN-05).

    Tudo numa transação; retry sob colisão de protocolo (UNIQUE, ADR-006).
    """
    from chamados.models import Chamado, ChamadoEvento

    if not is_quality(autor):
        raise PermissionDenied("Apenas usuários do grupo 'quality' podem abrir chamados.")
    if not is_quality(responsavel):
        raise ValidationError(
            {"responsavel": "O responsável deve ser um usuário do grupo 'quality'."}
        )

    if encaminhar:
        _exigir(procedimento_realizado, "procedimento_realizado")
        _exigir(tratativa, "tratativa")
        if not is_inteligencia(responsavel_inteligencia):
            raise ValidationError(
                {"responsavel_inteligencia": "Informe um responsável do grupo 'inteligencia'."}
            )
        status_inicial = Status.ENCAMINHADO
    else:
        status_inicial = Status.ABERTO
        procedimento_realizado = None
        tratativa = None
        responsavel_inteligencia = None

    agora = timezone.now()
    ano = agora.year

    # Retry sob colisão de protocolo: só o INSERT do Chamado disputa o UNIQUE;
    # cada tentativa é uma transação própria (savepoint), então o retry não
    # arrasta um estado sujo.
    ultimo_erro = None
    for _ in range(5):
        try:
            with transaction.atomic():
                chamado = Chamado(
                    protocolo=gerar_protocolo(ano),
                    cliente=cliente,
                    categoria=categoria,
                    numero_equipamento=numero_equipamento,
                    modelo_equipamento=modelo_equipamento,
                    problema_relatado=problema_relatado,
                    contato_nome=contato_nome,
                    contato_telefone=contato_telefone or "",
                    contato_email=contato_email or "",
                    contato_meio=contato_meio,
                    responsavel=responsavel,
                    responsavel_inteligencia=responsavel_inteligencia,
                    procedimento_realizado=procedimento_realizado,
                    tratativa=tratativa,
                    status=status_inicial,
                    aberto_por=autor,
                    aberto_em=agora,
                )
                chamado.full_clean(exclude=["protocolo"])
                chamado.save()
                ChamadoEvento.objects.create(
                    chamado=chamado,
                    acao=Acao.ABRIR,
                    estado_origem=None,
                    estado_destino=status_inicial,
                    autor=autor,
                    procedimento_snapshot=procedimento_realizado,
                    tratativa_snapshot=tratativa,
                    responsavel_inteligencia=responsavel_inteligencia,
                )
                return chamado
        except Exception as exc:  # noqa: BLE001 — só o UNIQUE de protocolo justifica retry
            if _e_colisao_de_protocolo(exc):
                ultimo_erro = exc
                continue
            raise
    raise ValidationError(
        "Não foi possível gerar um protocolo único após várias tentativas."
    ) from ultimo_erro


def _e_colisao_de_protocolo(exc) -> bool:
    from django.db import IntegrityError

    return isinstance(exc, IntegrityError) and "protocolo" in str(exc).lower()


# ---------------------------------------------------------------------------
# Máquina de estados (ADR-004) — transições declaradas como dado
# ---------------------------------------------------------------------------

# Papéis por posse (usados para autorizar a ação além do grupo).
POSSE_QUALITY = "quality"
POSSE_INTELIGENCIA = "inteligencia"
POSSE_EXPEDICAO = "expedicao"
POSSE_COMERCIAL = "comercial"
POSSE_DONO_ATUAL = "dono_atual"


@dataclass(frozen=True)
class Transicao:
    """Uma transição da máquina de estados (PRD, "Ciclo de Vida do Chamado").

    Declara origens permitidas, estado de destino, papel autorizado e os campos
    obrigatórios da ação. `destino=None` significa "derivado do log" (Reabrir).
    """

    origens: tuple
    destino: object  # Status | None (None = derivado do log, caso Reabrir)
    posse: str
    campos_obrigatorios: tuple = field(default_factory=tuple)


# Chave = Acao; espelha a tabela "Transições válidas" do PRD (RN-14).
# Sem EM_ANALISE: as ações do Quality partem direto de ABERTO.
TRANSICOES = {
    Acao.ENCAMINHAR: Transicao(
        origens=(Status.ABERTO,),
        destino=Status.ENCAMINHADO,
        posse=POSSE_QUALITY,
        campos_obrigatorios=("procedimento_realizado", "tratativa", "responsavel_inteligencia"),
    ),
    Acao.ENCAMINHAR_EXPEDICAO: Transicao(
        # A Inteligência, quando o equipamento precisa de manutenção, encaminha
        # para a Expedição (fila compartilhada). Sem responsável específico — a
        # posse em EXPEDICAO é do grupo inteiro (ver pode_agir).
        origens=(Status.ENCAMINHADO,),
        destino=Status.EXPEDICAO,
        posse=POSSE_INTELIGENCIA,
        campos_obrigatorios=("procedimento_realizado", "tratativa"),
    ),
    Acao.MARCAR_CHEGADA: Transicao(
        # A Expedição confirma que os equipamentos chegaram na base → segue para o
        # Laboratório (fila compartilhada). É a ÚNICA ação da expedição: ela não
        # resolve nem bloqueia. Sem campos obrigatórios (só o registro da chegada).
        origens=(Status.EXPEDICAO,),
        destino=Status.LABORATORIO,
        posse=POSSE_DONO_ATUAL,  # dono de EXPEDICAO = grupo expedicao (pode_agir)
    ),
    Acao.ENCAMINHAR_COMERCIAL: Transicao(
        # O Laboratório informa a tratativa POR EQUIPAMENTO e encaminha para o
        # Comercial (fila compartilhada). Única ação do laboratório por ora. A
        # obrigatoriedade das tratativas é validada especificamente (abaixo).
        origens=(Status.LABORATORIO,),
        destino=Status.COMERCIAL,
        posse=POSSE_DONO_ATUAL,  # dono de LABORATORIO = grupo laboratorio
    ),
    Acao.FINALIZAR_COMERCIAL: Transicao(
        # O Comercial finaliza: informa tratativa + custo (com/sem) POR EQUIPAMENTO
        # e encerra o chamado (RESOLVIDO). Validação específica abaixo.
        origens=(Status.COMERCIAL,),
        destino=Status.RESOLVIDO,
        posse=POSSE_DONO_ATUAL,  # dono de COMERCIAL = grupo comercial
    ),
    Acao.FINALIZAR: Transicao(
        origens=(Status.ABERTO,),
        destino=Status.RESOLVIDO,
        posse=POSSE_QUALITY,
        campos_obrigatorios=("procedimento_realizado",),
    ),
    Acao.RESOLVER: Transicao(
        # Só da Inteligência (ENCAMINHADO). A Expedição NÃO resolve — apenas marca
        # chegada; e o Laboratório, por ora, só recebe (sem ações definidas).
        origens=(Status.ENCAMINHADO,),
        destino=Status.RESOLVIDO,
        posse=POSSE_DONO_ATUAL,
        campos_obrigatorios=("procedimento_realizado",),
    ),
    Acao.BLOQUEAR: Transicao(
        # Quality bloqueia de ABERTO; Inteligência, de ENCAMINHADO. A Expedição
        # NÃO bloqueia (só marca chegada). A posse resolve quem pode (dono atual).
        origens=(Status.ABERTO, Status.ENCAMINHADO),
        destino=Status.BLOQUEADO,
        posse=POSSE_DONO_ATUAL,
        campos_obrigatorios=("motivo",),
    ),
    Acao.REABRIR: Transicao(
        origens=(Status.BLOQUEADO,),
        destino=None,  # derivado do log (ADR-005)
        posse=POSSE_DONO_ATUAL,
        campos_obrigatorios=("motivo",),
    ),
}


def estado_ativo_anterior_ao_bloqueio(chamado):
    """Último estado ativo antes do BLOQUEADO corrente (ADR-005, RN-12).

    Percorre o log do mais recente ao mais antigo e devolve o primeiro
    estado_destino que não seja BLOQUEADO — é para onde a reabertura volta e de
    onde a posse é derivada.
    """
    for evento in chamado.eventos.order_by("-criado_em"):
        if evento.estado_destino != Status.BLOQUEADO:
            return evento.estado_destino
    return Status.ABERTO  # fallback defensivo; o log sempre tem o ABRIR


def _posse_autorizada(user, chamado, posse: str) -> bool:
    if user.is_superuser:
        return True
    if posse == POSSE_QUALITY:
        return is_quality(user)
    if posse == POSSE_INTELIGENCIA:
        # Não basta ser do grupo: tem de ser o responsável de inteligência DAQUELE
        # chamado (isolamento individual — intel não age no chamado de outro).
        return is_inteligencia(user) and chamado.responsavel_inteligencia_id == user.id
    # POSSE_DONO_ATUAL: quem detém a posse no estado atual (RN-12, RN-17).
    from chamados.permissions import pode_agir

    return pode_agir(user, chamado)


def executar(chamado, acao, dados, autor):
    """Ponto único de transição de estado (ADR-004).

    Valida, em ordem: (1) a ação existe a partir do estado atual (RN-14); (2) o
    autor tem a posse/grupo autorizado (RN-16, RN-17); (3) os campos exigidos
    pela ação estão presentes (RN-09..RN-12). Só então aplica os campos
    mutáveis, muda o status e grava o ChamadoEvento — na MESMA transação.

    `dados` é um dict com as chaves da ação (procedimento_realizado, tratativa,
    responsavel_inteligencia, motivo). Retorna o chamado atualizado.
    """
    from chamados.models import ChamadoEvento, TratativaEquipamento

    transicao = TRANSICOES.get(acao)
    if transicao is None:
        raise ValidationError(f"Ação desconhecida: {acao}.")

    # (1) transição válida a partir do estado atual (RN-14).
    if chamado.status not in transicao.origens:
        raise ValidationError(
            f"Transição inválida: não é possível '{Acao(acao).label}' a partir de "
            f"'{Status(chamado.status).label}'."
        )

    # (2) posse / grupo autorizado (RN-16, RN-17).
    if not _posse_autorizada(autor, chamado, transicao.posse):
        raise PermissionDenied("Você não tem permissão para esta ação neste chamado.")

    # (3) campos obrigatórios da ação (RN-09..RN-12).
    for campo in transicao.campos_obrigatorios:
        valor = dados.get(campo)
        if campo == "responsavel_inteligencia":
            if not is_inteligencia(valor):
                raise ValidationError(
                    {campo: "Informe um responsável do grupo 'inteligencia'."}
                )
        else:
            _exigir(valor, campo)

    # (3b) Encaminhar p/ Comercial exige uma tratativa por equipamento do chamado.
    tratativas_equip = None
    if acao == Acao.ENCAMINHAR_COMERCIAL:
        tratativas_equip = _validar_tratativas_equipamento(
            chamado, dados.get("tratativas_equipamento")
        )

    # (3c) Finalizar (Comercial) exige tratativa + custo por equipamento.
    finalizacao_equip = None
    if acao == Acao.FINALIZAR_COMERCIAL:
        finalizacao_equip = _validar_finalizacao_comercial(
            chamado, dados.get("finalizacao_equipamento")
        )

    # Destino: fixo, ou derivado do log na reabertura (ADR-005).
    destino = transicao.destino or estado_ativo_anterior_ao_bloqueio(chamado)

    with transaction.atomic():
        origem = chamado.status

        # Aplica campos mutáveis (só os que a ação carrega; RN-04).
        if dados.get("procedimento_realizado"):
            chamado.procedimento_realizado = dados["procedimento_realizado"]
        if dados.get("tratativa"):
            chamado.tratativa = dados["tratativa"]
        if acao == Acao.ENCAMINHAR:
            chamado.responsavel_inteligencia = dados["responsavel_inteligencia"]

        # Encaminhar p/ Comercial: grava uma linha de tratativa por equipamento e
        # consolida o texto em `chamado.tratativa` (usado no detalhe/snapshot).
        if tratativas_equip:
            for item in tratativas_equip:
                TratativaEquipamento.objects.create(
                    chamado=chamado,
                    numero_equipamento=item["numero"],
                    tratativa=item["tratativa"],
                )
            chamado.tratativa = "\n".join(
                f"{item['numero']}: {item['tratativa']}" for item in tratativas_equip
            )

        # Finalizar (Comercial): completa as linhas de cada equipamento com a
        # tratativa do comercial e o custo (com/sem). Consolida no snapshot.
        if finalizacao_equip:
            from chamados.enums import CustoEquipamento

            for item in finalizacao_equip:
                # Atualiza a linha existente do equipamento (criada pelo lab); se
                # por algum motivo não existir, cria uma nova defensivamente.
                linha = (
                    chamado.tratativas_equipamento
                    .filter(numero_equipamento=item["numero"])
                    .order_by("-id")
                    .first()
                )
                if linha is None:
                    linha = TratativaEquipamento(
                        chamado=chamado, numero_equipamento=item["numero"], tratativa=""
                    )
                linha.tratativa_comercial = item["tratativa"]
                linha.custo = item["custo"]
                linha.save()
            chamado.tratativa = "\n".join(
                f"{item['numero']}: {item['tratativa']} "
                f"({CustoEquipamento(item['custo']).label})"
                for item in finalizacao_equip
            )

        chamado.status = destino
        # save direcionado: nunca toca nos fatos de abertura (RN-03). full_clean
        # em update_fields fecharia a porta a reescritas indevidas de qualquer forma.
        chamado.save(
            update_fields=[
                "procedimento_realizado",
                "tratativa",
                "responsavel_inteligencia",
                "status",
                "atualizado_em",
            ]
        )

        # Snapshot da tratativa: o texto informado, ou o consolidado por
        # equipamento (ENCAMINHAR_COMERCIAL/FINALIZAR_COMERCIAL não têm um
        # `tratativa` único — usam o consolidado gravado em chamado.tratativa).
        tratativa_snapshot = dados.get("tratativa")
        if tratativas_equip or finalizacao_equip:
            tratativa_snapshot = chamado.tratativa

        ChamadoEvento.objects.create(
            chamado=chamado,
            acao=acao,
            estado_origem=origem,
            estado_destino=destino,
            autor=autor,
            procedimento_snapshot=dados.get("procedimento_realizado"),
            tratativa_snapshot=tratativa_snapshot,
            motivo=dados.get("motivo"),
            responsavel_inteligencia=(
                dados.get("responsavel_inteligencia") if acao == Acao.ENCAMINHAR else None
            ),
        )
    return chamado


def _exigir(valor, campo):
    """Garante que um texto obrigatório da ação foi informado (não vazio)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ValidationError({campo: "Este campo é obrigatório para esta ação."})


def equipamentos_do_chamado(chamado):
    """Lista dos números de equipamento do chamado (numero_equipamento é multi-
    valor, gravado como "EQ-1, EQ-2"). Fonte única para o form/modal e a validação."""
    bruto = chamado.numero_equipamento or ""
    return [parte.strip() for parte in bruto.split(",") if parte.strip()]


def _validar_tratativas_equipamento(chamado, tratativas):
    """Valida as tratativas por equipamento no encaminhamento ao Comercial.

    `tratativas` é uma lista de dicts {"numero", "tratativa"}. Exige uma tratativa
    não-vazia para CADA equipamento do chamado (nem a mais, nem a menos). Retorna
    a lista normalizada (na ordem dos equipamentos do chamado).
    """
    equipamentos = equipamentos_do_chamado(chamado)
    por_numero = {}
    for item in tratativas or []:
        numero = (item.get("numero") or "").strip()
        texto = (item.get("tratativa") or "").strip()
        if numero:
            por_numero[numero] = texto

    normalizadas = []
    for numero in equipamentos:
        texto = por_numero.get(numero, "").strip()
        if not texto:
            raise ValidationError(
                {"tratativas_equipamento": f"Informe a tratativa do equipamento {numero}."}
            )
        normalizadas.append({"numero": numero, "tratativa": texto})
    return normalizadas


def _validar_finalizacao_comercial(chamado, finalizacoes):
    """Valida tratativa + custo por equipamento na finalização pelo Comercial.

    `finalizacoes` é uma lista de dicts {"numero", "tratativa", "custo"}. Exige,
    para CADA equipamento do chamado, uma tratativa não-vazia e um custo válido
    (COM_CUSTO/SEM_CUSTO). Retorna a lista normalizada na ordem dos equipamentos.
    """
    from chamados.enums import CustoEquipamento

    equipamentos = equipamentos_do_chamado(chamado)
    por_numero = {}
    for item in finalizacoes or []:
        numero = (item.get("numero") or "").strip()
        if numero:
            por_numero[numero] = {
                "tratativa": (item.get("tratativa") or "").strip(),
                "custo": (item.get("custo") or "").strip(),
            }

    custos_validos = set(CustoEquipamento.values)
    normalizadas = []
    for numero in equipamentos:
        dados_eq = por_numero.get(numero, {"tratativa": "", "custo": ""})
        if not dados_eq["tratativa"]:
            raise ValidationError(
                {"finalizacao_equipamento": f"Informe a tratativa do equipamento {numero}."}
            )
        if dados_eq["custo"] not in custos_validos:
            raise ValidationError(
                {"finalizacao_equipamento": f"Selecione o custo do equipamento {numero}."}
            )
        normalizadas.append(
            {"numero": numero, "tratativa": dados_eq["tratativa"], "custo": dados_eq["custo"]}
        )
    return normalizadas

"""Endpoints JSON que alimentam o mapa.

Views Django comuns com `JsonResponse` — sem DRF (ISC-ADR-12). Não há
consumidor externo, contrato a versionar nem autenticação por token; DRF aqui
seria uma dependência para serializar um dicionário.
"""
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from iscas import selectors
from iscas.models.cadastro import Agente, Cliente, ModeloEquipamento
from iscas.models.operacao import Solicitacao
from iscas.permissions import exige_operador
from iscas.services.cep import CepIndisponivel, CepInvalido, buscar_cep
from iscas.services.geo import agentes_para_solicitacao, agentes_proximos
from iscas.services.saldo import saldo_por_modelo


@exige_operador
def agentes_geojson(request):
    """GeoJSON dos agentes para os marcadores do Leaflet (ISC-RF-16)."""
    modelo = None
    if request.GET.get("modelo"):
        modelo = ModeloEquipamento.objects.filter(pk=request.GET["modelo"]).first()
    return JsonResponse(selectors.agentes_geojson(modelo=modelo))


@exige_operador
def solicitacoes_geojson(request):
    """GeoJSON das solicitações em aberto — a demanda no mapa."""
    return JsonResponse(selectors.solicitacoes_geojson())


@exige_operador
def proximidade(request):
    """Busca por proximidade em JSON, para o mapa desenhar as linhas."""
    try:
        raio_km = float(request.GET.get("raio_km", 50))
    except ValueError:
        return JsonResponse({"erro": "Raio inválido."}, status=400)

    # Modo solicitação: o pedido já sabe o cliente e os modelos que faltam.
    # Devolve cedo porque a resposta é diferente — traz `por_modelo` e
    # `cobre_tudo`, que o modo por ponto não tem como calcular.
    if request.GET.get("solicitacao"):
        return _proximidade_por_solicitacao(request, raio_km)

    cliente = None
    if request.GET.get("cliente"):
        cliente = get_object_or_404(Cliente.todos, pk=request.GET["cliente"])
        latitude, longitude = cliente.latitude, cliente.longitude
    else:
        try:
            latitude = float(request.GET["latitude"])
            longitude = float(request.GET["longitude"])
        except (KeyError, ValueError):
            return JsonResponse(
                {"erro": "Informe cliente, ou latitude e longitude."}, status=400
            )

    modelo = None
    if request.GET.get("modelo"):
        modelo = ModeloEquipamento.objects.filter(pk=request.GET["modelo"]).first()

    try:
        quantidade_minima = int(request.GET.get("quantidade_minima", 0))
    except ValueError:
        quantidade_minima = 0

    resultados = agentes_proximos(
        latitude=latitude,
        longitude=longitude,
        raio_km=raio_km,
        modelo=modelo,
        quantidade_minima=quantidade_minima,
    )

    return JsonResponse(
        {
            "origem": {"latitude": float(latitude), "longitude": float(longitude)},
            "cliente": selectors.cliente_geojson(cliente) if cliente else None,
            "raio_km": raio_km,
            "agentes": [
                {
                    "id": item["agente"].pk,
                    "nome": item["agente"].nome,
                    "telefone": item["agente"].telefone,
                    "cidade": item["agente"].cidade,
                    "latitude": float(item["agente"].latitude),
                    "longitude": float(item["agente"].longitude),
                    "distancia_km": round(item["distancia_km"], 2),
                    "disponivel": item["disponivel"],
                }
                for item in resultados
            ],
        }
    )


def _proximidade_por_solicitacao(request, raio_km):
    """Busca ancorada numa solicitação (ISC-RF-17).

    O operador escolhe O QUE precisa ser atendido e a que distância; cliente,
    modelos e quantidades vêm do pedido. Antes eram três campos soltos —
    cliente, modelo e quantidade mínima — que podiam descrever uma combinação
    que não existe em pedido nenhum.
    """
    solicitacao = get_object_or_404(
        Solicitacao.todos.select_related("cliente"),
        pk=request.GET["solicitacao"],
    )
    cliente = solicitacao.cliente

    # Sem coordenada não há de onde medir. Dizer isso é diferente de devolver
    # lista vazia, que o operador leria como "não há agente por perto".
    if not cliente.tem_coordenada:
        return JsonResponse(
            {
                "erro": (
                    f"{cliente} está sem coordenada no cadastro: não há de onde "
                    "medir a distância. Ajuste o endereço na ficha do cliente."
                )
            },
            status=400,
        )

    resultados = agentes_para_solicitacao(solicitacao=solicitacao, raio_km=raio_km)

    return JsonResponse(
        {
            "origem": {
                "latitude": float(cliente.latitude),
                "longitude": float(cliente.longitude),
            },
            "cliente": selectors.cliente_geojson(cliente),
            "raio_km": raio_km,
            "solicitacao": {
                "id": solicitacao.pk,
                "cliente": cliente.nome_razao_social,
                "status_display": solicitacao.get_status_display(),
                "falta": [
                    {"modelo": modelo.nome, "codigo": modelo.codigo, "falta": falta}
                    for modelo, falta in selectors.modelos_em_falta(solicitacao)
                ],
            },
            "agentes": [
                {
                    "id": item["agente"].pk,
                    "nome": item["agente"].nome,
                    "telefone": item["agente"].telefone,
                    "cidade": item["agente"].cidade,
                    "latitude": float(item["agente"].latitude),
                    "longitude": float(item["agente"].longitude),
                    "distancia_km": round(item["distancia_km"], 2),
                    "disponivel": item["disponivel"],
                    "cobre_tudo": item["cobre_tudo"],
                    "por_modelo": item["por_modelo"],
                }
                for item in resultados
            ],
        }
    )


@exige_operador
def consultar_cep(request):
    """CEP → endereço, para o formulário preencher os campos.

    Erro de CEP não é erro de servidor: devolvemos 200 com `ok: false` e uma
    mensagem que a tela exibe ao lado do campo. O operador segue digitando o
    endereço à mão — a busca por CEP é conveniência, nunca obstáculo.
    """
    try:
        endereco = buscar_cep(request.GET.get("cep", ""))
    except CepInvalido as exc:
        return JsonResponse({"ok": False, "erro": str(exc)})
    except CepIndisponivel as exc:
        return JsonResponse({"ok": False, "erro": str(exc)})
    return JsonResponse({"ok": True, "endereco": endereco})


@exige_operador
def geocodificar_endereco(request):
    """Endereço digitado → coordenada, para o pin do formulário.

    Chamado quando o operador termina de preencher o endereço, para que o mapa
    de conferência mostre o pin ANTES de salvar. A geocodificação definitiva
    continua acontecendo no save (services/cadastro.py); esta é a prévia.
    """
    from iscas.services.exceptions import GeocodificacaoFalhou
    from iscas.services.geo import geocodificar

    endereco = (request.GET.get("endereco") or "").strip()
    if not endereco:
        return JsonResponse({"ok": False, "erro": "Endereço vazio."})

    try:
        latitude, longitude = geocodificar(endereco)
    except GeocodificacaoFalhou as exc:
        return JsonResponse({"ok": False, "erro": str(exc)})

    return JsonResponse(
        {"ok": True, "latitude": float(latitude), "longitude": float(longitude)}
    )


def _serializar_unidades(unidades):
    """Formato que o TomSelect consome nos seletores de unidade."""
    return [
        {
            "id": unidade.pk,
            "identificador": unidade.identificador,
            "modelo": unidade.modelo.nome,
            "codigo": unidade.modelo.codigo,
            # O rótulo junta as duas informações: o operador busca tanto pelo
            # ID da isca quanto pelo modelo.
            "rotulo": f"{unidade.identificador} — {unidade.modelo.nome}",
        }
        for unidade in unidades
    ]


@exige_operador
def unidades_da_custodia(request):
    """Unidades disponíveis numa custódia, para o seletor de baixa/manutenção.

    "Disponíveis" exclui as que têm reserva ativa: unidade comprometida com uma
    solicitação não pode ser baixada nem mandada para manutenção sem antes
    cancelar a atribuição, e o service recusaria de qualquer forma. Oferecer no
    seletor só levaria o operador a um erro evitável.
    """
    from iscas.enums import TipoCustodia
    from iscas.models.cadastro import Deposito
    from iscas.models.custodia import Unidade
    from iscas.services.saldo import unidades_disponiveis

    tipo = request.GET.get("tipo")
    entidade_id = request.GET.get("id")

    # MANUTENCAO é conta singleton: não tem entidade, então não pede `id`.
    # Alimenta o seletor do retorno da manutenção.
    if tipo == "MANUTENCAO":
        unidades = Unidade.objects.filter(
            custodia_atual__tipo=TipoCustodia.MANUTENCAO
        ).select_related("modelo").order_by("modelo__nome", "identificador")
        return JsonResponse({"unidades": _serializar_unidades(unidades)})

    if not entidade_id:
        return JsonResponse({"unidades": []})

    if tipo == "AGENTE":
        entidade = get_object_or_404(Agente.todos, pk=entidade_id)
    elif tipo == "DEPOSITO":
        entidade = get_object_or_404(Deposito.todos, pk=entidade_id)
    else:
        return JsonResponse(
            {"erro": "Informe tipo AGENTE, DEPOSITO ou MANUTENCAO."}, status=400
        )

    unidades = (
        unidades_disponiveis(entidade)
        .select_related("modelo")
        .order_by("modelo__nome", "identificador")
    )

    return JsonResponse({"unidades": _serializar_unidades(unidades)})


@exige_operador
def dados_do_cliente(request, cliente_id):
    """Dados cadastrais do cliente, para a abertura de solicitação preencher.

    A tela copia estes valores nos campos editáveis: o operador confere,
    ajusta o que for específico daquela entrega, e a solicitação guarda a
    própria versão sem tocar no cadastro.
    """
    cliente = get_object_or_404(Cliente.todos, pk=cliente_id)
    return JsonResponse(
        {
            "nome": cliente.nome_razao_social,
            "documento": cliente.documento,
            "tipo_documento": cliente.tipo_documento,
            "email": cliente.email,
            "contato_nome": cliente.contato_nome,
            "telefone": cliente.telefone,
            "comercial_responsavel": cliente.comercial_responsavel,
            "endereco": {
                "logradouro": cliente.logradouro,
                "numero": cliente.numero,
                "complemento": cliente.complemento,
                "bairro": cliente.bairro,
                "cidade": cliente.cidade,
                "uf": cliente.uf,
                "cep": cliente.cep,
            },
            "tem_coordenada": cliente.tem_coordenada,
        }
    )


@exige_operador
def saldo_agente(request, agente_id):
    """Saldo discriminado de um agente, para o popup do marcador."""
    agente = get_object_or_404(Agente.todos, pk=agente_id)
    return JsonResponse(
        {
            "agente": {"id": agente.pk, "nome": agente.nome, "telefone": agente.telefone},
            "saldos": [
                {
                    "modelo": linha["modelo__nome"],
                    "codigo": linha["modelo__codigo"],
                    "total": linha["total"],
                    "disponivel": linha["disponivel"],
                    "reservado": linha["reservado"],
                }
                for linha in saldo_por_modelo(agente)
            ],
        }
    )

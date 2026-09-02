"""Geolocalização: busca por proximidade e geocodificação (ISC-ADR-09/11).

A consulta central do sistema — "quem está perto e tem saldo?" — é resolvida em
SQL com pré-filtro por bounding box seguido de haversine, sem PostGIS. Um índice
B-tree em (latitude, longitude) descarta a maioria dos candidatos antes da
aritmética.
"""
import hashlib
import json
import math
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import DecimalField, ExpressionWrapper, F, Value
from django.db.models.functions import ACos, Cast, Cos, Greatest, Least, Radians, Sin
from django.utils import timezone

from iscas.enums import GeoOrigem
from iscas.models.config import GeocodeCache
from iscas.services.exceptions import GeocodificacaoFalhou

#: Raio médio da Terra, em km.
RAIO_TERRA_KM = 6371.0

#: Um grau de latitude em km — constante. Longitude depende do cosseno da
#: latitude, por isso entra no cálculo do delta.
KM_POR_GRAU_LAT = 111.045


def bounding_box(lat, lng, raio_km):
    """Caixa que contém o círculo de `raio_km` ao redor do ponto.

    Conservadora por construção: pode incluir candidato fora do raio (o
    haversine descarta depois), nunca excluir um dentro dele. Falso negativo
    aqui seria estoque invisível.
    """
    lat = float(lat)
    lng = float(lng)
    delta_lat = raio_km / KM_POR_GRAU_LAT

    # Perto dos polos o cosseno tende a zero e o delta explodiria. O clamp
    # mantém a caixa finita; a 85° de latitude ela cobre a Terra inteira em
    # longitude, o que é conservador e correto.
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-6:
        delta_lng = 180.0
    else:
        delta_lng = min(raio_km / (KM_POR_GRAU_LAT * abs(cos_lat)), 180.0)

    return (
        lat - delta_lat,
        lat + delta_lat,
        lng - delta_lng,
        lng + delta_lng,
    )


def anotar_distancia(queryset, *, lat, lng):
    """Anota `distancia_km` (haversine) usando funções matemáticas do ORM.

    O `clamp` em [-1, 1] antes do `acos` não é preciosismo: para um ponto
    idêntico ao de origem, o erro de ponto flutuante produz argumento
    marginalmente acima de 1 e o `acos` estoura com domain error.
    """
    lat0 = math.radians(float(lat))
    lng0 = float(lng)

    lat_rad = Radians(Cast("latitude", DecimalField(max_digits=12, decimal_places=8)))
    delta_lng_rad = Radians(
        Cast("longitude", DecimalField(max_digits=12, decimal_places=8)) - Value(lng0)
    )

    coseno = (
        Value(math.cos(lat0)) * Cos(lat_rad) * Cos(delta_lng_rad)
        + Value(math.sin(lat0)) * Sin(lat_rad)
    )
    coseno_seguro = Least(Greatest(coseno, Value(-1.0)), Value(1.0))

    return queryset.annotate(
        distancia_km=ExpressionWrapper(
            Value(RAIO_TERRA_KM) * ACos(coseno_seguro),
            output_field=DecimalField(max_digits=10, decimal_places=3),
        )
    )


def agentes_proximos(*, latitude, longitude, raio_km, modelo=None, quantidade_minima=0):
    """Agentes ativos dentro do raio, do mais perto ao mais longe (ISC-RN-11).

    Args:
        modelo: filtra o saldo disponível por modelo (ISC-RF-18).
        quantidade_minima: descarta quem tem menos que isso disponível.

    Returns:
        Lista de dicts com agente, distancia_km e disponivel.

    Agente sem coordenada não aparece aqui (ISC-RN-12) — ele é listado à parte
    por `agentes_sem_coordenada()`, com alerta. Omitir em silêncio criaria
    estoque invisível.
    """
    from iscas.models.cadastro import Agente
    from iscas.services.saldo import saldo_disponivel

    lat_min, lat_max, lng_min, lng_max = bounding_box(latitude, longitude, raio_km)

    # Pré-filtro por caixa: descarta a maioria com o índice B-tree, sem
    # aritmética. Só o que sobra paga o custo do haversine.
    candidatos = Agente.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        latitude__gte=Decimal(str(lat_min)),
        latitude__lte=Decimal(str(lat_max)),
        longitude__gte=Decimal(str(lng_min)),
        longitude__lte=Decimal(str(lng_max)),
    )

    candidatos = anotar_distancia(candidatos, lat=latitude, lng=longitude).filter(
        distancia_km__lte=Decimal(str(raio_km))
    ).order_by("distancia_km")

    resultado = []
    for agente in candidatos:
        disponivel = saldo_disponivel(agente, modelo=modelo)
        if disponivel < quantidade_minima:
            continue
        resultado.append(
            {
                "agente": agente,
                "distancia_km": float(agente.distancia_km),
                "disponivel": disponivel,
            }
        )
    return resultado


def agentes_para_solicitacao(*, solicitacao, raio_km):
    """Agentes próximos que servem para ESTA solicitação (ISC-RF-17, ISC-RF-18).

    A solicitação já sabe o cliente (logo, o ponto de origem) e os modelos que
    faltam. Pedir esses três dados de novo ao operador — cliente, modelo e
    quantidade mínima — é redigitar o que o sistema tem, e é onde nascem as
    buscas incoerentes: cliente de uma solicitação, modelo de outra.

    O que cada agente contribui é medido POR MODELO EM FALTA, não pelo saldo
    total: um agente com 50 unidades de um modelo que a solicitação não pede
    não serve, e apareceria no topo se a conta fosse saldo bruto.

    Returns:
        Lista de dicts, do mais perto ao mais longe, cada um com:
        `agente`, `distancia_km`, `disponivel` (soma do que ele cobre desta
        solicitação), `cobre_tudo` e `por_modelo` — o detalhe que a tela mostra.

    Agente sem NADA do que falta fica de fora: é o mesmo critério do select de
    atribuição (`selectors.agentes_que_atendem`), para a busca não oferecer
    quem a tela seguinte vai recusar.

    A distância é medida do PONTO DE ENTREGA (`coordenada_de_busca`), não da
    sede do cliente: a isca vai para onde a solicitação manda, e uma entrega em
    obra pode estar a dezenas de quilômetros do endereço cadastrado. O cadastro
    do cliente entra só como fallback, para pedidos antigos.

    Precondição: a solicitação tem coordenada de busca. Sem ela não há de onde
    medir distância — quem chama checa antes e explica ao operador, em vez de
    devolver "nenhum agente próximo", que mentiria sobre a causa.
    """
    from iscas.selectors import modelos_em_falta
    from iscas.services.saldo import saldo_disponivel

    origem = solicitacao.coordenada_de_busca
    if origem is None:
        return []

    faltas = modelos_em_falta(solicitacao)
    if not faltas:
        return []

    latitude, longitude = origem
    candidatos = agentes_proximos(
        latitude=latitude,
        longitude=longitude,
        raio_km=raio_km,
    )

    resultado = []
    for item in candidatos:
        agente = item["agente"]
        por_modelo = []
        total = 0
        modelos_cobertos = 0

        for modelo, falta in faltas:
            disponivel = saldo_disponivel(agente, modelo=modelo)
            # O agente cobre no máximo o que falta — saldo além disso não
            # entra na conta nem na ordenação.
            cobre = min(disponivel, falta)
            total += cobre
            if cobre >= falta:
                modelos_cobertos += 1
            por_modelo.append(
                {
                    "modelo": modelo.nome,
                    "codigo": modelo.codigo,
                    "falta": falta,
                    "disponivel": disponivel,
                    "cobre": cobre,
                }
            )

        if total == 0:
            continue

        resultado.append(
            {
                **item,
                "disponivel": total,
                "cobre_tudo": modelos_cobertos == len(faltas),
                "por_modelo": por_modelo,
            }
        )
    return resultado


def agentes_sem_coordenada():
    """Agentes ativos fora da busca por proximidade (ISC-RN-12, ISC-RF-21)."""
    from iscas.models.cadastro import Agente

    return Agente.objects.filter(latitude__isnull=True) | Agente.objects.filter(
        longitude__isnull=True
    )


# ---------------------------------------------------------------------------
# Geocodificação (ISC-ADR-11)
# ---------------------------------------------------------------------------


def _normalizar(endereco: str) -> str:
    return " ".join((endereco or "").split()).lower()


def _hash_endereco(endereco: str) -> str:
    return hashlib.sha256(_normalizar(endereco).encode()).hexdigest()


def geocodificar(endereco: str, *, usar_cache=True):
    """Converte endereço em (latitude, longitude) via Nominatim/OSM.

    Síncrono, com timeout curto. Falha NUNCA bloqueia o salvamento do cadastro
    (ISC-RF-02): quem chama trata `GeocodificacaoFalhou` e grava com
    `geo_origem=PENDENTE`, para reprocessar depois pelo command
    `geocodificar_pendentes`.

    Returns:
        `(Decimal latitude, Decimal longitude)`.
    """
    if not (endereco or "").strip():
        raise GeocodificacaoFalhou("Endereço vazio.")

    chave = _hash_endereco(endereco)

    if usar_cache:
        cacheado = GeocodeCache.objects.filter(endereco_hash=chave).first()
        if cacheado:
            return cacheado.latitude, cacheado.longitude

    url = getattr(
        settings, "ISCAS_NOMINATIM_URL", "https://nominatim.openstreetmap.org/search"
    )
    params = urllib.parse.urlencode(
        {"q": endereco, "format": "json", "limit": 1, "countrycodes": "br"}
    )
    requisicao = urllib.request.Request(
        f"{url}?{params}",
        headers={
            # Obrigatório pela política de uso do Nominatim.
            "User-Agent": getattr(
                settings, "ISCAS_NOMINATIM_USER_AGENT", "GSInt-IscasFast/1.0"
            )
        },
    )
    timeout = getattr(settings, "ISCAS_GEOCODE_TIMEOUT", 3)

    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            dados = json.loads(resposta.read().decode())
    except Exception as exc:  # rede, timeout, JSON inválido — tudo degrada igual
        raise GeocodificacaoFalhou(
            f"Não foi possível geocodificar o endereço: {exc}"
        ) from exc

    if not dados:
        raise GeocodificacaoFalhou("Endereço não encontrado pelo provedor.")

    try:
        latitude = Decimal(str(dados[0]["lat"])).quantize(Decimal("0.000001"))
        longitude = Decimal(str(dados[0]["lon"])).quantize(Decimal("0.000001"))
    except (KeyError, IndexError, TypeError) as exc:
        raise GeocodificacaoFalhou("Resposta do provedor em formato inesperado.") from exc

    GeocodeCache.objects.update_or_create(
        endereco_hash=chave,
        defaults={
            "endereco_normalizado": _normalizar(endereco)[:300],
            "latitude": latitude,
            "longitude": longitude,
            "provedor": "nominatim",
        },
    )
    return latitude, longitude


#: O Nominatim devolve o estado por extenso em `state`; o campo UF do cadastro
#: guarda a sigla. `ISO3166-2-lvl4` ("BR-SP") é a fonte preferida por ser
#: estável, mas nem toda resposta a traz — daí o mapa de nomes como fallback.
_UF_POR_NOME = {
    "acre": "AC", "alagoas": "AL", "amapá": "AP", "amazonas": "AM",
    "bahia": "BA", "ceará": "CE", "distrito federal": "DF",
    "espírito santo": "ES", "goiás": "GO", "maranhão": "MA",
    "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG",
    "pará": "PA", "paraíba": "PB", "paraná": "PR", "pernambuco": "PE",
    "piauí": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondônia": "RO", "roraima": "RR",
    "santa catarina": "SC", "são paulo": "SP", "sergipe": "SE",
    "tocantins": "TO",
}


def _extrair_uf(endereco: dict) -> str:
    """Sigla da UF a partir do bloco `address` do Nominatim.

    Devolve string vazia quando não dá para determinar com segurança — o campo
    fica em branco e o operador escolhe, o que é melhor que preencher errado.
    """
    iso = str(endereco.get("ISO3166-2-lvl4") or "")
    if "-" in iso:
        sigla = iso.split("-")[-1].strip().upper()
        if len(sigla) == 2:
            return sigla

    nome = str(endereco.get("state") or "").strip().lower()
    return _UF_POR_NOME.get(nome, "")


def geocodificar_reverso(latitude, longitude):
    """Coordenada → endereço estruturado, via Nominatim `/reverse`.

    O caminho inverso do `geocodificar()`: o operador tem a coordenada — colada
    de um WhatsApp, de um rastreador, do Google Maps — e não o endereço. Sem
    isto, ele teria que abrir outro mapa para descobrir a rua e digitar à mão.

    Returns:
        dict com `logradouro`, `numero`, `bairro`, `cidade`, `uf`, `cep` e
        `endereco_completo` — as mesmas chaves que o `buscar_cep` devolve, para
        a tela preencher os campos do mesmo jeito nos dois casos. Campo que o
        provedor não conhece vem string vazia; o operador completa.

    Raises:
        GeocodificacaoFalhou: coordenada inválida, rede, timeout, ou ponto sem
            endereço conhecido (meio do oceano, área rural sem mapeamento).
    """
    coordenada = coordenada_valida(latitude, longitude)
    if coordenada is None:
        raise GeocodificacaoFalhou(
            "Coordenada inválida. Informe latitude e longitude em graus decimais."
        )
    lat, lng = coordenada

    url = getattr(
        settings, "ISCAS_NOMINATIM_REVERSE_URL",
        "https://nominatim.openstreetmap.org/reverse",
    )
    params = urllib.parse.urlencode(
        {
            "lat": str(lat),
            "lon": str(lng),
            "format": "json",
            # 18 = nível de endereço. Menos que isso devolve bairro ou cidade,
            # que não serve para preencher logradouro e número.
            "zoom": 18,
            "addressdetails": 1,
            "accept-language": "pt-BR",
        }
    )
    requisicao = urllib.request.Request(
        f"{url}?{params}",
        headers={
            "User-Agent": getattr(
                settings, "ISCAS_NOMINATIM_USER_AGENT", "GSInt-IscasFast/1.0"
            )
        },
    )
    timeout = getattr(settings, "ISCAS_GEOCODE_TIMEOUT", 3)

    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            dados = json.loads(resposta.read().decode())
    except Exception as exc:  # rede, timeout, JSON inválido — degradam igual
        raise GeocodificacaoFalhou(
            f"Não foi possível buscar o endereço da coordenada: {exc}"
        ) from exc

    if not dados or dados.get("error"):
        raise GeocodificacaoFalhou(
            "Nenhum endereço conhecido nesta coordenada."
        )

    endereco = dados.get("address") or {}

    # O Nominatim varia a chave do logradouro conforme o tipo de via, e a da
    # cidade conforme o porte do município — em cidade pequena vem só `town`
    # ou `village`, e ler apenas `city` devolveria vazio.
    def _primeiro(*chaves):
        for chave in chaves:
            valor = endereco.get(chave)
            if valor:
                return str(valor)
        return ""

    uf = _extrair_uf(endereco)

    return {
        "logradouro": _primeiro("road", "pedestrian", "footway", "residential"),
        "numero": _primeiro("house_number"),
        "bairro": _primeiro("suburb", "neighbourhood", "city_district", "quarter"),
        "cidade": _primeiro("city", "town", "village", "municipality"),
        "uf": uf,
        "cep": _primeiro("postcode"),
        "endereco_completo": dados.get("display_name") or "",
        "latitude": lat,
        "longitude": lng,
    }


def geocodificar_entidade(entidade, *, forcar=False, salvar=True):
    """Geocodifica um Agente/Cliente/Depósito, respeitando o pin manual.

    Ajuste manual do operador vence a geocodificação automática enquanto o
    endereço não mudar (ISC-RF-03) — o operador corrigiu porque o provedor
    errou; sobrescrever seria desfazer a correção a cada save.

    Returns:
        True se gravou coordenada nova.
    """
    if entidade.geo_origem == GeoOrigem.MANUAL and not forcar:
        return False

    try:
        # Endereço enxuto, sem CEP nem complemento: o Nominatim volta VAZIO
        # quando eles entram na consulta. Ver `endereco_para_geocodificacao`.
        latitude, longitude = geocodificar(entidade.endereco_para_geocodificacao)
    except GeocodificacaoFalhou:
        # Degradação graciosa: o cadastro fica pendente, sinalizado na UI.
        if entidade.geo_origem != GeoOrigem.MANUAL:
            entidade.geo_origem = GeoOrigem.PENDENTE
            if salvar and entidade.pk:
                entidade.save(update_fields=["geo_origem", "updated_at"])
        return False

    entidade.latitude = latitude
    entidade.longitude = longitude
    entidade.geo_origem = GeoOrigem.GEOCODIFICADO
    entidade.geocodificado_em = timezone.now()
    if salvar and entidade.pk:
        entidade.save(
            update_fields=[
                "latitude",
                "longitude",
                "geo_origem",
                "geocodificado_em",
                "updated_at",
            ]
        )
    return True


def coordenada_valida(latitude, longitude):
    """Converte para Decimal, ou devolve None se não for coordenada.

    Campo vazio, texto e valor fora do intervalo geográfico caem aqui. Sem esta
    guarda, `Decimal("")` levanta `InvalidOperation` e o formulário quebra com
    erro 500 — o que acontecia quando o agente ainda não tinha pin e o mapa não
    chegava a preencher os campos ocultos.
    """
    if latitude in (None, "") or longitude in (None, ""):
        return None
    try:
        lat = Decimal(str(latitude).strip()).quantize(Decimal("0.000001"))
        lng = Decimal(str(longitude).strip()).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not (Decimal("-90") <= lat <= Decimal("90")):
        return None
    if not (Decimal("-180") <= lng <= Decimal("180")):
        return None
    return lat, lng


def ajustar_pin(entidade, *, latitude, longitude, salvar=True):
    """Grava a posição arrastada à mão pelo operador (ISC-RF-03).

    Raises:
        ValueError: coordenada ausente ou inválida. Quem chama trata e mostra
            mensagem ao operador — nunca deixa virar erro 500.
    """
    coordenada = coordenada_valida(latitude, longitude)
    if coordenada is None:
        raise ValueError(
            "Coordenada inválida. Posicione o pin no mapa antes de salvar."
        )
    entidade.latitude, entidade.longitude = coordenada
    entidade.geo_origem = GeoOrigem.MANUAL
    entidade.geocodificado_em = timezone.now()
    if salvar:
        entidade.save(
            update_fields=[
                "latitude",
                "longitude",
                "geo_origem",
                "geocodificado_em",
                "updated_at",
            ]
        )
    return entidade

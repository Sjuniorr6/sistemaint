"""Montagem do texto de WhatsApp para o agente (ISC-RF-29).

O sistema NÃO envia nada: monta o texto e o link `wa.me` para o operador copiar
(não-objetivo explícito do PRD — nenhuma integração de API de WhatsApp). A
comunicação com o agente acontece fora do sistema.
"""
import re
import urllib.parse

_NAO_DIGITO = re.compile(r"\D")


def telefone_para_wa(telefone: str) -> str:
    """Normaliza o telefone para o formato que o `wa.me` espera.

    Acrescenta o DDI 55 quando o número vem só com DDD + assinante, que é como
    o operador cadastra no dia a dia.
    """
    numeros = _NAO_DIGITO.sub("", telefone or "")
    if not numeros:
        return ""
    if len(numeros) in (10, 11):  # DDD + 8 ou 9 dígitos
        numeros = f"55{numeros}"
    return numeros


def montar_texto_atribuicao(atribuicao) -> str:
    """Texto pronto com cliente, endereço, contato, modelo e quantidade."""
    solicitacao = atribuicao.solicitacao
    cliente = solicitacao.cliente

    linhas = [
        f"Olá, {atribuicao.agente.nome}!",
        "",
        "Entrega de iscas:",
        f"Cliente: {cliente.nome_razao_social}",
        # Endereço DA SOLICITAÇÃO, não do cadastro: a entrega pode ser numa
        # obra ou filial, e é para lá que o agente precisa ir.
        f"Endereço: {solicitacao.endereco_entrega}",
    ]

    contato_nome = solicitacao.contato_nome or cliente.contato_nome
    telefone = solicitacao.telefone or cliente.telefone
    if contato_nome or telefone:
        contato = " / ".join(p for p in (contato_nome, telefone) if p)
        linhas.append(f"Contato: {contato}")

    linhas.append("")

    # Agrupa as unidades reservadas por modelo — o agente precisa saber o quê e
    # quanto, não a lista de identificadores.
    from iscas.services.reserva import unidades_reservadas

    contagem = {}
    for unidade in unidades_reservadas(atribuicao):
        contagem[unidade.modelo.nome] = contagem.get(unidade.modelo.nome, 0) + 1

    if contagem:
        linhas.append("Equipamentos:")
        for nome, quantidade in sorted(contagem.items()):
            linhas.append(f"- {quantidade}x {nome}")
    else:
        # Já entregue: as reservas foram liberadas, então lemos do log.
        for linha in atribuicao.movimentacoes.filter(
            atribuicao=atribuicao
        ).prefetch_related("linhas__unidade__modelo"):
            for item in linha.linhas.all():
                nome = item.unidade.modelo.nome
                contagem[nome] = contagem.get(nome, 0) + 1
        if contagem:
            linhas.append("Equipamentos:")
            for nome, quantidade in sorted(contagem.items()):
                linhas.append(f"- {quantidade}x {nome}")

    if solicitacao.observacao:
        linhas.extend(["", f"Observação: {solicitacao.observacao}"])

    if solicitacao.prazo_desejado:
        linhas.append(f"Prazo desejado: {solicitacao.prazo_desejado.strftime('%d/%m/%Y')}")

    linhas.extend(["", "Assim que entregar, me avise para dar baixa. Obrigado!"])
    return "\n".join(linhas)


def link_whatsapp(atribuicao) -> str:
    """Link `wa.me` com o texto pré-preenchido (ISC-RF-29)."""
    numero = telefone_para_wa(atribuicao.agente.telefone)
    texto = urllib.parse.quote(montar_texto_atribuicao(atribuicao))
    if not numero:
        return f"https://wa.me/?text={texto}"
    return f"https://wa.me/{numero}?text={texto}"

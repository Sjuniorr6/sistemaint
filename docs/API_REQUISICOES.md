# API de Requisições — GSInt

Endpoint somente-leitura com as requisições geradas pelo sistema: cliente, data,
quantidade e IDs dos equipamentos.

- **URL base:** `https://intgoldensat.com.br`
- **Endpoint:** `GET /requisicao/api/requisicoes/ids/`
- **Formato:** JSON (UTF-8)

---

## 1. Autenticação

Toda requisição precisa do header `Authorization` com o token fornecido:

```
Authorization: Token SEU_TOKEN_AQUI
```

Sem o header, ou com token inválido, a resposta é **401**. O token não expira —
ele vale até ser revogado.

> O token identifica quem está consumindo. Não compartilhe com terceiros e não
> publique em repositório, front-end ou print de tela. Se vazar, avise para
> revogarmos e emitirmos outro.

---

## 2. Parâmetros

Todos são opcionais e combináveis na querystring.

| Parâmetro | Formato | Descrição |
|---|---|---|
| `cliente` | texto | Filtra pelo nome do cliente. Busca parcial, ignora maiúsculas/minúsculas. |
| `contrato` | `Retornavel` \| `Descartavel` | Filtra pelo tipo de isca. Ignora maiúsculas/minúsculas. Sem acento. |
| `data_inicio` | `AAAA-MM-DD` | Só requisições criadas a partir desta data (inclusive). |
| `data_fim` | `AAAA-MM-DD` | Só requisições criadas até esta data (inclusive). |
| `page` | inteiro | Página desejada. Padrão `1`. |
| `page_size` | inteiro | Itens por página. Padrão `100`, máximo `500`. |

Data em formato inválido é ignorada (o filtro simplesmente não é aplicado), não
gera erro.

---

## 3. Resposta

```json
{
  "total": 1523,
  "page": 1,
  "num_pages": 16,
  "requisicoes": [
    {
      "id": 4821,
      "cliente": "ACME LOGISTICA LTDA",
      "data": "2026-08-26T14:30:05.123456-03:00",
      "quantidade": 3,
      "contrato": "Retornavel",
      "ids": ["ID-001", "ID-002", "ID-003"]
    }
  ]
}
```

### Campos

| Campo | Tipo | Descrição |
|---|---|---|
| `total` | inteiro | Total de requisições que atendem ao filtro — **do conjunto inteiro, não da página**. |
| `page` | inteiro | Página atual. |
| `num_pages` | inteiro | Total de páginas disponíveis. |
| `requisicoes[].id` | inteiro | Número da requisição no sistema. |
| `requisicoes[].cliente` | texto | Nome do cliente. String vazia se não houver. |
| `requisicoes[].data` | texto ISO-8601 | Data/hora de criação, fuso `America/Sao_Paulo` (`-03:00`). |
| `requisicoes[].quantidade` | inteiro | Quantidade de equipamentos **solicitada**. |
| `requisicoes[].contrato` | texto | Tipo de isca: `Retornavel` ou `Descartavel`. String vazia quando não preenchida. |
| `requisicoes[].ids` | lista de texto | IDs dos equipamentos vinculados. Lista vazia se ainda não configurada. |

### Dois pontos que evitam interpretação errada

**`quantidade` é o que foi pedido; `ids` é o que já foi vinculado.** Os dois
divergem enquanto a requisição não passa pela configuração — é normal ver
`quantidade: 3` com `ids: []`. Para saber o que de fato saiu, use `len(ids)`,
não `quantidade`.

**`total` é do filtro inteiro, não da página.** Para paginar até o fim, itere
enquanto `page < num_pages` — não compare com o tamanho de `requisicoes`.

**`contrato` pode vir vazio.** Os valores são `Retornavel` e `Descartavel`
(sem acento, como estão gravados), mas uma minoria de requisições antigas
está com o campo em branco — hoje 15 de 3112. Trate `""` como "não
informado", não presuma um dos dois.

---

## 4. Códigos de status

| Código | Significado | O que fazer |
|---|---|---|
| `200` | Sucesso. | — |
| `401` | Token ausente, malformado ou inválido. | Confira o header `Authorization`. |
| `403` | Token válido, mas sem permissão. | Fale com a equipe de Inteligência. |
| `404` | URL errada. | Confira a barra final: `/ids/`. |
| `500` | Erro no servidor. | Tente de novo; se persistir, nos avise. |

Uma página além da última **não** dá erro: devolve `200` com a última página
disponível.

---

## 5. Exemplos

### cURL

```bash
curl -H "Authorization: Token SEU_TOKEN_AQUI" \
  "https://intgoldensat.com.br/requisicao/api/requisicoes/ids/?cliente=acme&data_inicio=2026-08-01"
```

### Python

```python
import requests

BASE = "https://intgoldensat.com.br/requisicao/api/requisicoes/ids/"
HEADERS = {"Authorization": "Token SEU_TOKEN_AQUI"}


def buscar_todas(**filtros):
    """Percorre todas as páginas e devolve a lista completa de requisições."""
    pagina, resultado = 1, []
    while True:
        resposta = requests.get(
            BASE,
            headers=HEADERS,
            params={**filtros, "page": pagina, "page_size": 500},
            timeout=30,
        )
        resposta.raise_for_status()
        corpo = resposta.json()
        resultado.extend(corpo["requisicoes"])
        if pagina >= corpo["num_pages"]:
            return resultado
        pagina += 1


for req in buscar_todas(data_inicio="2026-08-01"):
    print(req["id"], req["cliente"], req["quantidade"], len(req["ids"]))
```

### JavaScript

```javascript
const BASE = "https://intgoldensat.com.br/requisicao/api/requisicoes/ids/";

async function buscarTodas(filtros = {}) {
  const resultado = [];
  let pagina = 1;
  while (true) {
    const params = new URLSearchParams({ ...filtros, page: pagina, page_size: 500 });
    const resposta = await fetch(`${BASE}?${params}`, {
      headers: { Authorization: "Token SEU_TOKEN_AQUI" },
    });
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    const corpo = await resposta.json();
    resultado.push(...corpo.requisicoes);
    if (pagina >= corpo.num_pages) return resultado;
    pagina += 1;
  }
}
```

---

## 6. Boas práticas de consumo

- **Use `page_size=500`** em cargas grandes: menos requisições, menos carga no servidor.
- **Puxe por janela de data** em vez de varrer a base toda. Uma sincronização
  diária com `data_inicio` de ontem é muito mais barata que baixar tudo.
- **Não faça polling agressivo.** Requisições não mudam de segundo em segundo;
  de hora em hora já é bastante para a maioria dos casos.
- **Trate `ids` vazio como estado normal**, não como erro.

---

## 7. Suporte

Dúvidas, token novo ou revogação: **inteligencia@grupogoldensat.com.br**

# Emitir token de API — guia interno

Como gerar, entregar e revogar tokens de acesso à API do GSInt.
**Documento interno.** O que vai para quem consome é `API_REQUISICOES.md`.

---

## Regra que vale para tudo

**Um usuário dedicado por consumidor — nunca o token de uma pessoa.**

O projeto já segue esse padrão: existe o usuário `gsacionamento_api`, criado só
para integração. Reaproveitar o token de um usuário humano tem três problemas
concretos:

- **Revogar vira ou-tudo-ou-nada:** cortar o acesso do integrador derruba o login
  da pessoa junto.
- **Some a rastreabilidade:** o log não distingue o que foi ação da pessoa e o
  que foi o sistema dela.
- **Herda permissão demais:** um token de superusuário dá muito mais acesso do
  que ler requisições.

Cada consumidor (empresa, sistema, integração) ganha o seu.

---

## Passo 1 — criar o usuário da integração

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string

usuario = User.objects.create_user(
    username="acme_api",                 # <consumidor>_api
    email="ti@acme.com.br",              # contato técnico de quem consome
    password=get_random_string(50),      # senha aleatória, ninguém usa
)
usuario.is_staff = False       # não acessa o admin
usuario.is_superuser = False   # nunca superusuário
usuario.save()
print("usuário criado:", usuario.username)
```

A senha é descartável de propósito: esse usuário **não faz login em tela**,
só existe para carregar o token. Não anote e não envie a senha.

---

## Passo 2 — gerar o token

```python
from rest_framework.authtoken.models import Token

token, criado = Token.objects.get_or_create(user=usuario)
print("TOKEN:", token.key)
print("novo?", criado)   # False = já existia, nenhum token novo foi criado
```

Copie o valor de `TOKEN` — é ele que vai para quem consome.

> `get_or_create` não regenera token existente. Se `criado` vier `False` e você
> precisa mesmo de um novo, veja *Rotacionar* abaixo.

### Alternativa: pelo Django Admin

Em `/admin/authtoken/tokenproxy/` → **Add token** → escolher o usuário → salvar.
A chave aparece na listagem. Serve para um token avulso; o shell é melhor quando
você quer criar usuário e token de uma vez.

---

## Passo 3 — entregar o token

O token é credencial. Ele dá acesso aos dados de requisições de todos os
clientes, e não expira sozinho.

**Não envie por:** e-mail, WhatsApp, Slack, Teams, card de tarefa, planilha
compartilhada ou print. Todos esses guardam histórico que você não controla e
não conseguirá apagar depois.

**Envie por um destes:**

| Meio | Como |
|---|---|
| Cofre de senha | 1Password, Bitwarden, KeePass — item compartilhado com o contato técnico. |
| Link autodestrutivo | `onetimesecret.com` ou similar: o link expira após a primeira abertura. |
| Canal separado | Combine por um canal e mande por outro (avisa no chat, entrega por ligação). |

**O que acompanha a entrega:**

1. O token.
2. O arquivo `API_REQUISICOES.md` (esse pode ir por e-mail à vontade — não tem segredo).
3. Uma linha pedindo confirmação de recebimento, para você saber que chegou e que
   o link autodestrutivo foi consumido por quem devia.

Modelo curto:

> Olá, segue o acesso à API de requisições do GSInt.
> O token está no link abaixo, que expira na primeira abertura: <link>
> A documentação de consumo está em anexo.
> Pode confirmar quando tiver recebido? Qualquer dúvida, é só chamar.

---

## Passo 4 — anotar quem recebeu

Sem registro, daqui a seis meses ninguém sabe de quem é o token `a3f9...`.
Mantenha uma linha por token (planilha interna ou este arquivo):

| Usuário | Consumidor | Contato técnico | Emitido em | Status |
|---|---|---|---|---|
| `gsacionamento_api` | GS Acionamento | — | 18/02/2026 | ativo |
| `acme_api` | ACME Logística | ti@acme.com.br | — | ativo |

Anote o **usuário**, não o token. Se precisar do valor, ele está no banco.

---

## Revogar

Quando o contrato encerra, o token vaza, ou a integração sai do ar:

```python
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

Token.objects.filter(user__username="acme_api").delete()
```

O acesso corta na hora — a próxima chamada recebe `401`.

Se o consumidor não volta mais, desative o usuário também:

```python
User.objects.filter(username="acme_api").update(is_active=False)
```

Desativar o usuário **sem** apagar o token já basta para bloquear: o DRF recusa
token de usuário inativo. Mas apagar o token deixa a intenção explícita.

---

## Rotacionar

Troca de token sem trocar de usuário — use quando houver suspeita de vazamento:

```python
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

Token.objects.filter(user__username="acme_api").delete()
novo = Token.objects.create(user=User.objects.get(username="acme_api"))
print("NOVO TOKEN:", novo.key)
```

**Isso derruba a integração no instante em que roda.** Combine a janela com o
contato técnico antes, ou faça fora do horário de uso.

---

## Conferir o que está ativo

```python
from rest_framework.authtoken.models import Token

for t in Token.objects.select_related("user"):
    print(t.user.username, "| ativo:", t.user.is_active, "| criado:", t.created)
```

Vale rodar de tempos em tempos: token de integração que acabou e ninguém
revogou é acesso aberto sem dono.

---

## Onde isso é validado no código

- Autenticação por token: `REST_FRAMEWORK` em [`app/settings.py`](../app/settings.py#L140)
- View protegida: `api_requisicoes_ids` em [`requisicao/views.py`](../requisicao/views.py#L2890)
- Teste que garante a exigência de auth: `test_exige_autenticacao` em
  [`requisicao/tests/test_api_requisicoes_ids.py`](../requisicao/tests/test_api_requisicoes_ids.py)

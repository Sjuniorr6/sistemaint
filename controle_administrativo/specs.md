# SPEC — Atualização de Usuário e Board

## 1. Contexto

Realizar a atualização dos dados anteriormente vinculados à usuária **Laysa**, substituindo as informações pelo novo cadastro da usuária **Ellen Costa**.

A alteração deve garantir que os dados de acesso, identificação visual na board, permissões e vínculos internos sejam atualizados corretamente, evitando que permaneçam referências antigas à usuária Laysa.

---

## 2. Objetivo

Atualizar o usuário atualmente associado à Laysa para que passe a representar a usuária Ellen Costa, mantendo os acessos e vínculos necessários para continuidade da operação no sistema.

---

## 3. Escopo da Alteração

### 3.1 Atualização de acesso

* Alterar o login anteriormente vinculado à Laysa para o novo login da Ellen Costa.
* Alterar ou redefinir a senha de acesso conforme padrão definido pelo sistema.
* Garantir que a Ellen Costa consiga realizar login normalmente após a alteração.

### 3.2 Atualização de identificação do usuário

* Substituir o nome da Laysa pelo nome da Ellen Costa.
* Atualizar informações visíveis relacionadas ao usuário, como nome completo, usuário/login, exibição em telas e demais campos de identificação.

### 3.3 Atualização da board

* Atualizar a board para que todas as informações anteriormente exibidas em nome da Laysa passem a ser exibidas em nome da Ellen Costa.
* Garantir que cards, tarefas, registros ou vínculos relacionados à usuária sejam apresentados corretamente com o novo nome.

### 3.4 Permissões e vínculos

* Garantir que os acessos e permissões da usuária sejam mantidos ou ajustados conforme a necessidade operacional.
* Validar se os vínculos existentes continuam funcionando após a troca de nome e credenciais.
* Evitar perda de histórico, registros ou associações já existentes no sistema.

---

## 4. Regras de Negócio

* A substituição deve preservar os registros históricos vinculados ao usuário anterior, apenas atualizando a identificação exibida.
* A usuária Ellen Costa deve herdar os acessos necessários para executar as mesmas atividades atribuídas anteriormente à Laysa, salvo orientação contrária.
* A board não deve exibir mais o nome da Laysa após a atualização.
* Não deve haver duplicidade de usuário para a mesma função, caso a substituição seja feita no cadastro existente.
* A alteração não deve impactar outros usuários, permissões ou informações da board.

---

## 5. Critérios de Aceite

* O login anteriormente associado à Laysa deve ser atualizado para Ellen Costa.
* A senha deve ser alterada ou redefinida corretamente.
* O nome Ellen Costa deve aparecer no lugar de Laysa nas telas do sistema.
* A board deve exibir Ellen Costa nos registros, cards ou informações anteriormente associados à Laysa.
* A usuária deve conseguir acessar o sistema normalmente.
* As permissões e vínculos devem permanecer funcionais após a alteração.
* Não devem permanecer referências visíveis à Laysa na board ou nos dados principais do usuário.
* A alteração não deve gerar erro em telas, filtros, listagens ou vínculos existentes.

---

## 6. Validações Necessárias

* Testar login com o novo acesso da Ellen Costa.
* Verificar se a board passou a exibir o novo nome corretamente.
* Validar se as permissões da usuária permanecem corretas.
* Conferir se registros vinculados anteriormente à Laysa continuam acessíveis.
* Garantir que não houve impacto em outros usuários ou boards.
* Verificar se não existem referências antigas à Laysa em telas principais do sistema.

---

## 7. Resultado Esperado

Ao final da alteração, a usuária **Ellen Costa** deve estar corretamente cadastrada ou atualizada no sistema, com login, senha, permissões e vínculos devidamente ajustados. A board deve exibir o nome Ellen Costa no lugar da antiga referência à Laysa, mantendo a continuidade dos registros e acessos necessários.

## 8. Senha Padrão e Alteração no Primeiro Acesso

Deve ser criada uma senha padrão temporária para a usuária **Ellen Costa**, permitindo que ela realize o primeiro acesso ao sistema.

Após o login inicial, o sistema deve obrigar a usuária a alterar essa senha padrão antes de acessar as demais funcionalidades.

### Regras

- Definir uma senha padrão temporária para a Ellen Costa.
- No primeiro acesso, obrigar a alteração da senha.
- Bloquear o acesso às demais telas até que a nova senha seja cadastrada.
- A nova senha deve seguir os critérios de segurança definidos pelo sistema.
- Após a alteração, a senha padrão não deve mais ser válida.
- O sistema deve registrar que a troca de senha inicial foi concluída.

### Critérios de Aceite

- A Ellen Costa deve conseguir acessar o sistema com a senha padrão temporária.
- Após o primeiro login, deve ser redirecionada para a tela de alteração de senha.
- O acesso ao sistema só deve ser liberado após a definição da nova senha.
- A senha padrão não deve funcionar novamente após a alteração.
- A alteração não deve impactar os acessos, permissões e vínculos já definidos para a usuária.

---

## 9. Implementação (registro)

A Ellen **substitui a Laysa no cadastro existente** (o MESMO `User` + `FuncionarioAdministrativo`): apenas o nome/login mudam. Por ser o mesmo registro, **todas as permissões, grupos, roles e acessos ao sistema int da Laysa são mantidos** — não há criação de usuário novo, não há perda de histórico nem de vínculos. Só troca o nome e define a senha provisória.

**Decisões acordadas:**

- Ellen = Laysa renomeada. Login: `Ellen.Costa` · Senha provisória: `ggs@2026` (trocada obrigatoriamente no 1º acesso). Mesmas permissões/acessos.
- "Trocar o nome em todos os locais": o nome da Laysa só aparece via dados (`User` e `FuncionarioAdministrativo.nome`) — não há "Laysa" fixo em código/templates —, então renomear esses registros atualiza a exibição em todas as telas e no rodapé do painel.
- Bloqueio de 1º acesso restrito ao **painel administrativo** (`controle_administrativo`).

**Rodapé do painel (cards por operador):**

- **Ellen** aparece automaticamente ao renomear a Laysa (o card dela é o card da Laysa).
- **André Simão já tem acesso ao sistema** — não é usuário novo. Ele só precisa ser vinculado ao rodapé como operador, **sem alterar senha nem permissões** (`vincular_operador`).

**Como aplicar (rodar na base de produção):**

```bash
python manage.py substituir_usuario --dry-run     # pré-visualiza (Laysa -> Ellen Costa)
python manage.py substituir_usuario               # renomeia Laysa mantendo acessos + senha provisória

python manage.py vincular_operador --dry-run      # pré-visualiza (André Simão)
python manage.py vincular_operador                # vincula o André existente ao rodapé (senha/permissões intactas)
```

Ambos são idempotentes e seguros. `substituir_usuario` aceita `--de`, `--login`, `--nome`, `--senha`; `vincular_operador` aceita `--login`, `--nome`.

**Artefatos:**

- `FuncionarioAdministrativo.senha_provisoria` / `senha_alterada_em` (migration `0012`) — flag de 1º acesso e registro da conclusão da troca.
- View/URL `controle_administrativo:trocar_senha` + template `trocar_senha.html` — troca obrigatória (usa os validadores de `AUTH_PASSWORD_VALIDATORS`).
- Guarda em `painel`/`historico`: enquanto `senha_provisoria=True`, redireciona para a troca de senha; a senha provisória deixa de valer após a alteração.
- Comando `substituir_usuario` — renomeia Laysa→Ellen mantendo todos os acessos (mesmo `User`) e define a senha provisória `ggs@2026`.
- Comando `vincular_operador` — vincula um usuário **já existente** (ex.: André Simão) ao rodapé como operador, **sem criar conta, sem mexer em senha/permissões**.
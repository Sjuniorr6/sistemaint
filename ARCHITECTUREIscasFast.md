# ARCHITECTURE — App Iscas Fast (GSInt)

> Requisitos de produto (o **que** o sistema faz) estão em `PRD.md`. Este documento foca em **como** — stack, modelo de dados, padrões de código e decisões arquiteturais (ADRs). Cross-references `ISC-RN` / `ISC-RF` apontam para o PRD.

## Visão Arquitetural

O **Iscas Fast** é um **app Django** dentro do monólito **GSInt** — não um serviço novo, não um deploy novo. Reaproveita os padrões da casa: **camada de Services obrigatória** (thin views, fat services), `BaseModel` compartilhado com UUID e soft-delete, `ActiveManager`, e SSR com Django Templates + HTMX + Alpine.js. Mesmo padrão do app Chamados.

O coração do app é um **livro-razão append-only de custódia**. Toda mudança de posse de equipamento é um lançamento com **conta de origem** e **conta de destino** — exatamente a mecânica de partidas dobradas, aplicada a unidades físicas em vez de dinheiro. Nenhum saldo é campo editável: o saldo de qualquer custódia, a qualquer momento, é uma função do livro (`ISC-RN-01`). Não existe caminho no código que transfira posse sem gerar lançamento (`ISC-RN-02`).

A segunda característica estrutural é a **identidade unitária**: cada isca é uma linha em `Unidade`, com identificador único. A interface opera em lote — o operador digita "8 unidades" — mas a alocação, a reserva e o lançamento são sempre unitários (`ISC-RN-03`). É o que torna possível responder "onde está a isca X" e rastrear retornáveis em posse de cliente.

A terceira é a **dimensão geográfica**. Agente e Cliente carregam latitude e longitude, e a consulta central do sistema ("quem está perto e tem saldo?") é resolvida em SQL com pré-filtro por bounding box seguido de haversine, sem PostGIS (`ISC-ADR-09`). O mapa Leaflet consome um endpoint JSON servido por `JsonResponse` — sem DRF, coerente com o padrão do GSInt.

Não há multi-tenancy nem isolamento por cliente: o app é interno e todo Operador GS enxerga todos os dados (`ISC-RN-19`). Agentes e clientes são entidades de domínio sem credencial (`ISC-RN-15`); não existe rota autenticável para eles.

## Stack Técnica

| Camada          | Tecnologia                           |
|-----------------|--------------------------------------|
| Linguagem       | Python 3.12                          |
| Framework       | Django 5.x (WSGI)                    |
| Banco           | PostgreSQL                           |
| Frontend        | Django Templates + HTMX + Alpine.js  |
| Mapa            | Leaflet + Leaflet.markercluster (vendorizados) |
| Tiles           | OpenStreetMap (provedor configurável) |
| Geocodificação  | Nominatim/OSM via HTTP, com cache local |
| Estáticos       | WhiteNoise                           |
| Testes          | pytest + pytest-django + factory-boy |
| Deploy          | Herdado do GSInt                     |

Sem Celery/Redis, sem DRF e sem object storage no MVP (`ISC-ADR-12`, `ISC-ADR-13`). A única chamada externa é a geocodificação, síncrona, com timeout curto e degradação graciosa. Exportação de CSV é `StreamingHttpResponse` síncrona.

## Estrutura de Módulos

App único (`iscas/`), organizado por responsabilidade:

- `iscas/models/`
    - `cadastro.py`   `Agente`, `Cliente`, `Deposito`, `ModeloEquipamento`
    - `custodia.py`   `Custodia`, `Unidade`, `Movimentacao`, `MovimentacaoUnidade`
    - `operacao.py`   `Solicitacao`, `ItemSolicitacao`, `Atribuicao`, `AtribuicaoUnidade`, `SolicitacaoEvento`
    - `config.py`     `ConfiguracaoIscas` (singleton), `GeocodeCache`
- `iscas/services/`
    - `custodia.py`      **`registrar_movimentacao()`** — ponto de escrita único do livro-razão
    - `entrada.py`       entrada avulsa e em lote, geração de identificador interno
    - `transferencia.py` transferência entre custódias, envio/retorno de manutenção
    - `baixa.py`         perda, avaria, obsolescência
    - `estorno.py`       contra-lançamento referenciando o original
    - `saldo.py`         saldo em custódia, disponível, reservado
    - `reserva.py`       **`alocar_unidades()`** — ponto único de reserva, com lock
    - `solicitacao.py`   máquina de estados de Solicitação e Atribuição
    - `retorno.py`       retorno de retornável
    - `geo.py`           `geocodificar()`, `agentes_proximos()`
    - `mensagem.py`      montagem do texto de WhatsApp
- `iscas/selectors.py`   consultas de leitura para views e endpoints JSON
- `iscas/views/`         views SSR por área + `api.py` (JSON do mapa)
- `iscas/forms/`
- `iscas/templates/iscas/`
- `iscas/static/iscas/`
- `iscas/management/commands/`  `geocodificar_pendentes`, `recomputar_custodias`, `seed_custodias`
- `iscas/tests/`

## Padrões Transversais

### BaseModel

Cadastros herdam de `core.BaseModel` do GSInt: `id` UUID (PK), `created_at`, `updated_at`, `is_active`.

`Movimentacao`, `MovimentacaoUnidade` e `SolicitacaoEvento` **não** herdam `is_active`: são registros de log, imutáveis, sem soft-delete (`ISC-RN-17`, `ISC-ADR-15`). Herdam um `LogModel` com apenas `id` UUID e `created_at`.

### Deleção

Soft-delete via `is_active=False` para `Agente`, `Cliente`, `ModeloEquipamento`, `Deposito`. `ActiveManager` filtra por padrão. Log nunca é apagado nem desativado; correção é por estorno (`ISC-ADR-16`).

Desativar `Agente` com saldo em custódia é bloqueado na service layer (`ISC-RN-18`) — a verificação é uma consulta de saldo, não um flag.

### Service Layer

Toda regra vive em `iscas/services/`. Views e forms orquestram, nunca implementam regra. Services recebem dados já validados e o `usuario` autor como parâmetro explícito — nunca leem `request`.

### Ponto de Escrita Único do Livro-Razão

`iscas.services.custodia.registrar_movimentacao()` é a **única função autorizada** a criar `Movimentacao` / `MovimentacaoUnidade` e a atualizar os ponteiros de projeção da `Unidade`. Todos os demais services (entrada, transferência, baixa, entrega, retorno, manutenção, estorno) a chamam; nenhum escreve nesses models diretamente.

É o análogo, neste app, do `visiveis_para(user)` dos sistemas irmãos: um gargalo deliberado por onde 100% das escritas passam, garantindo que invariante nenhuma dependa de disciplina distribuída pelo código. Um teste de arquitetura verifica que nenhum módulo fora de `services/custodia.py` importa `Movimentacao` para escrita.

A função sempre roda em `transaction.atomic()`, e a atualização dos ponteiros acontece **na mesma transação** do lançamento.

### Permissões

Um único grupo Django: `Operadores Iscas`. Rotas protegidas por `PermissionRequiredMixin` / decorator. Parâmetros globais ficam no `/admin` para o Superusuário GSInt. Não há verificação de posse nem de tenant — todo operador vê tudo (`ISC-RN-19`).

### Dados Pessoais

CPF do agente é criptografado em repouso, com `cpf_hash` (SHA-256 + pepper de settings) `UNIQUE` para garantir unicidade sem descriptografar (`ISC-ADR-14`). Exibição mascarada em listagens; completo apenas na ficha, com registro de acesso (`ISC-RN-16`).

### Fuso Horário

Herdado do GSInt: `TIME_ZONE = 'America/Sao_Paulo'`, `USE_TZ = True`. Todo lançamento distingue `ocorrido_em` (momento real do fato, informado pelo operador) de `created_at` (momento do registro). A diferença entre os dois é a defasagem operacional — ela é medida, não escondida.

## Modelo de Dados (Conceitual)

### Cadastro

- **Agente** — `nome`, `cpf` (criptografado), `cpf_hash` (UNIQUE), `telefone`, `email` (nullable), `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf`, `cep`, `latitude`, `longitude` (Decimal, nullable), `geo_origem` (GEOCODIFICADO | MANUAL | PENDENTE), `geocodificado_em`.
    - Índice composto em (`latitude`, `longitude`) para o pré-filtro por bounding box.

- **Cliente** — `nome_razao_social`, `documento`, `tipo_documento` (CPF | CNPJ), `contato_nome`, `telefone`, `email`, mesmos campos de endereço e geolocalização do Agente.

- **Deposito** — `nome`, endereço, `latitude`, `longitude`. Modelado como entidade desde o MVP, ainda que exista um único registro: evita refatoração quando surgir um segundo ponto de estoque.

- **ModeloEquipamento** — `nome`, `codigo` (UNIQUE), `fabricante`, `descricao`, `tipo` (DESCARTAVEL | RETORNAVEL).
    - Validação de aplicação: `tipo` imutável se existir `MovimentacaoUnidade` de qualquer unidade do modelo (`ISC-RN-04`).

### Livro-Razão

- **Custodia** — a "conta" do livro. `tipo` (EXTERNO | DEPOSITO | AGENTE | CLIENTE | MANUTENCAO | BAIXA), `agente` (FK, nullable), `cliente` (FK, nullable), `deposito` (FK, nullable), `descricao`.
    - Uma `Custodia` é criada automaticamente por Agente, Cliente e Depósito. `EXTERNO`, `MANUTENCAO` e `BAIXA` são singletons criados por migration de dados.
    - CheckConstraint: exatamente uma FK preenchida para os tipos concretos; nenhuma para os singletons.
    - UNIQUE parcial por entidade, garantindo uma conta por agente/cliente/depósito.

- **Unidade** — `modelo` (FK), `identificador` (UNIQUE), `identificador_gerado` (bool), `observacao`.
    - **Ponteiros de projeção** (`ISC-ADR-04`): `custodia_atual` (FK Custodia), `custodia_desde` (datetime), `ultima_movimentacao` (FK Movimentacao).
    - Índice composto em (`custodia_atual`, `modelo`) — é o índice que sustenta toda consulta de saldo.

- **Movimentacao** — cabeçalho do lançamento. `tipo` (ENTRADA | TRANSFERENCIA | ENTREGA | RETORNO | ENVIO_MANUTENCAO | RETORNO_MANUTENCAO | BAIXA | ESTORNO), `origem` (FK Custodia), `destino` (FK Custodia), `autor` (FK Usuario), `ocorrido_em`, `justificativa`, `motivo_baixa` (nullable), `nota_fiscal` (nullable), `lote` (nullable), `solicitacao` (FK, nullable), `atribuicao` (FK, nullable), `estorno_de` (FK self, nullable), `created_at`.
    - Append-only. Sem `is_active`, sem `updated_at`, sem `save()` de atualização — a service layer rejeita instância com PK já persistida.

- **MovimentacaoUnidade** — linha do lançamento. `movimentacao` (FK), `unidade` (FK).
    - UNIQUE em (`movimentacao`, `unidade`). Índice em (`unidade`, `movimentacao`) para o extrato por unidade.

Um lote de 500 iscas é **um** cabeçalho e 500 linhas. O cabeçalho carrega o significado da operação (autor, momento, justificativa, documento de origem); as linhas carregam a identidade.

### Operação

- **Solicitacao** — `cliente` (FK), `status` (ABERTA | ATRIBUIDA | EM_ROTA | ENTREGUE | CANCELADA), `aberta_em`, `aberta_por` (FK Usuario), `prazo_desejado` (nullable), `observacao`, `motivo_cancelamento` (nullable).

- **ItemSolicitacao** — `solicitacao` (FK), `modelo` (FK), `quantidade`.
    - UNIQUE em (`solicitacao`, `modelo`).

- **Atribuicao** — `solicitacao` (FK), `agente` (FK), `status` (RESERVADA | EM_ROTA | ENTREGUE | CANCELADA), `criada_por`, `em_rota_em` (nullable), `entregue_em` (nullable), `recebido_por` (nullable), `motivo_cancelamento` (nullable).

- **AtribuicaoUnidade** — a reserva. `atribuicao` (FK), `unidade` (FK), `reservada_em`, `liberada_em` (nullable).
    - **UNIQUE parcial em (`unidade`) com condição `liberada_em IS NULL`** — garantia de banco de que uma unidade nunca tem duas reservas ativas (`ISC-RN-07`).

- **SolicitacaoEvento** — log append-only de transições. `solicitacao` (FK), `atribuicao` (FK, nullable), `status_anterior`, `status_novo`, `autor`, `dados` (JSONField), `created_at`.

### Configuração

- **ConfiguracaoIscas** — singleton editável no `/admin`: `raio_padrao_km`, `dias_alerta_retornavel`, `saldo_minimo_alerta`, `horas_alerta_em_rota`, `tiles_url`, `tiles_atribuicao`.

- **GeocodeCache** — `endereco_hash` (UNIQUE), `endereco_normalizado`, `latitude`, `longitude`, `provedor`, `consultado_em`.

## Derivação de Saldo e Situação

**Saldo em custódia** de um agente, por modelo:

```
Unidade.objects
  .filter(custodia_atual=custodia_do_agente)
  .values('modelo')
  .annotate(total=Count('id'))
```

Uma varredura sobre um índice composto. Não toca no livro-razão.

**Saldo disponível** = saldo em custódia menos reservas ativas, via `EXISTS` sobre `AtribuicaoUnidade` com `liberada_em IS NULL`. Não há campo `reservado` em lugar nenhum; a reserva é a existência da linha (`ISC-ADR-06`).

**Situação da unidade** (`ISC-ADR-07`) é anotação, não campo — `QuerySet.com_situacao()` monta um `Case/When` sobre o tipo da custódia atual, o tipo do modelo e a existência de reserva ativa:

| Custódia atual | Condição adicional        | Situação        |
|----------------|---------------------------|-----------------|
| BAIXA          | —                         | `BAIXADA`       |
| MANUTENCAO     | —                         | `EM_MANUTENCAO` |
| CLIENTE        | modelo DESCARTAVEL        | `CONSUMIDA`     |
| CLIENTE        | modelo RETORNAVEL         | `COM_CLIENTE`   |
| AGENTE         | reserva ativa, atrib. EM_ROTA | `EM_ROTA`   |
| AGENTE         | reserva ativa             | `RESERVADA`     |
| AGENTE         | sem reserva               | `COM_AGENTE`    |
| DEPOSITO       | —                         | `EM_DEPOSITO`   |

Guardas de service impedem que unidade em situação terminal (`CONSUMIDA`, `BAIXADA`) seja origem de qualquer lançamento — inclusive que descartável entregue apareça como candidata a `RETORNO` (`ISC-RN-05`).

**Tempo em posse de retornável** (`ISC-RF-31`) sai de `custodia_desde`, sem join.

## Concorrência: a Reserva

É a seção crítica do sistema. Duas solicitações simultâneas sobre o mesmo agente não podem alocar a mesma unidade (`ISC-RN-07`, RNF de concorrência).

`iscas.services.reserva.alocar_unidades(agente, modelo, quantidade, atribuicao)`:

```python
with transaction.atomic():
    unidades = list(
        Unidade.objects
        .select_for_update(skip_locked=True)
        .filter(
            custodia_atual=custodia_do_agente,
            modelo=modelo,
        )
        .exclude(
            Exists(AtribuicaoUnidade.objects.filter(
                unidade=OuterRef('pk'), liberada_em__isnull=True
            ))
        )
        .order_by('custodia_desde')[:quantidade]
    )
    if len(unidades) < quantidade:
        raise SaldoInsuficiente(...)
    AtribuicaoUnidade.objects.bulk_create([...])
```

Três garantias empilhadas:

1. **`select_for_update(skip_locked=True)`** — transações concorrentes ignoram linhas já travadas e pegam as próximas disponíveis, em vez de bloquear em fila. É semântica de fila de trabalho, correta para alocação.
2. **Verificação de contagem dentro da transação** — se o lock rendeu menos unidades do que o pedido, a transação inteira reverte com `SaldoInsuficiente`. Nunca há reserva parcial silenciosa.
3. **Índice único parcial em `AtribuicaoUnidade`** — última linha de defesa, no banco. Mesmo com bug de aplicação, dupla reserva ativa é impossível.

Ordenação por `custodia_desde` implementa o FIFO de `ISC-RF-25`.

**Confirmação de entrega** roda no mesmo padrão: `select_for_update` sobre as unidades da atribuição, `registrar_movimentacao()` de ENTREGA (Agente → Cliente), `liberada_em` preenchido nas reservas, transição de status, evento no log — tudo numa transação.

**Cancelamento** preenche `liberada_em` e transita o status. Não gera lançamento: nada mudou de custódia (`ISC-RN-09`).

## Geolocalização

### Busca por proximidade

Pré-filtro por bounding box antes do haversine — descarta a maioria dos candidatos com um índice B-tree comum, sem PostGIS:

```
delta_lat = raio_km / 111.045
delta_lng = raio_km / (111.045 * cos(radians(lat_origem)))
```

Sobre o conjunto reduzido, o haversine é anotado com funções matemáticas do ORM (`Cos`, `Sin`, `ACos`, `Radians`) — sem SQL cru:

```
6371 * ACos( clamp( Cos(lat0)*Cos(lat)*Cos(lng - lng0) + Sin(lat0)*Sin(lat) ) )
```

O `clamp` em [-1, 1] via `Least`/`Greatest` não é preciosismo: ponto idêntico produz argumento marginalmente acima de 1 por erro de ponto flutuante, e `acos` estoura com domain error. Já mordeu gente antes.

Filtro final `distancia_km <= raio` e ordenação por distância. O bounding box é conservador por construção — pode incluir candidato fora do raio (o haversine descarta), nunca excluir candidato dentro dele. Falso negativo aqui seria estoque invisível, e há teste específico para isso.

Agente com `latitude` ou `longitude` nulos é excluído da busca e listado à parte com alerta (`ISC-RN-12`, `ISC-RF-21`).

### Geocodificação

Nominatim/OSM por HTTP, síncrono no salvamento, com timeout de 3 segundos (`ISC-ADR-11`). Falha ou timeout não bloqueiam: o cadastro grava com `geo_origem=PENDENTE` e sinalização na UI (`ISC-RF-02`).

`GeocodeCache` evita reconsulta do mesmo endereço normalizado. `User-Agent` identificando a aplicação é obrigatório pela política de uso do Nominatim, assim como o limite de 1 requisição por segundo — respeitado pelo command `geocodificar_pendentes`, que reprocessa pendências em lote com throttle.

Ajuste manual do pin (`ISC-RF-03`) grava `geo_origem=MANUAL`, e a geocodificação automática **não sobrescreve** posição manual enquanto os campos de endereço não mudarem.

## Camada de Apresentação

SSR com Django Templates. HTMX para busca de proximidade, painéis parciais de saldo, listagens filtradas e confirmações. Alpine.js para estado local do painel lateral e seleção de unidades.

O mapa é Leaflet vendorizado em `static/`, alimentado por `GET /iscas/api/agentes.geojson` — view Django retornando `JsonResponse` com GeoJSON montado em `selectors.py`. Sem DRF (`ISC-ADR-12`).

`Leaflet.markercluster` cobre o requisito de 500 marcadores sem degradação. A sincronia mapa ↔ tabela lateral (`ISC-RF-20`) é Alpine ouvindo eventos do Leaflet, sem round-trip ao servidor.

Tiles OSM com atribuição obrigatória, URL vinda de `ConfiguracaoIscas` — trocar por MapTiler ou Mapbox é mudança de configuração, não de código (`ISC-ADR-10`).

## Decisões Arquiteturais (ADRs)

- **ISC-ADR-01** — **App no GSInt com fronteira de migração**
    - Decisão: `iscas/` como app do monólito GSInt, sem depender de nenhum outro app além de `core` e da autenticação.
    - Racional: o GSInt é o monólito legado, previsto para substituição pelo HubSAT. Construir nele é a decisão de negócio; o que a arquitetura controla é o **custo da migração futura**. Domínio inteiro dentro do app, nenhum app do GSInt dependendo do Iscas Fast, nenhuma FK saindo do app exceto para `Usuario`.
    - Consequências: alguma duplicação em relação a cadastros que talvez existam no GSInt (ver ISC-ADR-17). Em compensação, migrar é mover um app, não desemaranhar acoplamento.

- **ISC-ADR-02** — **Livro-razão append-only como fonte da verdade**
    - Decisão: `Movimentacao` + `MovimentacaoUnidade` são a única fonte de verdade sobre custódia. Nenhum saldo é armazenado.
    - Racional: saldo em campo diverge do histórico — é questão de quando, não de se. O padrão já é praticado no Estoque do HubSAT e no `ChamadoEvento` do GSInt.
    - Consequências: correção só por estorno; consultas de saldo são agregações; obrigação de manter os ponteiros de projeção consistentes (ISC-ADR-04).

- **ISC-ADR-03** — **Custódia como entidade, não FKs polimórficas**
    - Decisão: tabela `Custodia` funcionando como conta contábil; `Movimentacao` tem uma FK de origem e uma de destino.
    - Racional: a alternativa (seis FKs nuláveis com check constraints, ou `GenericForeignKey`) polui o modelo e destrói a indexabilidade. Com conta única, todo lançamento é um par de FKs indexadas, e adicionar um novo tipo de custódia não altera `Movimentacao`.
    - Consequências: indireção a mais na leitura; necessidade de criar a conta junto com a entidade (signal na criação de Agente/Cliente/Depósito) e de um command `seed_custodias` para os singletons.

- **ISC-ADR-04** — **Ponteiros de custódia na Unidade como projeção transacional**
    - Decisão: `Unidade.custodia_atual`, `custodia_desde` e `ultima_movimentacao` são campos, escritos exclusivamente por `registrar_movimentacao()` na mesma transação do lançamento.
    - Racional: é o desvio consciente do princípio "derivado nunca é campo", e a razão é técnica, não de performance. A custódia atual de uma unidade é "o destino do último lançamento dela" — em SQL, uma window function. E **PostgreSQL não permite `SELECT ... FOR UPDATE` em query com window function, agregação ou `GROUP BY`**. Sem ponteiro, não existe forma atômica de travar as unidades a reservar; a alternativa seria materializar candidatos e travar por id depois, o que reabre a corrida exatamente onde ela importa. O ponteiro é o que torna a reserva correta.
    - Consequências: invariante a manter. Mitigações: ponto de escrita único; command `recomputar_custodias` que reconstrói os três campos a partir do livro; e teste de reconciliação que compara ponteiro a ponteiro contra a reconstrução. O livro continua sendo a autoridade — o ponteiro é cache, e cache reconstruível.

- **ISC-ADR-05** — **Unidade individual, operação em lote**
    - Decisão: cada isca é uma linha; a UI opera por quantidade.
    - Racional: contador agregado não responde "onde está esta isca", não rastreia retornável em posse de cliente e não permite baixa por unidade. O custo de ergonomia se resolve na interface (colagem de lista, faixa sequencial, seleção automática FIFO).
    - Consequências: volume de linhas maior; cadastro de lote precisa ser eficiente (`bulk_create`).

- **ISC-ADR-06** — **Reserva por linha, com lock e índice único parcial**
    - Decisão: reserva é a existência de `AtribuicaoUnidade` com `liberada_em IS NULL`; alocação com `select_for_update(skip_locked=True)`; unicidade garantida por índice parcial no banco.
    - Racional: três camadas independentes. A aplicação pode errar; o índice parcial não deixa a inconsistência existir.
    - Consequências: liberação é preencher `liberada_em`, nunca deletar — o histórico de reservas canceladas fica auditável.

- **ISC-ADR-07** — **Situação da unidade derivada, status de workflow armazenado**
    - Decisão: `Unidade` não tem campo de situação (anotação `Case/When`); `Solicitacao` e `Atribuicao` **têm** campo `status`, mutável apenas por transição, com evento no log.
    - Racional: a distinção é deliberada. A situação da unidade é **consequência** de custódia e reserva — não tem vida própria, e um campo aqui seria uma terceira cópia da mesma verdade. O status da solicitação é um **workflow** com atores, guardas e transições inválidas: é estado de primeira classe, e o padrão da casa é armazená-lo com log de transições (`ChamadoEvento`).
    - Consequências: filtros por situação exigem a annotation; `com_situacao()` é o único caminho e está coberto por teste.

- **ISC-ADR-08** — **Máquinas de estado declarativas na service layer**
    - Decisão: tabelas de transição de `Solicitacao` e `Atribuicao` como estrutura de dados em `services/solicitacao.py`; mutação de status só por `transitar()`.
    - Racional: mesmo padrão do Chamados. Tabela declarativa é testável exaustivamente de forma parametrizada.
    - Consequências: toda transição gera `SolicitacaoEvento`; transição inválida levanta exceção de domínio, nunca falha em silêncio.

- **ISC-ADR-09** — **Haversine em SQL com bounding box, sem PostGIS**
    - Decisão: pré-filtro por caixa e haversine via funções matemáticas do ORM.
    - Racional: PostGIS resolveria com elegância, mas exige extensão no servidor, migration específica e conhecimento de operação que a equipe não tem hoje. Para 100 agentes e distância em linha reta, um índice B-tree em (lat, lng) mais aritmética resolve com folga. Migrar para PostGIS depois não muda o modelo, só a implementação de `agentes_proximos()`.
    - Consequências: distância em linha reta, não rodoviária — consistente com o não-objetivo de roteirização. Necessidade do clamp no `acos`.

- **ISC-ADR-10** — **Leaflet com tiles OSM, provedor configurável**
    - Decisão: Leaflet vendorizado, tiles OSM públicos, URL e atribuição em configuração.
    - Racional: zero custo e zero cadastro no MVP. A política de uso do OSM não comporta volume alto, e o app é interno de baixo tráfego — mas a troca precisa ser barata.
    - Consequências: se o volume crescer, migrar para provedor pago é alterar dois campos no `/admin`.

- **ISC-ADR-11** — **Geocodificação síncrona com degradação graciosa**
    - Decisão: chamada síncrona no salvamento, timeout de 3s, cache local, `PENDENTE` em caso de falha, command para reprocessar.
    - Racional: o volume é de dezenas de cadastros por mês. Introduzir Celery + Redis no GSInt por causa disso seria pagar infraestrutura permanente por um problema ocasional. O serviço está atrás de `services/geo.py`: se o GSInt ganhar Celery por outro motivo, tornar assíncrono é mudar o call site.
    - Consequências: salvamento de cadastro pode levar até 3s; o operador precisa saber que o pin pendente é normal e corrigível à mão.

- **ISC-ADR-12** — **Sem DRF: endpoints JSON com `JsonResponse`**
    - Decisão: o GeoJSON do mapa e os parciais são views Django comuns.
    - Racional: padrão da casa — sem DRF no MVP. Não há consumidor externo, não há contrato a versionar, não há autenticação por token. DRF aqui seria uma dependência para serializar um dicionário.
    - Consequências: serialização manual em `selectors.py`, com teste de formato.

- **ISC-ADR-13** — **Sem Celery/Redis no MVP**
    - Decisão: todas as operações são síncronas; jobs periódicos, se necessários, entram como management command agendado por cron.
    - Racional: o GSInt não roda Celery hoje (mesma decisão do app Chamados). Nada no Iscas Fast é pesado o bastante para justificar a mudança de topologia de deploy.
    - Consequências: exportação de CSV grande é streaming síncrono; alertas de retornável e de saldo baixo são calculados na leitura do dashboard, não empurrados.

- **ISC-ADR-14** — **CPF criptografado com hash de unicidade**
    - Decisão: `cpf` criptografado em repouso; `cpf_hash` (SHA-256 + pepper) `UNIQUE` para impedir agente duplicado.
    - Racional: consistente com o tratamento de CPF no GS Learning. O hash resolve unicidade sem descriptografar a base inteira a cada validação.
    - Consequências: gestão de chave e de pepper em variável de ambiente; perda da chave inviabiliza leitura dos CPFs — precisa entrar na rotina de backup de segredos. Busca por CPF só por igualdade (via hash), nunca por trecho.

- **ISC-ADR-15** — **Soft-delete padrão, log como exceção formal**
    - Decisão: cadastros com `is_active`; `Movimentacao`, `MovimentacaoUnidade` e `SolicitacaoEvento` sem soft-delete e sem update.
    - Racional: desativar um lançamento reescreveria todo saldo derivado dele. O log é o alicerce; alicerce não se edita.
    - Consequências: crescimento monotônico das tabelas de log — aceitável no volume projetado (100k lançamentos em dois anos).

- **ISC-ADR-16** — **Estorno em vez de edição ou exclusão**
    - Decisão: lançamento errado se corrige com contra-lançamento tipo `ESTORNO`, referenciando o original via `estorno_de`.
    - Racional: o erro é informação. Auditoria precisa ver o que foi lançado, quando se percebeu e quem corrigiu.
    - Consequências: extrato mostra as três linhas (original, estorno, lançamento correto) com o vínculo explícito; a UI agrupa visualmente para não confundir o operador.

- **ISC-ADR-17** — **Cadastro de Cliente próprio do app** *(a confirmar contra o código do GSInt)*
    - Decisão: `iscas.Cliente` próprio, sem reaproveitar model de cliente eventualmente existente em outro app do GSInt.
    - Racional: o Iscas Fast precisa de campos que um cadastro genérico provavelmente não tem (endereço geocodificado com pin manual, `geo_origem`), e a fronteira limpa do ISC-ADR-01 depende de não criar FK para outros apps.
    - Consequências: duplicação de cadastro de cliente dentro do GSInt. **Esta é a decisão mais frágil do documento**: se já existir um cadastro de cliente compartilhado e confiável no GSInt, reaproveitá-lo com uma tabela de extensão (`iscas.ClienteGeo` com OneToOne) é provavelmente melhor — vale conferir antes de implementar.

## Estratégia de Testes

TDD obrigatório para regra de negócio: o teste do service vem antes da implementação.

### Pirâmide

- **Unitários (pytest):** services de custódia, saldo, reserva, estorno, haversine, montagem de mensagem, tabelas de transição.
- **Integração (pytest-django):** views, forms, querysets, annotations, endpoint GeoJSON, exportação CSV, permissões.
- **E2E (pytest):** jornada completa — entrada de lote → transferência ao agente → solicitação → busca por proximidade → atribuição dividida entre dois agentes → rota → entrega → retorno de retornável.

### Testes Críticos Específicos

- **Reconciliação (ISC-ADR-04):** reconstruir `custodia_atual`, `custodia_desde` e `ultima_movimentacao` de todas as unidades a partir do livro-razão reproduz exatamente os ponteiros gravados. É o teste que sustenta o desvio ao princípio de derivação.
- **Concorrência de reserva (ISC-RN-07):** duas conexões reservando simultaneamente sobre saldo suficiente para apenas uma — exatamente uma sucede, a outra levanta `SaldoInsuficiente`, nenhuma unidade fica com duas reservas ativas. Executado com `TransactionTestCase` e conexões reais, não com transação de teste.
- **Índice único parcial:** tentativa de inserir segunda `AtribuicaoUnidade` ativa para a mesma unidade levanta `IntegrityError` — verifica a garantia de banco, não a da aplicação.
- **Tabelas de transição (parametrizado):** toda transição válida de `Solicitacao` e `Atribuicao` é permitida e gera evento; **toda** combinação inválida é bloqueada. Cobertura exaustiva da matriz.
- **Terminalidade do descartável (ISC-RN-05):** unidade descartável entregue não aparece como candidata a `RETORNO` e o service rejeita a tentativa por id direto.
- **Retornável em posse:** unidade retornável entregue permanece consultável com o cliente e o tempo em posse cresce corretamente.
- **Cancelamento (ISC-RN-09):** cancelar atribuição libera todas as reservas e restaura o saldo disponível ao valor anterior — comparação numérica antes/depois.
- **Estorno (ISC-ADR-16):** o lançamento original permanece byte a byte inalterado; o saldo volta ao estado anterior; a unidade volta à custódia anterior.
- **Bounding box não produz falso negativo:** agente posicionado a 0,99 × raio em oito direções cardeais e diagonais aparece no resultado. É o erro grave da geolocalização — estoque real que some da busca.
- **Haversine contra distâncias conhecidas:** pares de coordenadas com distância documentada, tolerância de 1%; e pontos idênticos retornando 0 sem estourar `acos`.
- **Agente sem coordenada (ISC-RN-12):** ausente da busca por proximidade, presente na listagem geral com alerta.
- **Desativação bloqueada (ISC-RN-18):** desativar agente com saldo em custódia é rejeitado; com saldo zerado, permitido.
- **Ponto de escrita único:** teste de arquitetura verificando que nenhum módulo fora de `services/custodia.py` importa `Movimentacao` ou `MovimentacaoUnidade` para escrita.
- **Imutabilidade do tipo de modelo (ISC-RN-04):** alterar `tipo` de modelo com unidades movimentadas é rejeitado.
- **Mascaramento de CPF (ISC-RN-16):** listagens nunca expõem CPF completo, nem por manipulação de parâmetro.

## Evolução Prevista (fora do MVP)

Ordem sugerida, cada item independente:

1. **Índice geoespacial (PostGIS)** — quando a base passar de alguns milhares de agentes ou surgir necessidade de consulta por polígono (área de cobertura, região de atendimento).
2. **Leitura de código de barras / QR** — elimina digitação de identificador; depende de interface mobile decente.
3. **Celery** — se e quando o GSInt adotar; a geocodificação e a exportação migram sem alteração de modelo.
4. **App ou portal do agente** — muda `ISC-RN-15` e reabre `Agente` como usuário; o modelo de custódia não muda, só o autor das ações.
5. **Integração com o HubSAT** — a saída de estoque da matriz vira entrada no Iscas Fast. O livro-razão já comporta: bastaria uma conta `Custodia` do tipo EXTERNO representando o HubSAT e um lançamento idempotente por documento de origem.

# PRD — App Iscas Fast (GSInt)

> Decisões técnicas (stack, modelo de dados, padrões de código, ADRs) estão documentadas em `ARCHITECTURE.md`. Este documento foca em **o que** o sistema faz, não em **como**.

## Sumário Executivo

O **Iscas Fast** é um app interno do sistema **GSInt** (monólito Django) para controlar o estoque de iscas do Grupo Golden Sat **em campo**. A diferença central em relação a um controle de estoque comum é que o estoque não fica parado num depósito: ele fica **com pessoas**, os agentes, distribuídas geograficamente pelo território de atuação.

Isso muda a pergunta que o sistema precisa responder. Não é "quantas iscas eu tenho?", é **"o cliente X precisa de N iscas agora — quem está perto dele e tem saldo?"**. Por isso o mapa não é um enfeite de dashboard: é a ferramenta operacional de decisão. O operador abre a solicitação do cliente, vê no mapa os agentes num raio configurável com o saldo disponível de cada um, atribui um ou mais agentes ao atendimento, e confirma a entrega quando ela acontece.

A premissa de projeto é o binômio **saldo derivado** e **custódia rastreável**. Nenhum saldo é campo no banco: todo saldo é computado a partir de um **log append-only de movimentações**, que registra origem, destino, tipo, autor e momento de cada mudança de custódia. E cada isca é uma **unidade individual identificada** — a interface opera em lote ("dar baixa em 8"), mas o sistema aloca 8 unidades específicas e sabe responder onde cada uma está. Sem isso, perda, avaria e devolução de retornável ficam irrastreáveis e o saldo se degrada em semanas.

O catálogo distingue dois tipos de isca: **descartável**, que ao ser entregue sai do estoque em definitivo, e **retornável**, que permanece rastreada em custódia do cliente até voltar por um evento de retorno.

Há um único perfil operando o sistema: o **Operador GS**. Agentes e clientes são atores do domínio, **não usuários** — não têm login, não acessam a plataforma. A comunicação com o agente acontece por WhatsApp, fora do sistema.

Público-alvo inicial: equipe interna de operação do Grupo Golden Sat. Escala estimada para o MVP: 100 agentes ativos, 5.000 unidades em circulação, 200 solicitações/mês.

## Problema e Oportunidade

### Contexto do Negócio

O Grupo Golden Sat mantém iscas distribuídas com agentes espalhados pelo território de atuação, justamente para que a entrega ao cliente seja rápida — a proposta de valor é proximidade. Quando um cliente solicita equipamento, o tempo de resposta depende de encontrar um agente próximo que tenha saldo.

Hoje essa informação não existe de forma consultável. Saber quantas iscas um agente tem exige ligar e perguntar. Saber quem está perto do cliente exige conhecimento pessoal da geografia da operação, concentrado em poucas pessoas. O controle do que saiu e do que voltou é informal, quando existe.

O efeito é acumulativo: sem registro confiável de saída e entrada, o saldo real diverge do saldo imaginado. Iscas retornáveis que ficaram com o cliente e nunca voltaram só aparecem quando alguém percebe a falta. Iscas perdidas ou avariadas não têm momento nem responsável identificado.

### Problemas Específicos

- Não há visibilidade de quanto cada agente tem em posse; a consulta depende de contato individual.
- Não há forma de encontrar rapidamente qual agente está próximo de um cliente que solicitou equipamento.
- Não há registro formal das saídas e entradas; o histórico depende da memória de quem operou.
- Iscas retornáveis entregues a clientes não são rastreadas até o retorno — o passivo em posse de terceiros é desconhecido.
- Perdas e avarias não têm momento, custódia nem responsável registrados; a diferença aparece só em contagem física.
- O conhecimento da distribuição geográfica dos agentes é tácito e concentrado, o que gera risco de continuidade.

### Oportunidade

Um app de estoque com dimensão geográfica resolve os seis problemas com um único modelo: um **livro-razão append-only de movimentações** que é a fonte da verdade de todo saldo, somado a **coordenadas de agente e de cliente** que tornam a busca por proximidade uma consulta e não um telefonema.

A solução é deliberadamente específica: estoque com custódia pessoal, busca por raio geográfico, e rastreio unitário. Não é um WMS, não é um roteirizador, não é um sistema de logística de transporte.

## Objetivo

### Objetivos de Produto

1. Responder em menos de 30 segundos, a partir do endereço de um cliente, quais agentes estão em condição de atendê-lo e com qual saldo.
2. Garantir que 100% das mudanças de custódia de equipamento tenham registro com origem, destino, autor e momento — sem exceção e sem edição posterior.
3. Eliminar a divergência entre saldo em sistema e saldo físico, tornando o saldo uma função do log e não um número mantido à mão.
4. Tornar visível, a qualquer momento, o total de iscas retornáveis em posse de clientes e há quanto tempo.
5. Permitir adicionar novos modelos de isca e novos agentes sem alteração de código.

### Não-Objetivos

- **Login para agentes e clientes.** Nenhum ator externo acessa o sistema. Todo registro é feito pelo Operador GS.
- **Notificação automática** por e-mail, SMS, push ou API de WhatsApp. A comunicação com o agente é manual e externa; o sistema apenas monta o texto da mensagem para cópia.
- **Aplicativo mobile nativo ou PWA instalável.** Interface web responsiva acessível pelo navegador.
- **Integração com o HubSAT** ou qualquer sistema irmão. O Iscas Fast é autossuficiente no MVP; nenhum saldo, cadastro ou evento vem de fora.
- **Rastreamento em tempo real da posição do agente.** A posição usada é o endereço cadastral, estático.
- **Cálculo de rota rodoviária, ETA ou otimização de rotas.** A distância é em linha reta e serve para ordenar candidatos, não para planejar deslocamento.
- **Roteirização de múltiplas entregas** ou consolidação de cargas.
- **Faturamento, precificação, custo de equipamento ou comissão de agente.** O sistema controla quantidade e custódia, não dinheiro.
- **Contrato de comodato formal** com geração de termo, assinatura ou vencimento contratual para iscas retornáveis. O sistema registra posse e tempo em posse, não o instrumento jurídico.
- **Workflow de agendamento de coleta** de retornáveis. O retorno é registrado quando acontece; não há agenda, rota nem cobrança automatizada.
- **Leitura de código de barras ou QR Code** para movimentação. Identificadores são digitados ou colados.
- **Inventário cíclico e contagem física assistida** pelo sistema (divergência de contagem é ajustada por movimentação manual justificada).
- **Multi-empresa ou isolamento por tenant.** O app é interno, com um único conjunto de dados.
- **Tradução de interface.** PT-BR exclusivamente.

## Personas

- **Operador GS:** único perfil com acesso ao sistema. Cadastra agentes, clientes e modelos; registra entradas de equipamento novo; recebe a solicitação do cliente por canal externo e a registra; busca agentes próximos no mapa; atribui o atendimento; confirma a entrega; registra retornos, perdas e avarias; consulta histórico e extratos. É o operador de todas as ações do domínio.

- **Superusuário GSInt (Staff interno):** acesso ao `/admin` do Django para parâmetros sistêmicos — raio padrão de busca, prazo de alerta de retornável em posse, provedor de tiles do mapa, catálogo de motivos de baixa. Não opera o fluxo diário.

- **Agente (ator externo, não usuário):** pessoa que mantém iscas em posse e realiza a entrega ao cliente. Possui nome, CPF, endereço geolocalizado e um saldo de equipamentos derivado do log. **Não tem login e não acessa o sistema** — recebe a demanda por WhatsApp e reporta a entrega ao operador pelo mesmo canal.

- **Cliente (ator externo, não usuário):** empresa ou pessoa que solicita iscas. Possui endereço geolocalizado, que é o ponto de referência da busca por proximidade. **Não tem login e não acessa o sistema.**

## Histórias de Usuário

- **Cadastros e estoque:**
    - Como operador, quero cadastrar um agente com nome, CPF, telefone e endereço completo, para que ele apareça no mapa e possa receber equipamentos. (ISC-RF-01, ISC-RF-02)
    - Como operador, quero corrigir manualmente o pin do agente no mapa quando a geocodificação errar, para que a busca por proximidade não fique distorcida. (ISC-RF-03)
    - Como operador, quero cadastrar um modelo de isca indicando se é descartável ou retornável, para que o sistema saiba se aquela unidade volta ao estoque. (ISC-RF-05, ISC-RN-04)
    - Como operador, quero registrar a entrada de um lote de iscas novas colando a lista de identificadores, para não cadastrar 500 unidades uma a uma. (ISC-RF-07, ISC-RF-08)
    - Como operador, quero transferir unidades do depósito para um agente, para abastecer quem está com saldo baixo. (ISC-RF-11)
    - Como operador, quero consultar uma isca pelo identificador e ver onde ela está e por onde passou, para responder a qualquer pergunta sobre uma unidade específica. (ISC-RF-10)

- **Atendimento a solicitação:**
    - Como operador, quero registrar a solicitação de um cliente informando modelo e quantidade, para dar início ao atendimento. (ISC-RF-22)
    - Como operador, quero ver no mapa os agentes num raio do cliente com o saldo disponível de cada um, para escolher quem atende. (ISC-RF-16, ISC-RF-17, ISC-RF-18)
    - Como operador, quero dividir uma solicitação entre dois agentes quando nenhum tem saldo suficiente sozinho, para não deixar o cliente sem atendimento. (ISC-RF-23, ISC-RN-10)
    - Como operador, quero que as unidades fiquem reservadas assim que eu atribuo o agente, para que outra solicitação não aloque as mesmas iscas. (ISC-RF-24, ISC-RN-07)
    - Como operador, quero copiar um texto pronto com endereço do cliente e quantidade para mandar no WhatsApp do agente, para não redigitar a informação. (ISC-RF-28)
    - Como operador, quero confirmar a entrega quando o agente me avisar que entregou, para que o saldo dele reflita a realidade. (ISC-RF-26, ISC-RN-08)
    - Como operador, quero cancelar uma atribuição e devolver as unidades ao saldo disponível do agente, quando o atendimento não se concretizar. (ISC-RF-27, ISC-RN-09)

- **Retornáveis e baixas:**
    - Como operador, quero ver todas as iscas retornáveis que estão com clientes e há quanto tempo, para cobrar a devolução do que está parado. (ISC-RF-30, ISC-RF-32)
    - Como operador, quero registrar o retorno de uma isca retornável indicando se voltou para o agente ou para o depósito, para recolocá-la no saldo disponível. (ISC-RF-31, ISC-RN-06)
    - Como operador, quero registrar perda ou avaria com justificativa, para que a unidade saia do saldo com motivo documentado. (ISC-RF-12, ISC-RN-13)
    - Como operador, quero estornar uma movimentação lançada por engano sem apagar o registro errado, para manter a auditoria íntegra. (ISC-RF-14, ISC-RN-02)

- **Histórico:**
    - Como operador, quero um extrato de todas as entradas e saídas filtrável por período, agente, cliente, modelo e tipo, para investigar qualquer divergência. (ISC-RF-33)
    - Como operador, quero ver o histórico completo de um agente, para conferir o que ele recebeu e o que entregou. (ISC-RF-34)
    - Como operador, quero exportar o extrato em CSV, para trabalhar os dados fora do sistema. (ISC-RF-36)

## Regras de Negócio

Decisões normativas que regem custódia, saldo e ciclo da solicitação, separadas dos requisitos funcionais para dar peso e facilitar futuras revisões.

- **ISC-RN-01:** Saldo é **sempre derivado** do log de movimentações, nunca armazenado como campo. Não existe campo "quantidade de equipamentos" em Agente, Depósito ou Cliente — *o saldo é uma função do histórico; um campo redundante inevitavelmente diverge dele.*
- **ISC-RN-02:** Toda mudança de custódia gera uma `Movimentacao` com origem, destino, tipo, autor, momento e unidades envolvidas. O registro é **append-only e imutável**; correção de lançamento errado se faz por movimentação de estorno, que referencia a original — *auditoria exige que o erro e a correção sejam ambos visíveis.*
- **ISC-RN-03:** Cada isca é uma **unidade individual** com identificador único no sistema. Operações de interface são em lote, mas a alocação é unitária — *rastrear perda, avaria e retorno exige identidade; contador agregado não responde "onde está esta isca".*
- **ISC-RN-04:** Todo `ModeloEquipamento` é `DESCARTAVEL` ou `RETORNAVEL`, definido no cadastro. O tipo é **imutável** depois que existir qualquer unidade daquele modelo com movimentação registrada — *mudar o tipo retroativamente invalidaria o significado do histórico já gravado.*
- **ISC-RN-05:** Unidade de modelo **descartável** entregue ao cliente entra em estado terminal (`CONSUMIDA`) e não retorna ao saldo por nenhum caminho — *a entrega é o fim do ciclo de vida dela no estoque.*
- **ISC-RN-06:** Unidade de modelo **retornável** entregue ao cliente permanece rastreada em custódia do cliente por tempo indeterminado, até um evento de `RETORNO` — *o passivo em posse de terceiro é informação de estoque, não ausência de informação.*
- **ISC-RN-07:** Na atribuição de um agente a uma solicitação, as unidades são **reservadas**: continuam em custódia do agente, mas ficam indisponíveis para outra solicitação. Saldo disponível = saldo em custódia − reservas ativas — *sem reserva, duas solicitações simultâneas alocam as mesmas unidades.*
- **ISC-RN-08:** A custódia só transfere do agente para o cliente na **confirmação de entrega**, registrada pelo Operador GS. A atribuição por si só não movimenta estoque — *o sistema registra o que aconteceu, não o que foi planejado.*
- **ISC-RN-09:** Cancelamento de atribuição ou de solicitação **libera todas as reservas ativas** vinculadas, devolvendo as unidades ao saldo disponível do agente. Cancelamento exige motivo — *reserva órfã trava estoque real.*
- **ISC-RN-10:** Uma solicitação pode ser atendida por **múltiplos agentes**, cada atribuição com seu agente e sua quantidade. A solicitação só atinge `ENTREGUE` quando todas as atribuições ativas estão entregues e a soma cobre a quantidade solicitada — *o agente mais próximo raramente tem o saldo exato do pedido.*
- **ISC-RN-11:** A busca por proximidade calcula distância em **linha reta** entre as coordenadas do cliente e as do agente, dentro de um raio configurável, ordenando por distância crescente. O resultado exibe o saldo disponível de cada agente para o modelo solicitado — *distância em linha reta ordena bem candidatos; rota rodoviária é precisão que não muda a decisão.*
- **ISC-RN-12:** Agente sem coordenadas válidas **não aparece** no resultado da busca por proximidade, mas aparece na listagem geral sinalizado com alerta — *omitir silenciosamente cria estoque invisível.*
- **ISC-RN-13:** Baixa por `PERDA`, `AVARIA` ou `OBSOLESCENCIA` exige **justificativa textual obrigatória** e registra o autor. A unidade sai do saldo e entra em estado terminal (`BAIXADA`) — *baixa sem motivo é buraco no inventário.*
- **ISC-RN-14:** Envio para manutenção **não é baixa**: a unidade muda para custódia de manutenção, sai do saldo disponível e pode retornar ao depósito por movimentação de retorno — *manutenção é ciclo reversível.*
- **ISC-RN-15:** Agente e Cliente são **entidades de domínio, não usuários**. Não possuem credencial, não acessam o sistema e não executam nenhuma ação nele. Toda ação do sistema tem como autor um Operador GS ou o Superusuário — *concentra a responsabilidade do registro em quem tem acesso.*
- **ISC-RN-16:** CPF do agente é dado pessoal sensível (LGPD). Armazenado com acesso restrito, exibido mascarado nas listagens e completo apenas na ficha do agente — *o CPF é necessário à identificação do custodiante, não à operação diária.*
- **ISC-RN-17:** Soft-delete via `is_active=False` é o padrão para cadastros (Agente, Cliente, Modelo). `Movimentacao` é **exceção formal**: nunca é desativada nem apagada — *o log é o alicerce de todo saldo; removê-lo reescreveria o passado.*
- **ISC-RN-18:** Agente desativado não recebe novas atribuições e não aparece no mapa, mas **mantém o saldo e o histórico**. Desativar agente com saldo em custódia exige transferência prévia das unidades — *desativação não pode evaporar estoque.*
- **ISC-RN-19:** Toda ação relevante registra autor e momento. O Operador GS enxerga todos os dados do sistema, sem isolamento — *o app é interno e a operação é compartilhada.*

## Ciclo de Vida da Unidade de Equipamento

A unidade é a peça central do domínio. Seu estado é derivado do log de movimentações somado às reservas ativas — não é um campo mantido à mão.

- `EM_DEPOSITO` — Unidade em custódia da matriz, disponível — Sistema (entrada ou transferência)
- `COM_AGENTE` — Unidade em custódia de agente, disponível — Sistema (transferência)
- `RESERVADA` — Em custódia do agente, vinculada a atribuição ativa, indisponível — Sistema (atribuição)
- `EM_ROTA` — Reservada e em deslocamento para o cliente — Operador (marcação de rota)
- `COM_CLIENTE` — Retornável entregue, em custódia do cliente — Sistema (confirmação de entrega, modelo retornável)
- `CONSUMIDA` — Descartável entregue. **Terminal** — Sistema (confirmação de entrega, modelo descartável)
- `EM_MANUTENCAO` — Fora do saldo disponível, ciclo reversível — Operador
- `BAIXADA` — Perda, avaria ou obsolescência. **Terminal** — Operador (com justificativa)

Transições relevantes: `COM_CLIENTE → COM_AGENTE | EM_DEPOSITO` por retorno; `EM_MANUTENCAO → EM_DEPOSITO` por conclusão de manutenção; `RESERVADA | EM_ROTA → COM_AGENTE` por cancelamento; qualquer estado não-terminal → `BAIXADA`. Estados terminais não admitem saída.

## Ciclo de Vida da Solicitação

**Solicitação:**
- `ABERTA` — Registrada, sem atribuição ativa — Operador (criação)
- `ATRIBUIDA` — Ao menos uma atribuição ativa; a UI indica cobertura parcial ou total — Operador
- `EM_ROTA` — Ao menos uma atribuição em deslocamento — Operador
- `ENTREGUE` — Todas as atribuições ativas entregues e cobertura total. **Terminal** — Sistema
- `CANCELADA` — Encerrada sem atendimento, com motivo. **Terminal** — Operador

Transições válidas: `ABERTA → ATRIBUIDA`, `ATRIBUIDA → EM_ROTA`, `EM_ROTA → ENTREGUE`, `ATRIBUIDA → ABERTA` (última atribuição cancelada), e `CANCELADA` a partir de `ABERTA`, `ATRIBUIDA` ou `EM_ROTA`.

**Atribuição (entidade filha da Solicitação):**
- `RESERVADA` — Unidades reservadas com o agente — Operador (atribuição)
- `EM_ROTA` — Agente em deslocamento — Operador
- `ENTREGUE` — Custódia transferida ao cliente. **Terminal** — Operador (confirmação)
- `CANCELADA` — Reservas liberadas, com motivo. **Terminal** — Operador

## Requisitos Funcionais

### Cadastros Base

- **ISC-RF-01:** O operador deve poder criar, editar e desativar Agentes, informando nome, CPF, telefone, e-mail opcional e endereço completo (logradouro, número, complemento, bairro, cidade, UF, CEP).
- **ISC-RF-02:** O sistema deve geocodificar automaticamente o endereço do agente ao salvar, obtendo latitude e longitude. Falha de geocodificação não impede o salvamento; o cadastro fica sinalizado como pendente de coordenada.
- **ISC-RF-03:** O operador deve poder ajustar manualmente a posição do agente arrastando o pin no mapa, sobrepondo o resultado da geocodificação. O ajuste manual é preservado até que o endereço seja alterado.
- **ISC-RF-04:** O operador deve poder criar, editar e desativar Clientes (nome ou razão social, documento, contato, endereço completo), com o mesmo comportamento de geocodificação e ajuste manual.
- **ISC-RF-05:** O operador deve poder criar, editar e desativar Modelos de Equipamento (nome, fabricante, descrição, tipo `DESCARTAVEL` ou `RETORNAVEL`).
- **ISC-RF-06:** O sistema deve bloquear a alteração do tipo de um Modelo que já possua unidades com movimentação registrada.

### Entrada e Movimentação de Estoque

- **ISC-RF-07:** O operador deve poder registrar a entrada de unidades novas informando modelo, identificadores, custódia de destino (Depósito ou Agente) e, opcionalmente, nota fiscal e lote de referência.
- **ISC-RF-08:** A entrada deve aceitar lote: colagem de lista de identificadores (um por linha) ou informação de faixa sequencial com prefixo, quantidade e numeração inicial.
- **ISC-RF-09:** O sistema deve gerar identificador interno único quando a unidade não possuir identificador de fábrica.
- **ISC-RF-10:** O operador deve poder consultar uma unidade pelo identificador e visualizar modelo, custódia atual, estado e histórico completo de movimentações.
- **ISC-RF-11:** O operador deve poder transferir unidades entre custódias internas: Depósito ↔ Agente e Agente ↔ Agente.
- **ISC-RF-12:** O operador deve poder registrar baixa de unidades por `PERDA`, `AVARIA` ou `OBSOLESCENCIA`, com justificativa textual obrigatória.
- **ISC-RF-13:** O operador deve poder enviar unidades para manutenção e registrar o retorno da manutenção ao Depósito.
- **ISC-RF-14:** O operador deve poder estornar uma movimentação lançada por engano. O estorno gera novo registro que referencia o original; nenhum registro é apagado ou editado.
- **ISC-RF-15:** O sistema deve apresentar painel de saldo por Agente e por Modelo, discriminando total em custódia, disponível e reservado.

### Mapa e Busca por Proximidade

- **ISC-RF-16:** O sistema deve exibir mapa interativo com marcadores de todos os Agentes ativos com coordenada válida. O popup do marcador mostra nome, telefone e saldo disponível por modelo.
- **ISC-RF-17:** O operador deve poder buscar Agentes próximos a um Cliente informando raio em quilômetros, obtendo resultado ordenado por distância crescente com a distância exibida.
- **ISC-RF-18:** A busca deve permitir filtrar por Modelo de Equipamento e por quantidade mínima disponível.
- **ISC-RF-19:** Ao buscar a partir de uma Solicitação, o mapa deve destacar o marcador do Cliente e traçar linha até cada Agente candidato.
- **ISC-RF-20:** O resultado da busca deve aparecer também em tabela lateral, sincronizada com o mapa: selecionar a linha destaca o marcador e vice-versa.
- **ISC-RF-21:** O sistema deve listar separadamente os Agentes ativos sem coordenada válida, com aviso de que não participam da busca por proximidade.

### Solicitações e Atendimento

- **ISC-RF-22:** O operador deve poder abrir uma Solicitação informando Cliente, itens (Modelo + quantidade), observação e prazo desejado opcional.
- **ISC-RF-23:** O operador deve poder criar uma ou mais Atribuições numa Solicitação, cada uma vinculando um Agente e uma quantidade por Modelo.
- **ISC-RF-24:** A criação da Atribuição deve reservar as unidades correspondentes no saldo do Agente, tornando-as indisponíveis para outras Solicitações.
- **ISC-RF-25:** O sistema deve selecionar automaticamente as unidades a reservar por ordem de entrada em custódia (FIFO), permitindo ao operador escolher unidades específicas quando necessário.
- **ISC-RF-26:** O operador deve poder marcar uma Atribuição como `EM_ROTA`.
- **ISC-RF-27:** O operador deve poder confirmar a entrega de uma Atribuição, informando data e hora efetivas e o nome de quem recebeu. A confirmação transfere a custódia das unidades ao Cliente.
- **ISC-RF-28:** O operador deve poder cancelar uma Atribuição ou uma Solicitação inteira, com motivo obrigatório, liberando todas as reservas ativas.
- **ISC-RF-29:** O sistema deve gerar texto pronto da Atribuição (nome e endereço do Cliente, contato, modelo e quantidade, observação) com botão de cópia e link `wa.me` para o telefone do Agente. Sem integração de API e sem envio automático.
- **ISC-RF-30:** O sistema deve indicar, na Solicitação, a cobertura atual (quantidade atribuída sobre quantidade solicitada) por Modelo.

### Retornáveis

- **ISC-RF-31:** O sistema deve listar todas as unidades de modelo retornável em custódia de Cliente, com identificação do cliente, data da entrega e tempo em posse.
- **ISC-RF-32:** O operador deve poder registrar o retorno de unidades retornáveis, indicando custódia de destino (Agente ou Depósito) e data efetiva.
- **ISC-RF-33:** O sistema deve sinalizar unidades retornáveis em posse de cliente há mais de N dias, sendo N parâmetro global configurável pelo Superusuário.

### Histórico e Relatórios

- **ISC-RF-34:** O sistema deve oferecer extrato de movimentações com filtros combináveis por período, Agente, Cliente, Modelo, tipo de movimentação e identificador de unidade.
- **ISC-RF-35:** O sistema deve oferecer histórico consolidado por Agente: entradas recebidas, entregas realizadas, retornos, baixas e saldo atual.
- **ISC-RF-36:** O sistema deve oferecer histórico consolidado por Cliente: unidades recebidas, unidades retornáveis ainda em posse e retornos efetuados.
- **ISC-RF-37:** O operador deve poder exportar qualquer extrato em CSV, respeitando os filtros aplicados.
- **ISC-RF-38:** O sistema deve apresentar dashboard operacional com: total de unidades por estado, saldo total em campo, solicitações abertas, retornáveis em posse de cliente e agentes com saldo abaixo de limite configurável.

## Requisitos Não Funcionais

- **Plataforma:** Aplicação web responsiva, servida pelo GSInt. Suportar Chrome, Edge, Firefox e Safari nas duas últimas versões principais.
- **Performance:** Páginas de listagem devem carregar em menos de 2 segundos. A busca por proximidade deve responder em menos de 1 segundo para uma base de até 1.000 agentes. O cálculo de saldo derivado deve responder em menos de 500ms por agente para até 100.000 movimentações registradas.
- **Mapa:** Renderização de até 500 marcadores simultâneos sem degradação perceptível de interação.
- **Escalabilidade MVP:** 100 agentes ativos, 5.000 unidades em circulação, 200 solicitações/mês, 100.000 movimentações acumuladas ao longo de dois anos, sem degradação.
- **Concorrência:** Duas reservas simultâneas sobre o mesmo saldo nunca podem alocar a mesma unidade. A operação de reserva é atômica.
- **Integridade:** O saldo apresentado é sempre reproduzível a partir do log de movimentações. Não existe caminho no sistema que altere custódia sem gerar registro.
- **Segurança:** Autenticação e sessão herdadas do GSInt. Acesso restrito ao grupo de operadores. CSRF e proteção de rotas por decorator de permissão.
- **LGPD:** CPF de agente e documento de cliente são dados pessoais. Armazenados com acesso restrito, exibidos mascarados em listagens. Log de acesso a dados sensíveis.
- **Auditoria:** Toda operação de escrita (cadastro, movimentação, atribuição, confirmação, cancelamento, baixa, estorno) registra autor, momento e conteúdo alterado. Movimentações são imutáveis por definição.
- **Disponibilidade:** Herdada do GSInt.
- **Compatibilidade mobile:** A interface deve ser plenamente funcional a partir de 360px de largura — o operador frequentemente registra confirmações fora da mesa.

## Jornada Principal do Atendimento

1. **Abastecimento:** O operador registra a entrada de um lote de iscas novas no Depósito, colando a lista de identificadores. Em seguida transfere parte das unidades para os agentes, gerando uma movimentação Depósito → Agente para cada transferência. O saldo de cada agente passa a refletir o log.

2. **Solicitação:** Um cliente entra em contato por canal externo pedindo 20 iscas de um modelo. O operador registra a Solicitação vinculada ao Cliente, com o item e a quantidade. Status: `ABERTA`.

3. **Busca no mapa:** O operador aciona a busca por proximidade a partir da Solicitação. O mapa centraliza no endereço do cliente e exibe os agentes num raio de 50km, ordenados por distância, com o saldo disponível de cada um para aquele modelo. O agente mais próximo tem 12 disponíveis; o segundo tem 8.

4. **Atribuição:** O operador cria duas Atribuições — 12 unidades com o primeiro agente, 8 com o segundo. O sistema reserva as unidades específicas em cada saldo. A Solicitação passa a `ATRIBUIDA` com cobertura total (20 de 20). As unidades reservadas ficam indisponíveis para qualquer outra solicitação.

5. **Comunicação:** O operador copia o texto pronto de cada Atribuição e envia pelo WhatsApp aos dois agentes, com endereço do cliente, quantidade e contato. O sistema não envia nada — apenas monta a mensagem.

6. **Rota:** Conforme cada agente confirma que saiu, o operador marca a Atribuição correspondente como `EM_ROTA`.

7. **Entrega:** Cada agente avisa que entregou. O operador confirma a entrega de cada Atribuição informando data, hora e quem recebeu. O sistema gera a movimentação Agente → Cliente para cada conjunto de unidades. O saldo do primeiro agente cai de 12 para 0; o do segundo, de 8 para 0. Quando a última Atribuição é confirmada, a Solicitação vai a `ENTREGUE`.

8. **Destino das unidades:** Sendo o modelo descartável, as 20 unidades entram em estado `CONSUMIDA` e saem do estoque em definitivo. Sendo retornável, ficam em estado `COM_CLIENTE`, aparecendo na lista de retornáveis em posse com contagem de dias.

9. **Retorno (só retornáveis):** Semanas depois, o cliente devolve as iscas. O operador registra o retorno indicando se voltaram para um agente ou para o Depósito. As unidades retornam ao saldo disponível da custódia de destino, com o histórico completo preservado.

## Métricas de Sucesso

- 100% das mudanças de custódia possuem movimentação correspondente com autor e momento identificados — verificável por reconciliação entre estado das unidades e log.
- Divergência entre saldo em sistema e contagem física de um agente amostrado ≤ 2%.
- Tempo médio entre abertura da Solicitação e criação da primeira Atribuição < 10 minutos.
- Zero casos de dupla alocação da mesma unidade em solicitações distintas (verificado em teste de concorrência).
- 100% dos agentes ativos com coordenada válida em até 30 dias após a implantação.
- Redução do tempo de resposta "quem está perto e tem saldo?" de contato telefônico para consulta de tela.
- Taxa de retorno de iscas retornáveis ≥ 90% em até 90 dias da entrega.

## Premissas e Riscos

- **Premissa:** O endereço cadastral do agente é uma aproximação aceitável da posição dele no momento do atendimento. Se a operação passar a exigir posição real, o modelo de coordenadas precisará evoluir para histórico posicional — o que altera o dimensionamento de dados, não a estrutura do estoque.
- **Premissa:** A geocodificação automática por serviço público terá taxa de acerto imperfeita para endereços brasileiros. O ajuste manual do pin não é recurso auxiliar: é parte obrigatória do fluxo de cadastro.
- **Risco:** O GSInt é o monólito legado, previsto para ser substituído pelo HubSAT. Construir um app novo nele implica migração futura. A mitigação é de fronteira: o Iscas Fast não depende de nenhum outro app do GSInt além da autenticação, mantém todo o domínio dentro do próprio app e não é dependido por ninguém. Isso reduz a migração a mover um app isolado, e não a desemaranhar acoplamentos.
- **Risco:** A comunicação com o agente ficando fora do sistema, o momento real da entrega depende de o operador ser avisado e registrar. Atraso de registro produz saldo temporariamente defasado. Mitigação de produto: a lista de atribuições em `EM_ROTA` há mais de X horas fica visível no dashboard como pendência.

---
name: painel-lancamentos-clickup
description: Cria o "Painel de Projetos de Lançamentos" da Exos no ClickUp dentro do workspace de um cliente (cross-workspace), a partir de um template fixo de 9 widgets (Projetos em Andamento, Marcos Andamento, Em Atraso, Copywriter, Criação e Designer, Páginas, Agendamento e Disparos, Gestão de Campanha, Metas). Como dashboards NÃO têm API pública nem cópia entre workspaces, a skill recria o painel via API interna (frontdoor) numa sessão de navegador autenticada (Playwright), repontando cada widget para as listas equivalentes do workspace de destino, resolvidas por nome. Use SEMPRE que o usuário pedir para criar/replicar/montar o painel (dashboard) de lançamentos para um cliente em OUTRO workspace — gatilhos: "cria o painel de lançamentos no workspace do cliente", "monta o dashboard de lançamentos pra Telesapiens", "replica o painel de projetos de lançamentos pro workspace X", "quero o painel de acompanhamento do lançamento no workspace do cliente", "monta o painel de lançamentos do cliente novo". Não confundir com `duplicar-projeto-clickup` (que cria as TAREFAS/listas do projeto) — esta skill cria só o PAINEL de acompanhamento.

---

# Painel de Projetos de Lançamentos (ClickUp · cross-workspace)

Recria o painel de acompanhamento de lançamentos da Exos no **workspace de um cliente**. O painel tem
**9 widgets** num grid de 12 colunas (definição fixa em [assets/template_lancamentos.json](assets/template_lancamentos.json)):

| Coluna | Widgets |
|---|---|
| Esquerda (números) | Projetos em Andamento · Marcos Andamento · Em Atraso |
| Centro | Copywriter · Gestão de Campanha (pizza por status) |
| Centro-dir. | Criação e Designer · Agendamento e Disparos (pizza) |
| Direita | Páginas (pizza) · Metas (Goals) |

## Por que não é "só duplicar" (leia antes)

- **Dashboards não têm API pública** (nem MCP): não dá pra ler/criar painel via `api.clickup.com`.
- A **UI não copia painel entre workspaces**. Por isso recriamos via **API interna `frontdoor`**,
  autenticada pela **sessão do navegador** (Playwright). Detalhes do schema/auth em
  [references/frontdoor_api.md](references/frontdoor_api.md).
- As fontes de dados (listas) e os filtros por **custom field** (Cliente/Evento) são **por-workspace**.
  No destino as listas têm **outros IDs** (casadas por nome) e os campos Cliente/Evento **não existem**
  — então os widgets nascem com filtros **genéricos** (status/overdue) e são refinados depois.

## Pré-requisitos

- **Workspace de destino** já com a estrutura de listas do padrão Exos (normalmente criada antes pela
  skill `duplicar-projeto-clickup`): listas de processo (Copywriting, Design & Criação, Produção de
  Páginas, Agendamentos…, Gestão de Campanhas), o card-painel `Painel Projeto Lançamentos` e as 8
  listas de fase (Concepção→Pós Venda). Sem elas, alguns widgets ficam sem fonte (a skill avisa).
- **Token REST** no Keychain (só para resolver listas por nome): `clickup-exos-api`.
- **Playwright** com sessão ClickUp logada (se abrir deslogado, peça o login 1×).

## Entradas (peça o que faltar)

1. **Workspace de destino** (ID ou nome do cliente). Ex.: Telesapiens `90171059720`.
2. **Nome do cliente** para o título do painel → `Lançamentos - <Cliente>` (confirme/ajuste).

## Fluxo

### 1) Resolver as listas do destino (read-only)
```bash
CLICKUP_TOKEN=$(security find-generic-password -s clickup-exos-api -w) \
  python3 scripts/resolve_lists.py --workspace <WS_DESTINO> \
    --template assets/template_lancamentos.json --out /tmp/list_map.json
```
Confira o resumo. Todo role (menos `metas`) deve ter ao menos 1 lista. Roles vazios = ajustar nomes/
estrutura no destino antes de seguir. **Mostre o mapeamento ao usuário e confirme.**

### 2) Montar os payloads dos 9 widgets
```bash
python3 scripts/build_payloads.py --template assets/template_lancamentos.json \
  --list-map /tmp/list_map.json --out /tmp/payloads.json
```

### 3) Criar o painel vazio no workspace de destino (Playwright)
- `browser_navigate` → `https://app.clickup.com/<WS_DESTINO>/hubs/dashboards` (logue se preciso).
- Clique **Novo painel** (`[data-test="hub-create-menu__create-button"]`) → **Começar do zero**.
- A URL vira `…/dashboards/<DASH_ID>` — **guarde o `DASH_ID`**.

### 4) Capturar host + token da sessão
- `browser_network_requests` (filtro `frontdoor.*dashboard/<DASH_ID>`) → identifique o **host**
  (`frontdoor-prod-<região>`). `browser_network_request` no GET/POST → `request-headers` → copie o
  `authorization: Bearer …` e confirme `x-workspace-id`. (Não imprima o token.)

### 5) Criar os widgets + aplicar layout (uma chamada)
- Use o snippet **recriar.js** de [references/frontdoor_api.md](references/frontdoor_api.md) em
  `browser_evaluate`, preenchendo `DASH`, `HOST`, `TOKEN`, `WS`, `NAME` e colando o array de
  `/tmp/payloads.json` em `PAYLOADS`. Ele faz POST dos 9 widgets, coleta os ids e aplica o
  `widget_layout` (grid exato) + renomeia o painel num único PUT. Confira o retorno (9 posts 200 +
  layout 200).

### 6) Verificar
- `browser_navigate` no painel, aguarde, **screenshot**. Confirme 9 widgets, títulos e posições.
  Opcional: GET `…/dashboard/<DASH_ID>` para checar `widget.length === 9` e os tipos.

## Pós-criação (informe o usuário)

- **Filtros Cliente/Evento** não foram aplicados (campos não existem no destino). Os widgets contam
  **todas** as tarefas das listas-alvo. Se o cliente tiver um campo de segmentação, edite cada widget
  e adicione o filtro.
- **Metas** fica "Nenhum resultado" até o workspace ter Goals.
- O painel é criado **privado** (do criador). Use **Compartilhar** no ClickUp para liberar ao time.

## Regras

- **Nunca** crie listas/pastas no destino — a skill só lê e casa por nome. Se faltar estrutura, avise e
  aponte a `duplicar-projeto-clickup`.
- **Sempre confirme** o `list_map` e o nome do painel com o usuário antes do passo 5 (escrita).
- Token de sessão é sensível: **nunca** imprima/grave o Bearer.
- IDs e o caso de referência (Telesapiens "Lançamentos - Multifaculdade") estão na memória
  `reference_clickup_dashboard_replicar`.

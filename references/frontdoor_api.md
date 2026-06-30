# API interna de Dashboards do ClickUp (frontdoor) — referência

Dashboards (painéis) **não têm endpoint na API pública** do ClickUp (nem no MCP `clickup`): não dá
para ler nem criar painel via `api.clickup.com/api/v2`. A UI também **não copia painel entre
workspaces**. A recriação usa a **API interna `frontdoor`** que o próprio app web chama — autenticada
pela sessão do navegador. Por isso esta skill depende do **Playwright** (sessão logada), e os
POST/PUT são feitos com `browser_evaluate(fetch)` de dentro da página autenticada.

## Endpoints

| Ação | Método | URL |
|---|---|---|
| Ler definição | GET | `https://frontdoor-prod-<REGIÃO>.clickup.com/dashboard/{dash_id}` |
| Criar widget | POST | `https://frontdoor-prod-<REGIÃO>.clickup.com/dashboard/{dash_id}/widget` |
| Salvar layout / renomear | PUT | `https://frontdoor-prod-<REGIÃO>.clickup.com/dashboard/{dash_id}` |

- A **REGIÃO** do host varia (ex.: `us-west-2-3`, `us-east-2-1`). **Use o mesmo host das requisições
  que já funcionam na página** — pegue de `browser_network_requests` (filtro `frontdoor.*dashboard`).
  Host errado → 400.

## Autenticação (capturar da própria página)

Pegue de uma requisição real bem-sucedida (`browser_network_request` → `request-headers`) e reutilize:

- `authorization: Bearer <jwt-do-workspace>` — JWT específico do workspace (tem `workspace_id` dentro;
  expira em ~horas). **Capture na hora, no workspace de destino.**
- `x-csrf: 1`
- `x-workspace-id: <id do workspace de destino>`
- `content-type: application/json`

> Nunca logar/imprimir o token. Ele é de sessão.

## Schema do corpo (POST widget)

Gerado pelo `build_payloads.py`. Campos principais:
`{ title, type, cols, rows, location:[{id,type:"subcategory"}], pre_made, filters,
   calculation?, group_by, x_axis, y_axis, include_subtasks, show_empty_field, cf_filter, maximumCards }`

- `type`: **3** = pizza por status (`pre_made:"statuses_pie_tasks"`); **16** = cálculo/número
  (`custom_calculation` ou `statuses_calc_open_tasks`, com `calculation:{field,func,unit,unit_side}`);
  **20** = Metas/Goals (`pre_made:"goal"`, `location:[]`).
- `location` `type:"subcategory"` = lista; `"category"` = pasta.

## Schema do PUT (layout + nome)

`{ name, filters, auto_refresh_enabled, auto_layout:false, widget_layout:[{widget_id,x,y,cols,rows}],
   private }`. Mande **todos** os widgets em `widget_layout` com as coordenadas do template; com
`auto_layout:false` as posições são respeitadas (grid de 12 colunas).

## Snippet reutilizável (recriar.js)

Cole como função em `browser_evaluate`, preenchendo `DASH`, `TOKEN`, `HOST` (capturados) e
`PAYLOADS` (conteúdo de `payloads.json`) e `NAME` (nome do painel). Faz POST de cada widget, coleta
os ids **na ordem** e aplica o layout num único PUT. Retorna um resumo para conferência.

```js
async () => {
  const DASH = "<dash_id>";
  const HOST = "https://frontdoor-prod-us-west-2-3.clickup.com"; // use o host real da sessão
  const TOKEN = "Bearer <jwt>";                                  // capturado dos headers
  const WS = "<workspace_id_destino>";
  const NAME = "Lançamentos - <Cliente>";
  const PAYLOADS = /* cole o array de payloads.json aqui */ [];
  const H = { authorization: TOKEN, "content-type": "application/json",
              "x-csrf": "1", "x-workspace-id": WS, accept: "application/json, text/plain, */*" };
  const created = [];
  for (const p of PAYLOADS) {
    const r = await fetch(`${HOST}/dashboard/${DASH}/widget`,
      { method: "POST", headers: H, credentials: "include", body: JSON.stringify(p.body) });
    let b = null; try { b = await r.json(); } catch (e) {}
    created.push({ title: p.title, status: r.status, id: b && b.id, layout: p.layout });
  }
  const widget_layout = created.filter(c => c.id).map(c =>
    ({ widget_id: c.id, x: c.layout.x, y: c.layout.y, cols: c.layout.cols, rows: c.layout.rows }));
  const put = await fetch(`${HOST}/dashboard/${DASH}`, { method: "PUT", headers: H, credentials: "include",
    body: JSON.stringify({ name: NAME,
      filters: { search: "", show_closed: false, op: "AND", filter_group_ops: [], filter_groups: [], fields: [] },
      auto_refresh_enabled: true, auto_layout: false, widget_layout, private: true,
      is_quick_action_bar_visible: null, is_apply_template_bar_visible: null }) });
  return { posts: created.map(c => ({ t: c.title, s: c.status, id: c.id })),
           layout_status: put.status, n_layout: widget_layout.length };
}
```

## Verificação

Reabra `…/dashboards/{dash_id}`, espere o carregamento e tire screenshot. Confira: 9 widgets,
títulos certos, posições conforme o template, e que as pizzas/contagens mostram dados (se as listas
de destino já tiverem tarefas). GET `…/dashboard/{dash_id}` confirma `widget.length === 9` e os tipos.

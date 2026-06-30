#!/usr/bin/env python3
"""
build_payloads.py — Monta os corpos de criação dos 9 widgets a partir do template + list_map.

Saída: payloads.json = lista (na ordem do template) de objetos:
  { "title", "body": {<corpo do POST /dashboard/{id}/widget>}, "layout": {x,y,cols,rows} }

O corpo segue o schema da API interna (frontdoor) capturado do próprio app. O snippet de
navegador (references/frontdoor_api.md → recriar.js) faz o POST de cada body, coleta o widget_id
retornado e, na MESMA ordem, monta o widget_layout para o PUT final de layout.

Filtros: genéricos só (status aberto / overdue). Os filtros por custom field Cliente/Evento da
origem NÃO entram — esses campos são por-workspace e não existem no destino. Ajuste manual depois.

Uso:
  python3 build_payloads.py --template ../assets/template_lancamentos.json \
    --list-map list_map.json --out payloads.json
"""
import argparse, json, os, sys

STATUS_OPEN = {"field": "status", "op": "EQ", "idx": 0,
               "values": [{"type": "unstarted"}, {"type": "active"}]}
DUEDATE_OVERDUE = {"field": "dueDate", "op": "EQ", "idx": 1, "values": [{"op": "overdue"}]}


def build_filters(spec):
    fields = []
    if spec.get("status_open"):
        fields.append(dict(STATUS_OPEN))
    if spec.get("overdue"):
        f = dict(DUEDATE_OVERDUE)
        f["idx"] = len(fields)
        fields.append(f)
    return {"fields": fields, "op": "AND", "show_closed": bool(spec.get("status_open"))}


def build_body(w, list_ids):
    location = [{"id": str(i), "type": "subcategory"} for i in list_ids]
    body = {
        "title": w["title"],
        "type": w["type"],
        "cols": w["cols"],
        "rows": w["rows"],
        "location": location,
        "group_by": {"type": None},
        "x_axis": {"unit": "status"} if w["type"] == 3 else {},
        "y_axis": {"unit": "tasks"} if w["type"] == 3 else {},
        "filters": build_filters(w.get("filters", {})),
        "include_subtasks": True,
        "show_empty_field": False,
        "pre_made": w["pre_made"],
        "cf_filter": {"id": None},
        "maximumCards": 100,
    }
    if "calculation" in w:
        body["calculation"] = w["calculation"]
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default=os.path.join(os.path.dirname(__file__), "..", "assets", "template_lancamentos.json"))
    ap.add_argument("--list-map", required=True)
    ap.add_argument("--out", default="payloads.json")
    args = ap.parse_args()

    tpl = json.load(open(args.template, encoding="utf-8"))
    lm = json.load(open(args.list_map, encoding="utf-8"))

    payloads, warnings = [], []
    for w in tpl["widgets"]:
        lr = w.get("location_role")
        list_ids = [] if lr is None else lm.get(lr, [])
        if lr is not None and not list_ids:
            warnings.append(f"{w['title']} (role {lr}) sem listas no list_map — widget ficará sem fonte.")
        payloads.append({
            "title": w["title"],
            "body": build_body(w, list_ids),
            "layout": {"x": w["x"], "y": w["y"], "cols": w["cols"], "rows": w["rows"]},
        })

    json.dump(payloads, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(payloads)} widgets montados -> {args.out}")
    for w in warnings:
        print("  [ATENÇÃO]", w)
    if not warnings:
        print("  todas as fontes resolvidas (exceto Metas, que não usa lista).")


if __name__ == "__main__":
    main()

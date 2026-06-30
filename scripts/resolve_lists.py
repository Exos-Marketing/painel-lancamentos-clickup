#!/usr/bin/env python3
"""
resolve_lists.py — Resolve as listas equivalentes do workspace de DESTINO por NOME.

Os IDs de lista mudam por workspace; o que é estável é o NOME (padrão Exos: Copywriting,
Design & Criação, Produção de Páginas, Agendamentos…, Gestão de Campanhas, Painel Projeto
Lançamentos, e as 8 listas de fase Concepção→Pós Venda). Este script lê a hierarquia do
workspace destino via API REST (token do Keychain) e casa cada `role` do template com os
IDs reais, gerando um list_map.json para o build_payloads.py.

Uso:
  CLICKUP_TOKEN=$(security find-generic-password -s clickup-exos-api -w) \
    python3 resolve_lists.py --workspace 90171059720 \
      --template ../assets/template_lancamentos.json --out list_map.json

Saída: list_map.json = { "<role>": ["<list_id>", ...], ... } + um resumo legível no stdout.
Roles sem match aparecem com lista vazia e um aviso — NÃO inventa IDs.
"""
import argparse, json, os, sys, unicodedata, urllib.request, urllib.error

API = "https://api.clickup.com/api/v2"


def norm(s):
    """minúsculas + sem acentos + espaços colapsados, p/ casar nomes com tolerância."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def http_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": token})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"[ERRO] GET {url} -> {e.code} {e.read()[:200]}", file=sys.stderr)
        raise


def collect_lists(token, workspace):
    """Retorna [(list_id, list_name, space_name, folder_name)] de todo o workspace."""
    out = []
    spaces = http_get(f"{API}/team/{workspace}/space?archived=false", token).get("spaces", [])
    for sp in spaces:
        spn = sp["name"]
        # listas em pastas
        folders = http_get(f"{API}/space/{sp['id']}/folder?archived=false", token).get("folders", [])
        for f in folders:
            for l in f.get("lists", []):
                out.append((l["id"], l["name"], spn, f["name"]))
        # listas sem pasta
        fl = http_get(f"{API}/space/{sp['id']}/list?archived=false", token).get("lists", [])
        for l in fl:
            out.append((l["id"], l["name"], spn, None))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, help="ID do workspace de DESTINO (cliente)")
    ap.add_argument("--template", default=os.path.join(os.path.dirname(__file__), "..", "assets", "template_lancamentos.json"))
    ap.add_argument("--out", default="list_map.json")
    args = ap.parse_args()

    token = os.environ.get("CLICKUP_TOKEN")
    if not token:
        print("[ERRO] defina CLICKUP_TOKEN (Keychain: security find-generic-password -s clickup-exos-api -w)", file=sys.stderr)
        sys.exit(2)

    tpl = json.load(open(args.template, encoding="utf-8"))
    roles = tpl["list_roles"]

    lists = collect_lists(token, args.workspace)
    by_norm = {}
    for lid, name, spn, fn in lists:
        by_norm.setdefault(norm(name), []).append((lid, name, spn, fn))

    result = {}
    print(f"\nWorkspace {args.workspace}: {len(lists)} listas encontradas.\n")
    for role, patterns in roles.items():
        ids, hits = [], []
        for pat in patterns:
            np = norm(pat)
            # match exato; se não houver, match por 'contém'
            cands = by_norm.get(np) or [t for k, v in by_norm.items() if np in k for t in v]
            for lid, name, spn, fn in cands:
                if lid not in ids:
                    ids.append(lid)
                    hits.append(f"{name} ({spn}{'/'+fn if fn else ''})")
        result[role] = ids
        flag = "OK " if ids else "!! "
        print(f"  {flag}{role:18} -> {len(ids)} lista(s): {', '.join(hits) if hits else 'NENHUMA (revisar nomes/estrutura no destino)'}")

    missing = [r for r, ids in result.items() if not ids]
    json.dump(result, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nlist_map salvo em {args.out}.")
    if missing:
        print(f"[ATENÇÃO] roles sem lista: {', '.join(missing)}. O widget de Metas ('metas') é "
              f"esperado vazio (não usa lista). Os demais precisam de ajuste antes de seguir.")


if __name__ == "__main__":
    main()

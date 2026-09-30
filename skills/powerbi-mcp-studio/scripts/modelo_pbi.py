"""
modelo_pbi.py - Auditoria, dicionario e checklist de publicacao de um modelo Power BI.
Parte da skill powerbi-mcp-studio. Somente leitura.

Entrada: o modelo exportado pelo MCP (database_operations -> ExportToBimFile) e, opcionalmente,
o relatorio (.pbix/.pbip) para saber o que os visuais usam.

Uso:
    python modelo_pbi.py auditoria  --bim modelo.bim --pbix Relatorio.pbix --saida auditoria.md
    python modelo_pbi.py dicionario --bim modelo.bim --pbix Relatorio.pbix --saida dicionario.md
    python modelo_pbi.py checklist  --bim modelo.bim --pbix Relatorio.pbix     -> gera as consultas DAX de conferencia

Sem --pbix a auditoria nao consegue dizer o que esta "sem uso" (so o que tem erro/risco).
"""
import json, re, sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


# ------------------------------------------------------------------ leitura
def carregar_bim(caminho):
    d = json.loads(Path(caminho).read_text(encoding="utf-8-sig"))
    return d.get("model", d)


def texto(expr):
    if isinstance(expr, list):
        return "\n".join(expr)
    return expr or ""


def objetos(m):
    medidas, colunas = [], []
    for t in m.get("tables", []):
        for x in t.get("measures", []):
            medidas.append(dict(x, tabela=t["name"], expressao=texto(x.get("expression"))))
        for x in t.get("columns", []):
            if x.get("type") == "rowNumber":
                continue
            colunas.append(dict(x, tabela=t["name"], expressao=texto(x.get("expression"))))
    return medidas, colunas


REF_COL = re.compile(r"(?:'([^']+)'|\b([A-Za-z_][\w]*))\s*\[([^\]]+)\]")
REF_MED = re.compile(r"(?<![\w'\]])\[([^\]]+)\]")


def dependencias(expr, nomes_medidas):
    """(medidas referenciadas, colunas referenciadas) - heuristica por regex sobre o DAX."""
    sem_str = re.sub(r'"(?:[^"]|"")*"', '""', expr)
    sem_com = re.sub(r"//[^\n]*|--[^\n]*|/\*.*?\*/", "", sem_str, flags=re.S)
    cols = {( (a or b), c) for a, b, c in REF_COL.findall(sem_com)}
    meds = set()
    for n in REF_MED.findall(sem_com):
        if n in nomes_medidas:
            meds.add(n)
    return meds, cols


def usados_relatorio(pbix):
    if not pbix:
        return None
    from inventario_pbi import inventario
    from pbi_arquivo import Relatorio
    inv = inventario(Relatorio(pbix))
    usados = set()
    for p in inv["paginas"]:
        for v in p["visuais"]:
            usados |= {(t, n) for _, t, n in v["campos"]}
        usados |= {(t, n) for _, t, n in p["filtros"]}
    usados |= {(t, n) for _, t, n in inv["filtros_relatorio"]}
    return usados, inv


# ------------------------------------------------------------------ regras
PADROES_RISCO = [
    (r"\bFILTER\s*\(\s*(?:'[^']+'|[A-Za-z_]\w*)\s*,", "FILTER sobre a tabela inteira - prefira filtro de coluna (KEEPFILTERS/condicao simples no CALCULATE)"),
    (r"\bIFERROR\s*\(|\bISERROR\s*\(", "IFERROR/ISERROR - costuma esconder erro e custa desempenho; prefira DIVIDE ou testes explicitos"),
    (r"(?<!DIVIDE)\s/\s*(?:\[|\()", "divisao com '/' - prefira DIVIDE() (trata zero/blank)"),
    (r"\b(SUMX|AVERAGEX|COUNTX|MAXX|MINX)\s*\(\s*(?:'[^']+'|[A-Za-z_]\w*)\s*,[^)]*\b(SUMX|AVERAGEX|COUNTX|FILTER)\s*\(", "iteradores aninhados sobre tabelas - risco de lentidao"),
    (r"\bVALUES\s*\([^)]*\)\s*\)\s*=", "comparacao com VALUES() - use SELECTEDVALUE"),
]


def auditoria(m, uso):
    medidas, colunas = objetos(m)
    nomes_med = {x["name"] for x in medidas}
    achados = defaultdict(list)

    # 1. erros
    for x in medidas + colunas:
        st = (x.get("state") or "ready").lower()
        if st not in ("ready", "valid"):
            tipo = "Medida" if x in medidas else "Coluna"
            achados["Erros (quebram o refresh ou os visuais)"].append(
                f"{tipo} `{x['tabela']}[{x['name']}]` - {x.get('errorMessage') or st}")

    # 2. relacoes
    for r in m.get("relationships", []):
        desc = f"`{r['fromTable']}[{r['fromColumn']}]` -> `{r['toTable']}[{r['toColumn']}]`"
        if r["name"].startswith("AutoDetected"):
            achados["Relacoes"].append(f"{desc}: criada automaticamente pelo Desktop - confirme se a chave esta certa (chaves compostas quebram com duplicados)")
        if r.get("crossFilteringBehavior") == "bothDirections":
            achados["Relacoes"].append(f"{desc}: filtro bidirecional - pode gerar ambiguidade e lentidao; use so se necessario")
        if r.get("toCardinality") == "many" and r.get("fromCardinality", "many") == "many":
            achados["Relacoes"].append(f"{desc}: muitos-para-muitos - confirme se nao falta uma tabela dimensao")
        if r.get("isActive") is False:
            achados["Relacoes"].append(f"{desc}: inativa - so funciona com USERELATIONSHIP")

    # 3. sem uso
    if uso is not None:
        usados, _ = uso
        grafo = {x["name"]: dependencias(x["expressao"], nomes_med) for x in medidas}
        vivos, fila = set(), [n for t, n in usados if n in nomes_med]
        cols_vivas = {(t, n) for t, n in usados}
        while fila:
            n = fila.pop()
            if n in vivos:
                continue
            vivos.add(n)
            meds, cols = grafo.get(n, (set(), set()))
            fila += list(meds)
            cols_vivas |= cols
        for x in colunas:
            if x.get("type") == "calculated":
                meds, cols = dependencias(x["expressao"], nomes_med)
                cols_vivas |= cols
        rel_cols = {(r["fromTable"], r["fromColumn"]) for r in m.get("relationships", [])} | \
                   {(r["toTable"], r["toColumn"]) for r in m.get("relationships", [])}
        sort_by = {(x["tabela"], x["sortByColumn"]) for x in colunas if x.get("sortByColumn")}
        for x in medidas:
            if x["name"] not in vivos:
                achados["Medidas sem uso (nem em visuais, nem por outras medidas usadas)"].append(f"`{x['tabela']}[{x['name']}]`")
        for x in colunas:
            k = (x["tabela"], x["name"])
            if x.get("type") == "calculated" and k not in cols_vivas and k not in rel_cols and k not in sort_by:
                achados["Colunas calculadas sem uso"].append(f"`{x['tabela']}[{x['name']}]`")

    # 4. boas praticas
    for x in medidas:
        e = x["expressao"]
        for pad, msg in PADROES_RISCO:
            if re.search(pad, e, flags=re.I | re.S):
                achados["Padroes de risco no DAX (desempenho/robustez)"].append(f"`{x['name']}`: {msg}")
        if not x.get("formatString") and not x.get("formatStringDefinition") and x.get("dataType") not in ("string",) \
                and not re.search(r"HTML|SVG|txt|texto|cor|color", x["name"], re.I):
            achados["Documentacao e formato"].append(f"`{x['name']}`: sem formato definido")
    sem_desc = [x["name"] for x in medidas if not x.get("description")]
    if sem_desc:
        achados["Documentacao e formato"].append(f"{len(sem_desc)} de {len(medidas)} medidas sem descricao")
    visiveis_fato = [x for x in colunas if not x.get("isHidden") and re.search(r"(^id|_id$|^cd_|^sk_|key$)", x["name"], re.I)]
    for x in visiveis_fato[:15]:
        achados["Documentacao e formato"].append(f"`{x['tabela']}[{x['name']}]`: parece chave tecnica e esta visivel - considere ocultar")
    calendarios = [t for t in m.get("tables", []) if t.get("dataCategory") == "Time"]
    if not calendarios:
        achados["Documentacao e formato"].append("nenhuma tabela marcada como tabela de datas (Marcar como tabela de datas)")
    if (m.get("annotations") and any(a.get("name") == "__PBI_TimeIntelligenceEnabled" and a.get("value") == "1" for a in m["annotations"])):
        achados["Documentacao e formato"].append("Data/hora automatica ligada - cria tabelas ocultas; desligue se ja existe calendario")
    return achados, medidas, colunas


def md_auditoria(achados, m, medidas, colunas, uso, origem):
    total = sum(len(v) for v in achados.values())
    pesos = {"Erros (quebram o refresh ou os visuais)": 10, "Relacoes": 3}
    penal = sum(len(v) * pesos.get(k, 1) for k, v in achados.items())
    nota = max(0, 100 - penal)
    L = [f"# Auditoria do modelo", "", f"Origem: {origem} - gerado em {date.today():%d/%m/%Y}", "",
         f"**Nota: {nota}/100** - {total} achado(s). Tabelas: {len(m.get('tables', []))}, medidas: {len(medidas)}, "
         f"colunas: {len(colunas)}, relacoes: {len(m.get('relationships', []))}.", ""]
    if uso is None:
        L += ["> Sem o relatorio (--pbix), a analise de itens sem uso nao foi feita.", ""]
    ordem = ["Erros (quebram o refresh ou os visuais)", "Relacoes", "Medidas sem uso (nem em visuais, nem por outras medidas usadas)",
             "Colunas calculadas sem uso", "Padroes de risco no DAX (desempenho/robustez)", "Documentacao e formato"]
    for k in ordem + [k for k in achados if k not in ordem]:
        if achados.get(k):
            L += [f"## {k} ({len(achados[k])})", ""] + [f"- {i}" for i in achados[k]] + [""]
    L += ["## Como tratar", "",
          "- Erros: corrigir ou excluir (confirmar com o dono do relatorio antes de excluir).",
          "- Sem uso: confirmar que nao ha outro relatorio conectado a este modelo antes de apagar.",
          "- Relacoes: validar a chave com uma consulta de duplicados antes de mudar cardinalidade.",
          "- A nota e indicativa: erros pesam 10, relacoes 3, demais 1."]
    return "\n".join(L)


def md_dicionario(m, medidas, colunas, uso, origem):
    usados = uso[0] if uso else set()
    L = [f"# Dicionario do modelo", "", f"Origem: {origem} - gerado em {date.today():%d/%m/%Y}", ""]
    L += ["## Tabelas", "", "| Tabela | Tipo | Colunas | Medidas | Oculta |", "|---|---|---|---|---|"]
    for t in m.get("tables", []):
        tipo = ",".join(sorted({(p.get("source") or {}).get("type", "?") for p in t.get("partitions", [])})) or "-"
        L.append(f"| {t['name']} | {tipo} | {len(t.get('columns', []))} | {len(t.get('measures', []))} | {'sim' if t.get('isHidden') else ''} |")
    L += ["", "## Relacionamentos", "", "| De | Para | Cardinalidade | Filtro | Ativa |", "|---|---|---|---|---|"]
    for r in m.get("relationships", []):
        L.append(f"| {r['fromTable']}[{r['fromColumn']}] | {r['toTable']}[{r['toColumn']}] | "
                 f"{r.get('fromCardinality', 'many')}:{r.get('toCardinality', 'one')} | "
                 f"{'ambos' if r.get('crossFilteringBehavior') == 'bothDirections' else 'unico'} | {'nao' if r.get('isActive') is False else 'sim'} |")
    L += ["", "## Medidas", ""]
    for x in sorted(medidas, key=lambda x: (x["tabela"], x["name"])):
        usado = " - usada no relatorio" if (x["tabela"], x["name"]) in usados else ""
        L += [f"### {x['tabela']}[{x['name']}]{usado}", "",
              (x.get("description") or "_Sem descricao._"), "",
              f"Formato: `{x.get('formatString') or '-'}`" + (f" · Pasta: {x['displayFolder']}" if x.get("displayFolder") else ""), "",
              "```dax", x["expressao"].strip(), "```", ""]
    L += ["## Colunas", "", "| Tabela | Coluna | Tipo | Origem | Oculta |", "|---|---|---|---|---|"]
    for x in colunas:
        L.append(f"| {x['tabela']} | {x['name']} | {x.get('dataType', '')} | {'calculada' if x.get('type') == 'calculated' else 'dados'} | {'sim' if x.get('isHidden') else ''} |")
    return "\n".join(L)


def checklist(m, uso):
    medidas, _ = objetos(m)
    usados = uso[0] if uso else set()
    meds = [x for x in medidas if (x["tabela"], x["name"]) in usados and x.get("dataType") != "string"
            and not re.search(r"HTML|SVG|txt", x["name"], re.I)] or [x for x in medidas if x.get("dataType") != "string"][:15]
    q = ["// Checklist de publicacao - rode via MCP dax_query_operations Execute (resultMode Inline).",
         "// 1) Valores das medidas usadas no relatorio (blank/erro aparecem aqui)",
         "EVALUATE ROW(" + ",\n    ".join(f'"{x["name"]}", [{x["name"]}]' for x in meds[:25]) + ")", "",
         "// 2) Linhas por tabela (tabela vazia = refresh falhou ou filtro de origem errado)",
         "EVALUATE UNION(" + ",\n    ".join(f'ROW("Tabela", "{t["name"]}", "Linhas", COUNTROWS(\'{t["name"]}\'))'
                                             for t in m.get("tables", []) if not t.get("isHidden") and t.get("columns")) + ")", ""]
    q.append("// 3) Chaves do lado 1 duplicadas (quebram relacoes no proximo refresh)")
    for r in m.get("relationships", []):
        if r.get("toCardinality", "one") == "one":
            q.append(f"EVALUATE FILTER(SUMMARIZE('{r['toTable']}', '{r['toTable']}'[{r['toColumn']}], \"n\", COUNTROWS('{r['toTable']}')), [n] > 1)")
    q += ["", "// 4) Valores da fato sem correspondencia na dimensao (aparecem como (Em branco) nos visuais)"]
    for r in m.get("relationships", []):
        if r.get("toCardinality", "one") == "one":
            q.append(f"EVALUATE ROW(\"{r['fromTable']}->{r['toTable']}\", COUNTROWS(EXCEPT(VALUES('{r['fromTable']}'[{r['fromColumn']}]), VALUES('{r['toTable']}'[{r['toColumn']}]))))")
    return "\n".join(q)


def opt(nome):
    if nome in sys.argv:
        return sys.argv[sys.argv.index(nome) + 1]
    return None


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("auditoria", "dicionario", "checklist"):
        raise SystemExit(__doc__)
    cmd, bim = sys.argv[1], opt("--bim")
    if not bim:
        raise SystemExit("--bim obrigatorio (MCP: database_operations ExportToBimFile)")
    m = carregar_bim(bim)
    rel = opt("--pbix") or opt("--pbip")
    uso = usados_relatorio(rel)
    origem = Path(rel).name if rel else Path(bim).name
    if cmd == "auditoria":
        achados, medidas, colunas = auditoria(m, uso)
        out = md_auditoria(achados, m, medidas, colunas, uso, origem)
    elif cmd == "dicionario":
        medidas, colunas = objetos(m)
        out = md_dicionario(m, medidas, colunas, uso, origem)
    else:
        out = checklist(m, uso)
    if opt("--saida"):
        Path(opt("--saida")).write_text(out, encoding="utf-8")
        print(f"salvo em {opt('--saida')}")
    else:
        print(out)


if __name__ == "__main__":
    main()

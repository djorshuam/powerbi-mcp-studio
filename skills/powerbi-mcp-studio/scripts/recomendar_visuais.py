"""
recomendar_visuais.py - Le os DADOS e recomenda como visualizar: perfila colunas (data, geografia,
identificador, medida, dimensao, percentual, meta), sugere visuais com justificativa, escolhe o layout
de mercado mais adequado e ja gera o mapa.json para o layout_pbi.py. Parte da skill powerbi-mcp-studio.

Entradas (uma delas):
    --csv a.csv [b.csv ...]      planilhas em CSV (separador , ou ; detectado)
    --xlsx planilha.xlsx         le todas as abas com tabela (usa extrair_dashboard.py)
    --pasta extraida/            saida do extrair_dashboard.py (dados/*.csv)
    --bim modelo.bim             modelo Power BI exportado pelo MCP (usa medidas existentes)
        [--perfil perfil.json]   cardinalidades vindas do DAX gerado por --consulta-perfil (opcional)

Uso:
    python recomendar_visuais.py --xlsx vendas.xlsx --objetivo "diretoria acompanha vendas" --saida rec/
    python recomendar_visuais.py --bim modelo.bim --consulta-perfil        -> imprime DAX de perfil p/ rodar no MCP
    python recomendar_visuais.py --bim modelo.bim --perfil perfil.json --layout scorecard --saida rec/

Saida em --saida:
    recomendacoes.md   explicacao legivel: perfil das colunas, visuais sugeridos e por que, layout escolhido
    recomendacoes.json tudo estruturado
    mapa.json          pronto para: layout_pbi.py instanciar --modelo <layout> --mapa mapa.json
    tabelas_mcp.json   (CSV/xlsx) definicoes de tabela (M + colunas) para table_operations Create no MCP
"""
import csv, json, re, subprocess, sys, unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
LAYOUTS = AQUI.parent / "layouts"


def norm(s):
    return unicodedata.normalize("NFKD", str(s).lower()).encode("ascii", "ignore").decode()


# ------------------------------------------------------------------ leitura
def ler_csv(caminho):
    txt = Path(caminho).read_text(encoding="utf-8-sig", errors="replace")
    amostra = txt[:5000]
    sep = ";" if amostra.count(";") > amostra.count(",") else ","
    linhas = list(csv.reader(txt.splitlines(), delimiter=sep))
    linhas = [l for l in linhas if any(c.strip() for c in l)]
    if len(linhas) < 2:
        return None
    cab = [c.strip() or f"Coluna{i + 1}" for i, c in enumerate(linhas[0])]
    dados = [dict(zip(cab, l + [""] * (len(cab) - len(l)))) for l in linhas[1:]]
    return {"nome": re.sub(r"\W+", "_", Path(caminho).stem).strip("_"), "arquivo": str(Path(caminho).resolve()),
            "sep": sep, "colunas": cab, "linhas": dados}


def num(v):
    s = str(v).strip().replace("R$", "").replace("%", "").strip()
    if not s:
        return None
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s):
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d+,\d+", s):
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def data(v):
    s = str(v).strip()
    for f in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%d/%m/%y", "%Y-%m", "%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:19] if "T" in s else s, f)
        except ValueError:
            pass
    return None


# ------------------------------------------------------------------ perfil
PAD = {
    "id": r"(^id$|^id_|_id$|codigo|^cod_|_cod$|chave|\bkey\b|cpf|cnpj|matricula|protocolo|^sk_|^nk_)",
    "geo": r"(^uf$|estado|cidade|municipio|pais|country|state|city|regiao|region|latitude|longitude|^lat$|^lon|^long$|\bcep\b|bairro)",
    "data": r"(data|date|^dt_|_dt$|dia|mes|month|ano|year|periodo|competencia|semana|trimestre)",
    "pct": r"(%|perc|taxa|pct|rate|margem|ratio|indice|aderencia|atingimento|conversao)",
    "meta": r"(meta|target|objetivo|orcado|orcamento|budget|previsto|planejado)",
    "moeda": r"(valor|receita|custo|preco|faturamento|venda|despesa|lucro|ticket|montante|r\$|revenue|cost|price|sales|amount)",
    "qtd": r"(qtd|quantidade|qtde|volume|numero|num_|total|count|unidades|itens)",
    "etapa": r"(etapa|fase|estagio|stage|status_funil|funil)",
    "conta": r"(conta|dre|plano_contas|grupo_conta|natureza)",
}


def classificar(nome, valores, n_linhas):
    nn = norm(nome)
    vals = [v for v in valores if str(v).strip() != ""]
    distintos = len(set(vals))
    nums = [num(v) for v in vals]
    frac_num = sum(x is not None for x in nums) / max(1, len(vals))
    datas = [data(v) for v in vals[:300]]
    frac_data = sum(d is not None for d in datas) / max(1, min(300, len(vals)))
    p = {"coluna": nome, "distintos": distintos, "vazios": n_linhas - len(vals), "papel": "dimensao", "tags": []}
    for k, rx in PAD.items():
        if re.search(rx, nn):
            p["tags"].append(k)
    if frac_data > 0.9 and frac_num < 0.9:
        p["papel"] = "data"
    elif "id" in p["tags"] or (distintos > 0.9 * n_linhas and n_linhas > 30 and frac_num < 0.5):
        p["papel"] = "id"
    elif frac_num > 0.9:
        xs = [x for x in nums if x is not None]
        inteiro_ano = xs and all(float(x).is_integer() and 1900 <= x <= 2100 for x in xs)
        if inteiro_ano and "data" in p["tags"]:
            p["papel"] = "data"
        elif "id" in p["tags"] or (distintos == n_linhas and n_linhas > 30 and all(float(x).is_integer() for x in xs[:200])):
            p["papel"] = "id"
        elif distintos <= 12 and not any(t in p["tags"] for t in ("moeda", "qtd", "pct", "meta")) and n_linhas > 50:
            p["papel"] = "dimensao"
        else:
            p["papel"] = "medida"
            p["min"], p["max"] = (min(xs), max(xs)) if xs else (None, None)
            if xs and 0 <= min(xs) and max(xs) <= 1.0 and "qtd" not in p["tags"]:
                p["tags"].append("pct")
    elif "geo" in p["tags"]:
        p["papel"] = "geo"
    if p["papel"] == "dimensao":
        p["cardinalidade"] = "baixa" if distintos <= 6 else "media" if distintos <= 20 else "alta" if distintos <= 60 else "muito alta"
    p["exemplos"] = [str(v)[:30] for v in list(dict.fromkeys(vals))[:4]]
    return p


def perfil_tabela(t):
    n = len(t["linhas"])
    cols = [classificar(c, [l.get(c, "") for l in t["linhas"]], n) for c in t["colunas"]]
    return {"tabela": t["nome"], "linhas": n, "colunas": cols, "arquivo": t.get("arquivo"), "sep": t.get("sep")}


def perfil_bim(bim, perfil=None):
    m = json.loads(Path(bim).read_text(encoding="utf-8-sig"))
    m = m.get("model", m)
    card = {}
    if perfil:
        for r in json.loads(Path(perfil).read_text(encoding="utf-8")):
            card[(r["tabela"], r["coluna"])] = r
    tabs = []
    for t in m.get("tables", []):
        if t.get("isHidden") or t["name"].startswith(("DateTableTemplate", "LocalDateTable")):
            continue
        cols = []
        for c in t.get("columns", []):
            if c.get("type") == "rowNumber" or c.get("isHidden"):
                continue
            nn, dt = norm(c["name"]), c.get("dataType", "string")
            info = card.get((t["name"], c["name"]), {})
            p = {"coluna": c["name"], "distintos": info.get("distintos"), "tags": [k for k, rx in PAD.items() if re.search(rx, nn)], "papel": "dimensao"}
            if dt == "dateTime":
                p["papel"] = "data"
            elif "id" in p["tags"]:
                p["papel"] = "id"
            elif dt in ("int64", "double", "decimal") and c.get("summarizeBy", "sum") != "none":
                p["papel"] = "medida"
            elif "geo" in p["tags"]:
                p["papel"] = "geo"
            if p["papel"] == "dimensao":
                d = p["distintos"]
                p["cardinalidade"] = "?" if d is None else "baixa" if d <= 6 else "media" if d <= 20 else "alta" if d <= 60 else "muito alta"
            cols.append(p)
        meds = []
        for x in t.get("measures", []):
            if x.get("isHidden") or (x.get("dataType") == "string"):
                continue
            fmt = (x.get("formatString") or "") + " " + norm(x["name"])
            tags = [k for k, rx in PAD.items() if re.search(rx, norm(x["name"]))]
            if "%" in fmt:
                tags.append("pct")
            meds.append({"medida": x["name"], "tags": tags, "descricao": x.get("description")})
        tabs.append({"tabela": t["name"], "linhas": None, "colunas": cols, "medidas": meds})
    rels = [(r["fromTable"], r["toTable"]) for r in m.get("relationships", []) if r.get("isActive", True)]
    return tabs, rels


def consulta_perfil(bim):
    tabs, _ = perfil_bim(bim)
    partes = []
    for t in tabs:
        for c in t["colunas"]:
            if c["papel"] in ("dimensao", "geo"):
                partes.append(f'ROW("tabela", "{t["tabela"]}", "coluna", "{c["coluna"]}", "distintos", DISTINCTCOUNT(\'{t["tabela"]}\'[{c["coluna"]}]))')
    return "EVALUATE UNION(\n    " + ",\n    ".join(partes) + ")" if partes else "// nenhuma dimensao"


# ------------------------------------------------------------------ recomendacao
def f_col(t, c):
    return f"Coluna:{t}[{c}]"


def medidas_derivadas(fato):
    """Medidas que um analista criaria: atingimento, margem, ticket medio. DAX para o Power BI e formula para o HTML."""
    T, cols = fato["tabela"], fato["colunas"]
    med = [c for c in cols if c["papel"] == "medida"]
    achar = lambda *tags, excl=(): next((c["coluna"] for c in med if all(t in c["tags"] for t in tags) and not any(e in c["tags"] for e in excl)), None)
    valor = next((c["coluna"] for c in med if "moeda" in c["tags"] and re.search(r"venda|receita|faturamento|valor|revenue|sales", norm(c["coluna"]))), achar("moeda", excl=("meta",)))
    custo = next((c["coluna"] for c in med if re.search(r"custo|cost|despesa", norm(c["coluna"]))), None)
    meta = achar("meta")
    idc = next((c["coluna"] for c in cols if c["papel"] == "id"), None)
    out = []
    S = lambda c: f"SUM('{T}'[{c}])"
    if valor and meta:
        out.append({"nome": "Atingimento", "dax": f"DIVIDE({S(valor)}, {S(meta)})", "formato": "0.0%", "tags": ["pct", "meta"], "kpi": True,
                    "js": {"op": "div", "a": ["sum", valor], "b": ["sum", meta]}, "porque": f"{valor} / {meta}: responde 'batemos a meta?'"})
    if valor and custo:
        out.append({"nome": "Margem %", "dax": f"DIVIDE({S(valor)} - {S(custo)}, {S(valor)})", "formato": "0.0%", "tags": ["pct"], "kpi": True,
                    "js": {"op": "margem", "a": ["sum", valor], "b": ["sum", custo]}, "porque": f"({valor} - {custo}) / {valor}"})
    if valor and idc:
        out.append({"nome": "Ticket Medio", "dax": f"DIVIDE({S(valor)}, DISTINCTCOUNT('{T}'[{idc}]))", "formato": "#,0.00", "tags": ["moeda"], "kpi": True,
                    "js": {"op": "div", "a": ["sum", valor], "b": ["distinct", idc]}, "porque": f"{valor} por {idc}"})
    return out


def recomendar(tabs, objetivo=""):
    """Escolhe a tabela fato (mais medidas/linhas) e monta sugestoes por tipo de pergunta."""
    def peso(t):
        return len(t.get("medidas", [])) * 3 + sum(c["papel"] == "medida" for c in t["colunas"]) * 2 + (t.get("linhas") or 0) / 1000
    fato = max(tabs, key=peso)
    T = fato["tabela"]
    todas = [(t["tabela"], c) for t in tabs for c in t["colunas"]]
    datas = [(tn, c) for tn, c in todas if c["papel"] == "data"]
    geos = [(tn, c) for tn, c in todas if c["papel"] == "geo" and not re.search(r"lat|lon", norm(c["coluna"]))]
    dims = [(tn, c) for tn, c in todas if c["papel"] == "dimensao" and c.get("cardinalidade") not in ("muito alta",)]
    for tn, c in todas:  # colunas geograficas de texto tambem servem de dimensao (ranking por UF/regional)
        if c["papel"] == "geo" and (c.get("distintos") or 99) <= 60 and not re.search(r"lat|lon|cep", norm(c["coluna"])):
            d = c.get("distintos") or 20
            dims.append((tn, dict(c, cardinalidade="baixa" if d <= 6 else "media" if d <= 20 else "alta")))
    dims.sort(key=lambda x: ({"baixa": 0, "media": 1, "alta": 2, "?": 1}.get(x[1].get("cardinalidade"), 3), x[1].get("vazios") or 0))
    etapas = [(tn, c) for tn, c in dims if "etapa" in c["tags"]]
    metas_cols = [c for c in fato["colunas"] if c["papel"] == "medida" and "meta" in c["tags"]]

    # medidas: existentes (bim) ou agregacoes das colunas numericas
    kpis = []
    for x in fato.get("medidas", []):
        kpis.append({"campo": f"Medida:{T}[{x['medida']}]", "nome": x["medida"], "tags": x["tags"]})
    for t in tabs:
        if t is fato:
            continue
        for x in t.get("medidas", []):
            kpis.append({"campo": f"Medida:{t['tabela']}[{x['medida']}]", "nome": x["medida"], "tags": x["tags"]})
    for c in fato["colunas"]:
        if c["papel"] != "medida" or "meta" in c["tags"]:
            continue
        ag = "Media" if "pct" in c["tags"] else "Soma"
        kpis.append({"campo": f"{ag}:{T}[{c['coluna']}]", "nome": f"{'Media' if ag == 'Media' else 'Total'} de {c['coluna']}", "tags": c["tags"]})
    prior = lambda k: (0 if set(k["tags"]) & {"moeda", "pct"} else 1 if "qtd" in k["tags"] else 2)
    kpis.sort(key=prior)
    derivadas = medidas_derivadas(fato)
    for d in reversed(derivadas):
        if d.get("kpi"):
            kpis.insert(1, {"campo": f"Medida:{T}[{d['nome']}]", "nome": d["nome"], "tags": d["tags"]})
    fato["derivadas"] = derivadas
    if not kpis:
        chave = next((c for c in fato["colunas"] if c["papel"] == "id"), fato["colunas"][0])
        kpis.append({"campo": f"Contagem:{T}[{chave['coluna']}]", "nome": "Registros", "tags": ["qtd"]})
    ids = [c for c in fato["colunas"] if c["papel"] == "id"]
    if ids and len(kpis) < 6:
        kpis.append({"campo": f"ContagemDistinta:{T}[{ids[0]['coluna']}]", "nome": f"{ids[0]['coluna']} distintos", "tags": ["qtd"]})
    principal = next((k for k in kpis if k["campo"].startswith("Soma:") and "moeda" in k["tags"]), kpis[0])

    sug = {"kpis": [], "tendencia": [], "ranking": [], "composicao": [], "geo": [], "funil": [], "meta": [], "tabela": [], "filtros": []}
    for k in kpis[:8]:
        sug["kpis"].append({"tipo": "card", "campos": [f"Values={k['campo']}"], "titulo": k["nome"],
                            "porque": "numero-chave em destaque" + (" (percentual: use media, nunca soma)" if "pct" in k["tags"] else "")})
    if datas:
        tn, c = datas[0]
        col_mes = f"{c['coluna']} Mes" if fato.get("linhas") else c["coluna"]  # CSV: coluna derivada ano-mes criada no M/HTML
        for k in [k for k in kpis if "pct" not in k["tags"]][:1] + [k for k in kpis if "pct" in k["tags"]][:1]:
            sug["tendencia"].append({"tipo": "lineChart", "campos": [f"Category={f_col(tn, col_mes)}", f"Y={k['campo']}"],
                                     "titulo": f"{k['nome']} por mes", "porque": f"'{c['coluna']}' e data: linha mensal mostra evolucao e sazonalidade sem o ruido diario"})
    for tn, c in dims[:4]:
        card_ = c.get("cardinalidade")
        tipo = "clusteredBarChart" if card_ in ("media", "alta", "?") else "clusteredColumnChart"
        sug["ranking"].append({"tipo": tipo, "campos": [f"Category={f_col(tn, c['coluna'])}", f"Y={principal['campo']}"],
                               "titulo": f"{principal['nome']} por {c['coluna']}",
                               "porque": f"'{c['coluna']}' tem {c.get('distintos', '?')} valores: " + ("barras horizontais ordenadas leem melhor rotulos longos" if tipo == "clusteredBarChart" else "poucas categorias: colunas comparam bem")})
        if card_ == "baixa":
            sug["composicao"].append({"tipo": "donutChart", "campos": [f"Category={f_col(tn, c['coluna'])}", f"Y={principal['campo']}"],
                                      "titulo": f"Participacao por {c['coluna']}", "porque": f"so {c.get('distintos')} categorias: rosca mostra participacao sem poluir"})
    for tn, c in geos[:1]:
        sug["geo"].append({"tipo": "filledMap", "campos": [f"Category={f_col(tn, c['coluna'])}", f"Values={principal['campo']}"],
                           "titulo": f"{principal['nome']} por {c['coluna']}", "porque": f"'{c['coluna']}' e geografico"})
    for tn, c in etapas[:1]:
        sug["funil"].append({"tipo": "funnel", "campos": [f"Category={f_col(tn, c['coluna'])}", f"Y={principal['campo']}"],
                             "titulo": f"Funil por {c['coluna']}", "porque": f"'{c['coluna']}' parece etapa de processo"})
    if metas_cols:
        mcol = metas_cols[0]
        cat = (datas[0][0], (datas[0][1]["coluna"] + " Mes") if fato.get("linhas") else datas[0][1]["coluna"]) if datas else ((dims[0][0], dims[0][1]["coluna"]) if dims else None)
        base = next((k for k in kpis if k["campo"].startswith("Soma:") and "moeda" in k["tags"]), principal)
        if cat:
            sug["meta"].append({"tipo": "clusteredColumnChart", "campos": [f"Category={f_col(cat[0], cat[1])}", f"Y={base['campo']}", f"Y=Soma:{T}[{mcol['coluna']}]"],
                                "titulo": f"Realizado x {mcol['coluna']}", "porque": f"existe coluna de meta ('{mcol['coluna']}'): comparar lado a lado"})
    det = [f"Values={f_col(tn, c['coluna'])}" for tn, c in dims[:2]] + [f"Values={k['campo']}" for k in kpis[:3]]
    sug["tabela"].append({"tipo": "tableEx", "campos": det, "titulo": "Detalhe", "porque": "conferencia e exportacao; no maximo 6 colunas"})
    for tn, c in ([datas[0]] if datas else []) + [d for d in dims if d[1].get("cardinalidade") in ("baixa", "media")][:3]:
        sug["filtros"].append({"tipo": "slicer", "campos": [f"Values={f_col(tn, c['coluna'])}"], "titulo": c["coluna"], "porque": "filtro de uso frequente"})

    # layout
    obj = norm(objetivo)
    if sug["funil"] or re.search(r"funil|pipeline|vendedor|crm", obj):
        layout = "funil-comercial"
    elif any("conta" in c["tags"] for c in fato["colunas"]) or re.search(r"dre|financeir|orcad", obj):
        layout = "financeiro-dre"
    elif re.search(r"farol|aderencia|scorecard|okr|semaforo", obj) or (metas_cols and len(kpis) > 8):
        layout = "scorecard"
    elif sug["geo"] and re.search(r"mapa|unidade|filial|regiao|estado|loja", obj + " ".join(c["coluna"] for _, c in geos)):
        layout = "geografico"
    elif re.search(r"tempo real|monitor|tv|noc|operac", obj):
        layout = "operacional"
    elif re.search(r"analis|explor|filtro", obj):
        layout = "analitico-filtro-lateral"
    elif re.search(r"compar|anterior|ano passado|yoy|variacao", obj):
        layout = "comparativo-periodos"
    else:
        layout = "executivo"
    return fato, sug, layout


ORDEM_SLOT = {  # tipo do slot -> fontes de sugestao em ordem de preferencia
    "card": ["kpis"], "multiRowCard": ["kpis"],
    "lineChart": ["tendencia", "meta", "ranking"], "areaChart": ["tendencia", "ranking"],
    "clusteredColumnChart": ["meta", "ranking", "tendencia"], "clusteredBarChart": ["ranking", "meta"],
    "stackedColumnChart": ["ranking"], "donutChart": ["composicao", "ranking"], "pieChart": ["composicao", "ranking"],
    "funnel": ["funil", "ranking"], "filledMap": ["geo", "ranking"], "tableEx": ["tabela"], "pivotTable": ["tabela"],
    "slicer": ["filtros"],
}


def montar_mapa(layout, sug):
    spec = json.loads((LAYOUTS / layout / "layout.json").read_text(encoding="utf-8"))
    usados, mapa = set(), {}
    for v in spec["paginas"][0]["visuais"]:
        for fonte in ORDEM_SLOT.get(v["tipo"], []):
            cand = next((i for i, s in enumerate(sug[fonte]) if (fonte, i) not in usados), None)
            if cand is None:
                continue
            s = sug[fonte][cand]
            usados.add((fonte, cand))
            if v["tipo"] == "multiRowCard":
                camp = [c for k in sug["kpis"][:4] for c in k["campos"]]
                mapa[v["slot"]] = {"campos": camp, "titulo": "Indicadores"}
            else:
                cfg = {"campos": s["campos"], "titulo": s["titulo"]}
                if s["tipo"] != v["tipo"] and not (v["tipo"] in ("pivotTable",) and s["tipo"] == "tableEx"):
                    cfg["tipo"] = s["tipo"]
                if v["tipo"] == "pivotTable" and s["tipo"] == "tableEx":
                    cfg["tipo"] = "tableEx"
                mapa[v["slot"]] = cfg
            break
    return mapa


def tabelas_mcp(perfis):
    """Definicoes para MCP table_operations Create (Power Query M lendo o CSV)."""
    tipos_m = {"data": ("type date", "DateTime"), "medida": ("type number", "Double")}
    out = []
    for p in perfis:
        if not p.get("arquivo"):
            continue
        tr, cols = [], []
        for c in p["colunas"]:
            tm, td = tipos_m.get(c["papel"], ("type text", "String"))
            if c["papel"] == "id":
                tm, td = "type text", "String"
            tr.append(f'{{"{c["coluna"]}", {tm}}}')
            cols.append({"name": c["coluna"], "dataType": td, "sourceColumn": c["coluna"]})
        mes = [c["coluna"] for c in p["colunas"] if c["papel"] == "data"]
        for c in mes:
            cols.append({"name": f"{c} Mes", "dataType": "String", "sourceColumn": f"{c} Mes"})
        caminho = p["arquivo"].replace('"', '""')  # M nao usa escape de barra invertida
        m = ("let\n    Fonte = Csv.Document(File.Contents(\"" + caminho + "\"), [Delimiter=\"" + p["sep"] + "\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n"
             "    Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars=true]),\n"
             "    Tipos = Table.TransformColumnTypes(Cabecalho, {" + ", ".join(tr) + "}, \"en-US\")"
             + "".join(f",\n    Mes{i} = Table.AddColumn({'Tipos' if i == 0 else 'Mes' + str(i - 1)}, \"{c} Mes\", each Date.ToText([{c}], \"yyyy-MM\"), type text)" for i, c in enumerate(mes))
             + f"\nin\n    {'Mes' + str(len(mes) - 1) if mes else 'Tipos'}")
        out.append({"name": p["tabela"], "mExpression": m, "columns": cols,
                    "_obs": "Ajuste o caminho do CSV para o local definitivo (ou troque por Excel.Workbook/SharePoint) antes de criar."})
    return out


def md(perfis, fato, sug, layout, mapa, objetivo):
    L = ["# Recomendacoes de visualizacao", ""]
    if objetivo:
        L += [f"Objetivo informado: _{objetivo}_", ""]
    L += [f"**Tabela principal:** `{fato['tabela']}`" + (f" ({fato['linhas']} linhas)" if fato.get("linhas") else ""), "",
          f"**Layout recomendado:** `{layout}` — ver `layouts/{layout}/LAYOUT.md` e `previa.png`", "", "## Perfil dos dados", ""]
    for p in perfis:
        L += [f"### {p['tabela']}", "", "| Coluna | Papel | Distintos | Marcas | Exemplos |", "|---|---|---|---|---|"]
        for c in p["colunas"]:
            L.append(f"| {c['coluna']} | {c['papel']}{' (' + c['cardinalidade'] + ')' if c.get('cardinalidade') else ''} | {c.get('distintos', '')} | {', '.join(c['tags'])} | {', '.join(c.get('exemplos', []))} |")
        for x in p.get("medidas", []):
            L.append(f"| [{x['medida']}] | medida DAX | | {', '.join(x['tags'])} | |")
        L.append("")
    nomes = {"kpis": "Numeros-chave (cartoes)", "tendencia": "Evolucao no tempo", "ranking": "Comparacao / ranking", "composicao": "Participacao",
             "geo": "Geografia", "funil": "Funil", "meta": "Realizado x meta", "tabela": "Detalhe", "filtros": "Filtros"}
    L += ["## Visuais sugeridos", ""]
    for k, lst in sug.items():
        if lst:
            L += [f"**{nomes[k]}**"] + [f"- `{s['tipo']}` — {s['titulo']}: {s['porque']}" for s in lst] + [""]
    if fato.get("derivadas"):
        L += ["## Medidas a criar", "", "| Medida | DAX | Por que |", "|---|---|---|"]
        L += [f"| {d['nome']} | `{d['dax']}` | {d['porque']} |" for d in fato["derivadas"]]
        L += ["", "Power BI: criar via MCP (`measure_operations` Create, tabela `" + fato["tabela"] + "`, com o formato indicado em `medidas.json`). HTML: calculadas automaticamente.", ""]
    L += ["## Pagina montada", "", f"`mapa.json` preenche {len(mapa)} espaco(s) do layout `{layout}`. Proximo passo:", "",
          f"```\npython scripts/layout_pbi.py instanciar --modelo {layout} --mapa mapa.json --pagina \"Visao Geral\" --saida layout.json\n```", "",
          "Depois: HTML (`gerar_html.py`) ou Power BI (`visuais_pbi.py lote` + `svg_fundo.py` + `tema_pbi.py`)."]
    return "\n".join(L)


def main():
    a = lambda n, d=None: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
    objetivo = a("--objetivo", "")
    perfis, rels = [], []
    if "--bim" in sys.argv:
        if "--consulta-perfil" in sys.argv:
            print(consulta_perfil(a("--bim")))
            print("\n// Rode no MCP (dax_query_operations Execute, Inline) e salve como JSON: "
                  '[{"tabela": "...", "coluna": "...", "distintos": N}, ...] -> --perfil perfil.json')
            return
        perfis, rels = perfil_bim(a("--bim"), a("--perfil"))
    else:
        arquivos = []
        if "--csv" in sys.argv:
            i = sys.argv.index("--csv") + 1
            while i < len(sys.argv) and not sys.argv[i].startswith("--"):
                arquivos.append(sys.argv[i]); i += 1
        if a("--xlsx"):
            saida_ext = Path(a("--saida", "rec")) / "extraido"
            subprocess.run([sys.executable, str(AQUI / "extrair_dashboard.py"), a("--xlsx"), "--saida", str(saida_ext)], check=True, capture_output=True)
            arquivos += sorted(str(p) for p in (saida_ext / "dados").glob("*.csv"))
        if a("--pasta"):
            arquivos += sorted(str(p) for p in (Path(a("--pasta")) / "dados").glob("*.csv"))
        if not arquivos:
            raise SystemExit(__doc__)
        for f in arquivos:
            t = ler_csv(f)
            if t:
                perfis.append(perfil_tabela(t))
    fato, sug, layout = recomendar(perfis, objetivo)
    layout = a("--layout", layout)
    mapa = montar_mapa(layout, sug)
    out = Path(a("--saida", "rec"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "mapa.json").write_text(json.dumps(mapa, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "recomendacoes.json").write_text(json.dumps({"fato": fato["tabela"], "layout": layout, "sugestoes": sug, "perfis": perfis},
                                                       ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "medidas.json").write_text(json.dumps([dict(d, tabela=fato["tabela"]) for d in fato.get("derivadas", [])], ensure_ascii=False, indent=1), encoding="utf-8")
    if perfis and perfis[0].get("arquivo"):
        (out / "tabelas_mcp.json").write_text(json.dumps(tabelas_mcp(perfis), ensure_ascii=False, indent=1), encoding="utf-8")
    texto = md(perfis, fato, sug, layout, mapa, objetivo)
    (out / "recomendacoes.md").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()

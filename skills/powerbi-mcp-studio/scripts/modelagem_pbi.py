"""
modelagem_pbi.py - Padrao de modelagem da skill: transforma uma tabela "achatada" (planilha/CSV) num
MODELO ESTRELA pronto para o MCP, com tabela calendario, tabela de medidas com pastas e medidas explicitas.
Parte da skill powerbi-mcp-studio.

Padrao aplicado:
  - Fato: a tabela original (chaves de texto ficam, mas ocultas); colunas numericas viram medidas explicitas.
  - Dimensoes: d<Nome> por grupo de colunas descritivas (ex.: dLocal = UF + Regional; dProduto = Produto + Categoria),
    criadas em Power Query referenciando a fato (Table.Distinct), relacao 1:* unidirecional.
  - Calendario: tabela DAX (CALENDAR do 1o ao ultimo ano da fato), marcada como tabela de datas, com Ano, Trimestre,
    Mes, Mes Num, Ano Mes, Dia da Semana; relacao com a coluna de data da fato.
  - _Medidas: tabela so de medidas; pastas "1. Base" (somas, contagens) e "2. Indicadores" (derivadas: atingimento,
    margem, ticket). Visuais usam SEMPRE medidas explicitas (nada de soma implicita).

Uso:
    python modelagem_pbi.py plano --rec rec/ --saida rec/modelo_estrela.json [--csv-no-pc "C:\\...\\Pedidos.csv"]
        -> plano com tabelas (M/DAX), relacoes, medidas com pastas, colunas a ocultar, e o de-para de campos
    python modelagem_pbi.py remapear --plano rec/modelo_estrela.json --mapa rec/mapa.json --saida rec/mapa_estrela.json
        -> reescreve os campos do mapa/layout para o modelo estrela (Soma:Pedidos[Valor Venda] -> Medida:_Medidas[Total Valor Venda])

O plano e executado pelo Claude via MCP (ordem em "passos"); ver references/modelagem.md.
"""
import json, re, sys, unicodedata
from pathlib import Path


def norm(s):
    return unicodedata.normalize("NFKD", str(s).lower()).encode("ascii", "ignore").decode()


GRUPOS = [  # nome da dimensao -> padroes de coluna (a primeira coluna que casar e a chave)
    ("dLocal", r"(cidade|municipio|^uf$|estado|regional|regiao|pais|bairro|filial|loja|unidade)"),
    ("dProduto", r"(produto|sku|item|categoria|subcategoria|marca|linha|familia)"),
    ("dCliente", r"(cliente|segmento|customer|empresa|conta)"),
    ("dVendedor", r"(vendedor|representante|consultor|gerente|equipe|time)"),
    ("dCanal", r"(canal|origem|midia|campanha)"),
]
HIERARQ = {"dLocal": ["cidade", "municipio", "uf", "estado", "regional", "regiao", "pais"],
           "dProduto": ["produto", "sku", "item", "subcategoria", "categoria", "familia", "linha", "marca"]}


def plano(rec, csv_pc=None):
    r = json.loads((rec / "recomendacoes.json").read_text(encoding="utf-8"))
    tab = json.loads((rec / "tabelas_mcp.json").read_text(encoding="utf-8"))[0]
    meds = json.loads((rec / "medidas.json").read_text(encoding="utf-8")) if (rec / "medidas.json").exists() else []
    perfil = next(p for p in r["perfis"] if p["tabela"] == r["fato"])
    F = perfil["tabela"]
    cols = {c["coluna"]: c for c in perfil["colunas"]}
    m_fato = tab["mExpression"]
    if csv_pc:
        m_fato = re.sub(r'File\.Contents\("[^"]*"\)', lambda _: f'File.Contents("{csv_pc}")', m_fato)
    m_fato = re.sub(r",\s*Mes\d+ = Table\.AddColumn\([^\n]*\)", "", m_fato)  # ano-mes vem do calendario
    m_fato = re.sub(r"in\s+Mes\d+\s*$", "in\n    Tipos", m_fato.strip())
    data_col = next((c for c, p in cols.items() if p["papel"] == "data"), None)

    # dimensoes
    usados, dims = set(), []
    for nome, rx in GRUPOS:
        grupo = [c for c, p in cols.items() if c not in usados and p["papel"] in ("dimensao", "geo") and re.search(rx, norm(c))]
        if not grupo:
            continue
        ordem = HIERARQ.get(nome, [])
        grupo.sort(key=lambda c: next((i for i, k in enumerate(ordem) if k in norm(c)), 99))
        usados |= set(grupo)
        dims.append({"nome": nome, "chave": grupo[0], "colunas": grupo})
    for c, p in cols.items():  # sobras de baixa/media cardinalidade viram dimensao propria
        if c not in usados and p["papel"] in ("dimensao", "geo") and p.get("cardinalidade") in ("baixa", "media", "alta"):
            dims.append({"nome": "d" + re.sub(r"\W", "", c.title()), "chave": c, "colunas": [c]})
            usados.add(c)

    tabelas = [{"name": F, "mExpression": m_fato,
                "columns": [x for x in tab["columns"] if not x["name"].endswith(" Mes")]}]
    for d in dims:
        lista = ", ".join(f'"{c}"' for c in d["colunas"])
        ref = F if re.fullmatch(r"[A-Za-z_]\w*", F) else '#"' + F + '"'
        m = (f"let\n    Fonte = {ref},\n"
             f"    Colunas = Table.SelectColumns(Fonte, {{{lista}}}),\n"
             f"    Unicos = Table.Distinct(Colunas, {{\"{d['chave']}\"}}),\n"
             f"    SemVazio = Table.SelectRows(Unicos, each [{d['chave']}] <> null and [{d['chave']}] <> \"\")\nin\n    SemVazio")
        tabelas.append({"name": d["nome"], "mExpression": m,
                        "columns": [{"name": c, "dataType": "String", "sourceColumn": c} for c in d["colunas"]]})

    calendario = None
    if data_col:
        calendario = {"name": "Calendario", "daxExpression":
            f"VAR _ini = DATE(YEAR(MIN('{F}'[{data_col}])), 1, 1)\nVAR _fim = DATE(YEAR(MAX('{F}'[{data_col}])), 12, 31)\nRETURN\nADDCOLUMNS(\n    CALENDAR(_ini, _fim),\n"
            "    \"Ano\", YEAR([Date]),\n    \"Trimestre\", \"T\" & QUARTER([Date]),\n    \"Mes Num\", MONTH([Date]),\n"
            "    \"Mes\", FORMAT([Date], \"mmm\"),\n    \"Ano Mes\", FORMAT([Date], \"yyyy-mm\"),\n"
            "    \"Dia da Semana\", FORMAT([Date], \"ddd\"),\n    \"Dia Semana Num\", WEEKDAY([Date], 2)\n)",
            "marcar_data": "Date", "ordenar": {"Mes": "Mes Num", "Dia da Semana": "Dia Semana Num"}}

    relacoes = [{"fromTable": F, "fromColumn": d["chave"], "toTable": d["nome"], "toColumn": d["chave"],
                 "fromCardinality": "Many", "toCardinality": "One", "crossFilteringBehavior": "OneDirection", "isActive": True} for d in dims]
    if calendario:
        relacoes.append({"fromTable": F, "fromColumn": data_col, "toTable": "Calendario", "toColumn": "Date",
                         "fromCardinality": "Many", "toCardinality": "One", "crossFilteringBehavior": "OneDirection", "isActive": True})

    # medidas explicitas
    medidas = []
    fmt = lambda p: "0.0%" if "pct" in p["tags"] else "#,0.00" if "moeda" in p["tags"] or "meta" in p["tags"] else "#,0"
    for c, p in cols.items():
        if p["papel"] == "medida":
            ag, nome = ("AVERAGE", f"Media {c}") if "pct" in p["tags"] else ("SUM", f"Total {c}")
            medidas.append({"name": nome, "expression": f"{ag}('{F}'[{c}])", "formatString": fmt(p), "displayFolder": "1. Base",
                            "description": f"{'Media' if ag == 'AVERAGE' else 'Soma'} de {F}[{c}]", "_origem": f"{'Media' if ag == 'AVERAGE' else 'Soma'}:{F}[{c}]"})
    idc = next((c for c, p in cols.items() if p["papel"] == "id"), None)
    if idc:
        medidas.append({"name": f"Qtd {idc}", "expression": f"DISTINCTCOUNT('{F}'[{idc}])", "formatString": "#,0", "displayFolder": "1. Base",
                        "description": f"Quantidade de {idc} distintos", "_origem": f"ContagemDistinta:{F}[{idc}]"})
    medidas.append({"name": "Linhas", "expression": f"COUNTROWS('{F}')", "formatString": "#,0", "displayFolder": "1. Base",
                    "description": f"Linhas de {F}", "_origem": f"Contagem:{F}[*]"})
    base = {re.sub(r"^(Total|Media) ", "", m["name"]): m["name"] for m in medidas}
    for d in meds:  # derivadas reescritas sobre as medidas base
        dax = d["dax"]
        for c in cols:
            dax = dax.replace(f"SUM('{F}'[{c}])", f"[Total {c}]")
        if idc:
            dax = dax.replace(f"DISTINCTCOUNT('{F}'[{idc}])", f"[Qtd {idc}]")
        medidas.append({"name": d["nome"], "expression": dax, "formatString": d["formato"], "displayFolder": "2. Indicadores",
                        "description": d.get("porque", ""), "_origem": f"Medida:{F}[{d['nome']}]"})

    ocultar = [{"tabela": F, "coluna": d["chave"]} for d in dims] + [{"tabela": F, "coluna": c} for d in dims for c in d["colunas"][1:]]
    ocultar += [{"tabela": F, "coluna": c} for c, p in cols.items() if p["papel"] == "medida"]
    if data_col:
        ocultar.append({"tabela": F, "coluna": data_col})
    # de-para para os visuais
    depara = {}
    for d in dims:
        for c in d["colunas"]:
            depara[f"Coluna:{F}[{c}]"] = f"Coluna:{d['nome']}[{c}]"
    if data_col:
        depara[f"Coluna:{F}[{data_col} Mes]"] = "Coluna:Calendario[Ano Mes]"
        depara[f"Coluna:{F}[{data_col}]"] = "Coluna:Calendario[Date]"
    for m in medidas:
        depara[m["_origem"]] = f"Medida:_Medidas[{m['name']}]"

    passos = [
        f"1. table_operations Create: {F} (fato) e depois as dimensoes {', '.join(d['nome'] for d in dims)} (mExpression + columns)",
        "2. table_operations Create: _Medidas com daxExpression = ROW(\"_\", BLANK()) (depois ocultar a coluna \"_\")",
        "3. table_operations Create: Calendario com daxExpression; MarkAsDateTable (coluna Date); column_operations Update sortByColumn (Mes->Mes Num, Dia da Semana->Dia Semana Num)",
        "4. RefreshWithXMLA de todas as tabelas; conferir COUNTROWS e se cada chave de dimensao e unica",
        "5. relationship_operations Create: relacoes do plano (1:*, filtro unico)",
        "6. measure_operations Create na tabela _Medidas: medidas do plano (displayFolder, formatString, description)",
        "7. column_operations Update isHidden=true: colunas em 'ocultar' (fato mostra so medidas; dimensoes mostram atributos)",
        "8. Validar: KPIs via DAX = planilha; filtro por dimensao = filtro na planilha",
        "9. Exibicao de modelo: organizar em estrela (fato no centro, dimensoes em volta, Calendario e _Medidas no topo) - pela interface",
    ]
    return {"fato": F, "dimensoes": dims, "tabelas": tabelas, "calendario": calendario,
            "tabela_medidas": {"name": "_Medidas", "daxExpression": "ROW(\"_\", BLANK())"},
            "relacoes": relacoes, "medidas": medidas, "ocultar": ocultar, "depara": depara, "passos": passos}


def remapear(pl, obj):
    dp = pl["depara"]

    def troca(campo):
        papel, spec = campo.split("=", 1)
        if spec in dp:
            return f"{papel}={dp[spec]}"
        m = re.fullmatch(r"(\w+):(.+)\[(.+)\]", spec)
        if m and m.group(1) in ("Soma", "Media", "Contagem", "ContagemDistinta"):
            chave = next((k for k in dp if k.endswith(f"[{m.group(3)}]") and k.startswith(("Soma", "Media", "ContagemDistinta"))), None)
            if chave:
                return f"{papel}={dp[chave]}"
        return campo
    if isinstance(obj, dict) and "paginas" in obj:
        for pg in obj["paginas"]:
            for v in pg["visuais"]:
                v["campos"] = [troca(c) for c in v.get("campos", [])]
    else:
        for k, v in obj.items():
            v["campos"] = [troca(c) for c in v.get("campos", [])]
    return obj


def main():
    a = lambda n, d=None: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] == "plano":
        pl = plano(Path(a("--rec", "rec")), a("--csv-no-pc"))
        Path(a("--saida", "modelo_estrela.json")).write_text(json.dumps(pl, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"fato {pl['fato']} + {len(pl['dimensoes'])} dimensoes ({', '.join(d['nome'] + '[' + ', '.join(d['colunas']) + ']' for d in pl['dimensoes'])})")
        print(f"Calendario: {'sim' if pl['calendario'] else 'nao (sem coluna de data)'} · _Medidas: {len(pl['medidas'])} medidas em pastas · {len(pl['relacoes'])} relacoes")
        print("\n".join(pl["passos"]))
    elif sys.argv[1] == "remapear":
        pl = json.loads(Path(a("--plano")).read_text(encoding="utf-8"))
        alvo = json.loads(Path(a("--mapa")).read_text(encoding="utf-8"))
        Path(a("--saida")).write_text(json.dumps(remapear(pl, alvo), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"campos remapeados para o modelo estrela -> {a('--saida')}")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

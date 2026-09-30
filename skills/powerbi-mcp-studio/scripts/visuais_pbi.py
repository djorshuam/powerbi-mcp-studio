"""
visuais_pbi.py - Paginas e visuais de relatorios Power BI (.pbix ou .pbip, formato PBIR).
Parte da skill powerbi-mcp-studio. Escrita so com o Power BI Desktop FECHADO.

Listar (pode com o Desktop aberto):
    python visuais_pbi.py listar --pbix X.pbix [--pagina "Visao Geral"]

Mover/redimensionar por plano (JSON):
    python visuais_pbi.py mover --pbix X.pbix --plano plano.json
    plano.json: [{"pagina": "Visao Geral", "visual": "<id ou titulo>", "x": 20, "y": 80, "w": 300, "h": 160}]

Posicionar pelo Figma (retangulos nomeados com o id ou titulo do visual dentro do frame da pagina):
    python visuais_pbi.py figma --pbix X.pbix --pagina "Visao Geral" --frame 12:34 [--figma-file CHAVE] [--dry-run]

Criar pagina / visual (usado pelo conversor Excel/HTML -> Power BI):
    python visuais_pbi.py nova-pagina --pbix X.pbix --nome "Vendas" [--largura 1280 --altura 720]
    python visuais_pbi.py criar --pbix X.pbix --pagina "Vendas" --tipo card --campo "Values=Medida:Vendas[Total]" \
        --x 20 --y 20 --w 220 --h 120 [--titulo "Total de vendas"]
    python visuais_pbi.py lote --pbix X.pbix --spec layout.json          -> varias paginas/visuais de uma vez

Visual customizado (ex.: HTML Content) copiado de outro relatorio que ja o tenha:
    python visuais_pbi.py visual-custom --pbix X.pbix --de outro.pbix [--guid htmlContent443BE3AD55E043BF878BED274D3A6855]

Campos: "<Papel>=<Tipo>:<Tabela>[<Campo>]"  Tipo = Medida | Coluna | Soma | Media | Contagem | Min | Max | ContagemDistinta
Tipos de visual e papeis: ver TIPOS abaixo (ou `python visuais_pbi.py tipos`).

Saidas: 0 ok | 2 estrutura nao reconhecida (use a interface) | 1 erro.
"""
import json, os, re, secrets, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pbi_arquivo import Relatorio, EstruturaDesconhecida, ArquivoAberto, dump_json, MSG_LEGADO  # noqa: E402

SCHEMA_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"
SCHEMA_PAGINA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"

TIPOS = {  # visualType -> papeis aceitos (ordem = ordem sugerida)
    "card": ["Values"],
    "cardVisual": ["Data"],
    "multiRowCard": ["Values"],
    "kpi": ["Indicator", "TrendLine", "Goal"],
    "gauge": ["Y", "MinValue", "MaxValue", "TargetValue"],
    "clusteredColumnChart": ["Category", "Y", "Series"],
    "clusteredBarChart": ["Category", "Y", "Series"],
    "stackedColumnChart": ["Category", "Y", "Series"],
    "stackedBarChart": ["Category", "Y", "Series"],
    "lineChart": ["Category", "Y", "Series"],
    "areaChart": ["Category", "Y", "Series"],
    "lineClusteredColumnComboChart": ["Category", "Y", "Y2"],
    "pieChart": ["Category", "Y"],
    "donutChart": ["Category", "Y"],
    "funnel": ["Category", "Y"],
    "treemap": ["Group", "Values"],
    "scatterChart": ["Category", "X", "Y", "Size"],
    "tableEx": ["Values"],
    "pivotTable": ["Rows", "Columns", "Values"],
    "slicer": ["Values"],
    "map": ["Category", "Size"],
    "filledMap": ["Category", "Values"],
    "textbox": [],
    "htmlContent443BE3AD55E043BF878BED274D3A6855": ["content", "sampling", "tooltips"],  # HTML Content (AppSource)
}
HTML_CONTENT = "htmlContent443BE3AD55E043BF878BED274D3A6855"
AGG = {"Soma": 0, "Media": 1, "Contagem": 5, "Min": 3, "Max": 4, "ContagemDistinta": 2}
AGG_NOME = {0: "Sum", 1: "Avg", 2: "CountNonNull", 3: "Min", 4: "Max", 5: "Count"}


def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def campo(spec):
    """'Medida:Tabela[Campo]' -> (field, queryRef, nativeQueryRef)."""
    m = re.fullmatch(r"\s*(\w+)\s*:\s*'?([^'\[]+?)'?\s*\[([^\]]+)\]\s*", spec)
    if not m:
        raise SystemExit(f"campo invalido: {spec!r} (use Tipo:Tabela[Campo])")
    tipo, tab, nome = m.groups()
    col = {"Column": {"Expression": {"SourceRef": {"Entity": tab}}, "Property": nome}}
    if tipo == "Medida":
        return {"Measure": {"Expression": {"SourceRef": {"Entity": tab}}, "Property": nome}}, f"{tab}.{nome}", nome
    if tipo == "Coluna":
        return col, f"{tab}.{nome}", nome
    if tipo in AGG:
        f = AGG[tipo]
        return {"Aggregation": {"Expression": col, "Function": f}}, f"{AGG_NOME[f]}({tab}.{nome})", f"{tipo} de {nome}"
    raise SystemExit(f"tipo de campo invalido: {tipo}. Use Medida, Coluna ou {list(AGG)}")


def novo_id():
    return secrets.token_hex(10)


P = lambda **k: [{"properties": {n: lit(v) for n, v in k.items()}}]
BARRAS = {"clusteredColumnChart", "clusteredBarChart", "stackedColumnChart", "stackedBarChart"}
LINHAS = {"lineChart", "areaChart", "lineClusteredColumnComboChart"}


def acabamento(tipo, vis, vco, series=1):
    """Padrao de qualidade dos visuais nativos (mesma linguagem do dashboard HTML):
    titulo 12pt semibold a esquerda; visual transparente sem borda/sombra (o cartao vem do fundo SVG);
    sem linhas de grade; barras com rotulo de dado e sem eixo de valor; legenda so com 2+ series, no topo;
    sem titulos de eixo; cartao com numero grande. Cores e fonte vem do tema (tema_pbi.py)."""
    o = vis.setdefault("objects", {})
    if "title" in vco:
        vco["title"][0]["properties"].update(fontSize=lit(12), bold=lit(True), alignment=lit("left"))
    vco.update(background=P(show=False), border=P(show=False), dropShadow=P(show=False),
               padding=[{"properties": {"top": lit(4), "bottom": lit(4), "left": lit(6), "right": lit(6)}}])
    if tipo in ("card", "multiRowCard"):
        o["labels"] = P(fontSize=28)
    elif tipo in BARRAS | LINHAS:
        o["categoryAxis"] = P(showAxisTitle=False, gridlineShow=False)
        o["valueAxis"] = P(showAxisTitle=False, gridlineShow=False, show=tipo not in BARRAS)
        o["legend"] = P(show=series > 1, position="TopRight", showTitle=False)
        o["labels"] = P(show=tipo in BARRAS or tipo == "lineClusteredColumnComboChart")
        if tipo in BARRAS:
            o["valueAxis"] = P(showAxisTitle=False, gridlineShow=False, show=False)
    elif tipo == "slicer":
        vco.update(title=P(show=False))
        o["header"] = P(show=True, fontSize=10)
        o["data"] = P(mode="Dropdown")
    elif tipo in ("tableEx", "pivotTable"):
        o["grid"] = P(gridVertical=False, rowPadding=4)


def visual_json(tipo, campos, x, y, w, h, z, titulo=None, texto=None):
    if tipo not in TIPOS:
        raise SystemExit(f"tipo '{tipo}' nao suportado. Tipos: {', '.join(TIPOS)}")
    nome = novo_id()
    vis = {"visualType": tipo, "drillFilterOtherVisuals": True}
    if campos:
        qs = {}
        for papel, spec in campos:
            if papel not in TIPOS[tipo]:
                raise SystemExit(f"papel '{papel}' invalido para {tipo}. Aceitos: {TIPOS[tipo]}")
            f, qref, nref = campo(spec)
            qs.setdefault(papel, {"projections": []})["projections"].append(
                {"field": f, "queryRef": qref, "nativeQueryRef": nref})
        vis["query"] = {"queryState": qs}
    if tipo == "textbox" and texto:
        vis["objects"] = {"general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": texto, "textStyle": {"fontSize": "14pt", "fontWeight": "bold"}}]}]}}]}
    vco = {"subTitle": [{"properties": {"show": lit(False)}}]}  # tema Fluent 2 liga subtitulo automatico (duplica o titulo)
    if tipo == HTML_CONTENT:  # o titulo esta dentro do HTML; visual limpo e transparente
        titulo = None
        vco.update(title=[{"properties": {"show": lit(False)}}], background=[{"properties": {"show": lit(False)}}],
                   visualHeader=[{"properties": {"show": lit(False)}}], border=[{"properties": {"show": lit(False)}}])
        vis["objects"] = {"contentFormatting": [{"properties": {"userSelect": lit(False)}}]}
    if titulo:
        vco["title"] = [{"properties": {"show": lit(True), "text": lit(titulo)}}]
    vis["visualContainerObjects"] = vco
    if tipo in ("card", "multiRowCard") and titulo:
        # titulo ja nomeia o numero: sem rotulo de categoria repetido embaixo do valor
        vis.setdefault("objects", {})["categoryLabels"] = [{"properties": {"show": lit(False)}}]
    if tipo != HTML_CONTENT and "--sem-acabamento" not in sys.argv:
        acabamento(tipo, vis, vco, series=len([c for c in (campos or []) if c[0] in ("Y", "Y2")]))
    return nome, {"$schema": SCHEMA_VISUAL, "name": nome,
                  "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
                  "visual": vis}


def achar_visual(visuais, ref):
    for v in visuais:
        vj = v["json"]
        tit = None
        try:
            tit = vj["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"].strip("'")
        except (KeyError, IndexError, TypeError):
            pass
        if ref in (v["id"], tit):
            return v
    raise SystemExit(f"visual '{ref}' nao encontrado. Ids: {[v['id'] for v in visuais]}")


def figma_nos(chave, node, token):
    req = urllib.request.Request(f"https://api.figma.com/v1/files/{chave}/nodes?ids={node}",
                                 headers={"X-Figma-Token": token})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    doc = d["nodes"][node]["document"]
    fb = doc["absoluteBoundingBox"]
    out = []
    def walk(n):
        for c in n.get("children", []):
            b = c.get("absoluteBoundingBox")
            if b:
                out.append({"nome": c.get("name", ""), "x": b["x"] - fb["x"], "y": b["y"] - fb["y"], "w": b["width"], "h": b["height"]})
            walk(c)
    walk(doc)
    return fb, out


def opt(nome, padrao=None):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        raise SystemExit(f"{nome} precisa de um valor")
    return padrao


def opts(nome):
    return [sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == nome]


def carregar_env():
    for env in (Path.cwd() / ".env",):
        if env.exists():
            for l in env.read_text(encoding="utf-8").splitlines():
                if "=" in l and not l.strip().startswith("#"):
                    k, v = l.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def proximo_z(rel, pagina):
    zs = [v["json"].get("position", {}).get("z", 0) for v in rel.visuais(pagina)]
    return (max(zs) if zs else 0) + 1000


def cmd_nova_pagina(rel, nome, largura, altura, mudancas):
    if any(p["nome"] == nome for p in rel.paginas()):
        raise SystemExit(f"ja existe pagina '{nome}'")
    pid = novo_id()
    pj = {"$schema": SCHEMA_PAGINA, "name": pid, "displayName": nome, "displayOption": "FitToPage",
          "height": altura, "width": largura}
    mudancas[f"Report/definition/pages/{pid}/page.json"] = dump_json(pj)
    chave = "Report/definition/pages/pages.json"
    pages = json.loads(mudancas[chave]) if chave in mudancas else rel.ler_json(chave)
    pages.setdefault("pageOrder", []).append(pid)
    mudancas[chave] = dump_json(pages)
    return {"id": pid, "nome": nome, "json": pj}


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == "tipos":
        for t, p in TIPOS.items():
            print(f"{t:32} {', '.join(p)}")
        return
    alvo = opt("--pbix") or opt("--pbip")
    if not alvo:
        raise SystemExit("--pbix ou --pbip obrigatorio")
    rel = Relatorio(alvo)
    if not rel.pbir:
        raise EstruturaDesconhecida(MSG_LEGADO)
    dry = "--dry-run" in sys.argv
    mud = {}

    if cmd == "listar":
        for p in rel.paginas():
            if opt("--pagina") and p["nome"] != opt("--pagina"):
                continue
            print(f"[{p['nome']}] {p['json'].get('width')}x{p['json'].get('height')}")
            for v in rel.visuais(p):
                pos = v["json"].get("position", {})
                tipo = (v["json"].get("visual") or {}).get("visualType", "grupo")
                print(f"  {v['id']}  {tipo:28} x={pos.get('x', 0):.0f} y={pos.get('y', 0):.0f} w={pos.get('width', 0):.0f} h={pos.get('height', 0):.0f}")
        return

    if cmd == "mover":
        plano = json.loads(Path(opt("--plano")).read_text(encoding="utf-8"))
        for item in plano:
            p = rel.pagina(item["pagina"])
            v = achar_visual(rel.visuais(p), item["visual"])
            pos = v["json"]["position"]
            pos.update({k2: item[k1] for k1, k2 in (("x", "x"), ("y", "y"), ("w", "width"), ("h", "height")) if k1 in item})
            mud[v["arquivo"]] = dump_json(v["json"])
            print(f"{item['pagina']}/{v['id']} -> x={pos['x']} y={pos['y']} w={pos['width']} h={pos['height']}")

    elif cmd == "figma":
        carregar_env()
        token = os.environ.get("FIGMA_TOKEN") or sys.exit("FIGMA_TOKEN nao definido")
        chave = opt("--figma-file") or sys.exit("--figma-file obrigatorio")
        p = rel.pagina(opt("--pagina"))
        fb, nos = figma_nos(chave, opt("--frame"), token)
        ex, ey = p["json"]["width"] / fb["width"], p["json"]["height"] / fb["height"]
        visuais = rel.visuais(p)
        for n in nos:
            try:
                v = achar_visual(visuais, n["nome"])
            except SystemExit:
                continue
            pos = v["json"]["position"]
            pos.update(x=round(n["x"] * ex, 2), y=round(n["y"] * ey, 2), width=round(n["w"] * ex, 2), height=round(n["h"] * ey, 2))
            mud[v["arquivo"]] = dump_json(v["json"])
            print(f"{v['id']} <- '{n['nome']}' x={pos['x']} y={pos['y']} w={pos['width']} h={pos['height']}")
        if not mud:
            print("nenhum retangulo do frame tem nome igual a um id/titulo de visual desta pagina")

    elif cmd == "visual-custom":
        guid = opt("--guid", HTML_CONTENT)
        origem = Relatorio(opt("--de"))
        pref = f"Report/CustomVisuals/{guid}/"
        arquivos = [n for n in origem.nomes() if n.startswith(pref)]
        if not arquivos:
            raise SystemExit(f"'{opt('--de')}' nao contem o visual {guid}")
        for n in arquivos:
            mud[n] = origem.ler(n)
        rpt = rel.ler_json("Report/definition/report.json")
        pub = rpt.setdefault("publicCustomVisuals", [])
        if guid not in pub:
            pub.append(guid)
        mud["Report/definition/report.json"] = dump_json(rpt)
        print(f"visual {guid} copiado ({len(arquivos)} arquivos) e registrado em publicCustomVisuals")

    elif cmd == "nova-pagina":
        cmd_nova_pagina(rel, opt("--nome"), int(opt("--largura", 1280)), int(opt("--altura", 720)), mud)
        print(f"pagina '{opt('--nome')}' criada")

    elif cmd == "criar":
        p = rel.pagina(opt("--pagina"))
        campos = [tuple(c.split("=", 1)) for c in opts("--campo")]
        nome, vj = visual_json(opt("--tipo"), campos, float(opt("--x", 20)), float(opt("--y", 20)),
                               float(opt("--w", 300)), float(opt("--h", 200)), proximo_z(rel, p), opt("--titulo"), opt("--texto"))
        mud[f"Report/definition/pages/{p['id']}/visuals/{nome}/visual.json"] = dump_json(vj)
        print(f"visual {opt('--tipo')} {nome} criado em '{p['nome']}'")

    elif cmd == "lote":
        spec = json.loads(Path(opt("--spec")).read_text(encoding="utf-8"))
        existentes = {p["nome"]: p for p in rel.paginas()}
        for pg in spec["paginas"]:
            if pg["nome"] in existentes:
                p = existentes[pg["nome"]]
                z = proximo_z(rel, p)
            else:
                p = cmd_nova_pagina(rel, pg["nome"], pg.get("largura", 1280), pg.get("altura", 720), mud)
                existentes[pg["nome"]] = p
                z = 1000
            for v in pg.get("visuais", []):
                campos = [tuple(c.split("=", 1)) for c in v.get("campos", [])]
                nome, vj = visual_json(v["tipo"], campos, v["x"], v["y"], v["w"], v["h"], z, v.get("titulo"), v.get("texto"))
                mud[f"Report/definition/pages/{p['id']}/visuals/{nome}/visual.json"] = dump_json(vj)
                z += 1000
            print(f"[{pg['nome']}] {len(pg.get('visuais', []))} visual(is)")
    else:
        raise SystemExit(__doc__)

    if dry:
        print(f"(dry-run) {len(mud)} arquivo(s) seriam gravados")
        return
    bak = rel.gravar(mud)
    print(f"ok. Backup: {bak}")


if __name__ == "__main__":
    try:
        main()
    except EstruturaDesconhecida as e:
        print(f"ESTRUTURA NAO RECONHECIDA: {e}"); sys.exit(2)
    except ArquivoAberto as e:
        print(e); sys.exit(1)

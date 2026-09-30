"""
extrair_dashboard.py - Le um dashboard feito em Excel (.xlsx/.xlsm) ou HTML e extrai:
  - os DADOS em CSV (um por aba/tabela), prontos para virar tabelas no Power BI;
  - a ESTRUTURA em spec.json: graficos (tipo, titulo, series, categorias), KPIs/cartoes,
    tabelas dinamicas, filtros e abas - base para o Claude montar modelo, medidas e paginas.
Parte da skill powerbi-mcp-studio (agente conversor-dashboard). Python 3.9+, sem dependencias.

Uso:
    python extrair_dashboard.py dashboard.xlsx --saida pasta_extraida
    python extrair_dashboard.py painel.html   --saida pasta_extraida

Saida em <pasta>: dados/*.csv, spec.json, resumo.md
"""
import csv, html, json, re, sys, zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
      "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"}
MAPA_GRAFICO = {  # tipo Excel/JS -> visualType do Power BI
    "barChart:col": "clusteredColumnChart", "barChart:bar": "clusteredBarChart", "bar3DChart:col": "clusteredColumnChart",
    "bar3DChart:bar": "clusteredBarChart", "lineChart": "lineChart", "line3DChart": "lineChart", "areaChart": "areaChart",
    "pieChart": "pieChart", "pie3DChart": "pieChart", "doughnutChart": "donutChart", "scatterChart": "scatterChart",
    "bubbleChart": "scatterChart", "radarChart": "lineChart",
    "bar": "clusteredColumnChart", "horizontalBar": "clusteredBarChart", "line": "lineChart", "pie": "pieChart",
    "doughnut": "donutChart", "scatter": "scatterChart", "bubble": "scatterChart", "area": "areaChart",
    "polarArea": "pieChart", "radar": "lineChart", "funnel": "funnel", "gauge": "gauge", "treemap": "treemap",
}


def slug(s):
    s = re.sub(r"[^\w]+", "_", s, flags=re.U).strip("_")
    return s[:50] or "tabela"


def salvar_csv(pasta, nome, linhas):
    pasta.mkdir(parents=True, exist_ok=True)
    p = pasta / f"{slug(nome)}.csv"
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f, delimiter=";").writerows(linhas)
    return p


def tipo_coluna(valores):
    v = [x for x in valores if x not in ("", None)]
    if not v:
        return "texto"
    if all(re.fullmatch(r"-?\d+", str(x)) for x in v):
        return "inteiro"
    if all(re.fullmatch(r"-?\d+([.,]\d+)?(E-?\d+)?", str(x), re.I) for x in v):
        return "decimal"
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}.*|\d{1,2}/\d{1,2}/\d{2,4}", str(x)) for x in v):
        return "data"
    return "texto"


# ------------------------------------------------------------------ Excel
def col_idx(ref):
    letras = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letras:
        n = n * 26 + ord(ch) - 64
    return n - 1


def excel_serial_data(v):
    from datetime import date, timedelta
    try:
        f = float(v)
        if 20000 < f < 80000:
            return (date(1899, 12, 30) + timedelta(days=int(f))).isoformat()
    except ValueError:
        pass
    return v


def ler_xlsx(caminho, saida):
    z = zipfile.ZipFile(caminho)
    nomes = set(z.namelist())
    ss = []
    if "xl/sharedStrings.xml" in nomes:
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            ss.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    # estilos: quais numFmt sao data
    datas_fmt = set()
    if "xl/styles.xml" in nomes:
        st = ET.fromstring(z.read("xl/styles.xml"))
        custom = {n.get("numFmtId"): n.get("formatCode", "") for n in st.iter(f"{{{NS['m']}}}numFmt")}
        xfs = st.find("m:cellXfs", NS)
        for i, xf in enumerate(xfs if xfs is not None else []):
            fid = xf.get("numFmtId", "0")
            code = custom.get(fid, "")
            if fid in {"14", "15", "16", "17", "22"} or re.search(r"[dy]{1,4}.*m|m.*[dy]", code, re.I) and "h" not in code.lower():
                datas_fmt.add(i)
    spec = {"origem": str(caminho), "tipo": "excel", "abas": [], "graficos": [], "kpis": [], "tabelas_dinamicas": [], "nomes_definidos": []}
    for dn in wb.iter(f"{{{NS['m']}}}definedName"):
        spec["nomes_definidos"].append({"nome": dn.get("name"), "ref": dn.text})
    abas = []
    for s in wb.find("m:sheets", NS):
        alvo = rels[s.get(f"{{{NS['r']}}}id")]
        alvo = alvo.lstrip("/") if alvo.startswith("/") else "xl/" + alvo
        abas.append((s.get("name"), alvo, s.get("state")))
    for nome, arq, estado in abas:
        sh = ET.fromstring(z.read(arq))
        grade, formulas = {}, []
        for c in sh.iter(f"{{{NS['m']}}}c"):
            ref = c.get("r"); t = c.get("t"); v = c.find("m:v", NS); f = c.find("m:f", NS)
            val = None
            if t == "s" and v is not None:
                val = ss[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
            elif v is not None:
                val = v.text
                if c.get("s") and int(c.get("s")) in datas_fmt:
                    val = excel_serial_data(val)
            row = int(re.search(r"\d+", ref).group(0)) - 1
            if val is not None:
                grade[(row, col_idx(ref))] = val
            if f is not None and f.text:
                formulas.append({"celula": ref, "formula": "=" + f.text, "valor": val})
        if not grade:
            continue
        # detecta blocos de tabela: linhas contiguas com >=2 colunas preenchidas
        linhas = sorted({r for r, _ in grade})
        cols = sorted({c for _, c in grade})
        mat = [[grade.get((r, c), "") for c in range(min(cols), max(cols) + 1)] for r in range(min(linhas), max(linhas) + 1)]
        blocos, atual = [], []
        for linha in mat:
            if sum(1 for x in linha if x != "") >= 2:
                atual.append(linha)
            else:
                if len(atual) >= 3:
                    blocos.append(atual)
                atual = []
        if len(atual) >= 3:
            blocos.append(atual)
        tabelas = []
        for i, b in enumerate(blocos):
            usadas = [j for j in range(len(b[0])) if any(l[j] != "" for l in b)]
            b = [[l[j] for j in usadas] for l in b]
            nome_csv = nome if len(blocos) == 1 else f"{nome}_{i + 1}"
            p = salvar_csv(saida / "dados", nome_csv, b)
            cab = [str(x) for x in b[0]]
            tabelas.append({"csv": str(p.relative_to(saida)), "linhas": len(b) - 1, "colunas": cab,
                            "tipos": {cab[j]: tipo_coluna([l[j] for l in b[1:]]) for j in range(len(cab))}})
        # KPIs: formulas de agregacao isoladas
        for f in formulas:
            if re.match(r"=\s*(SUM|SOMA|AVERAGE|MEDIA|MÉDIA|COUNT|CONT|MAX|MIN|SUBTOTAL)\w*\(", f["formula"], re.I):
                spec["kpis"].append(dict(f, aba=nome))
        spec["abas"].append({"nome": nome, "oculta": estado in ("hidden", "veryHidden"), "tabelas": tabelas,
                             "formulas": len(formulas)})
    # graficos
    for n in sorted(nomes):
        if re.match(r"xl/charts/chart\d+\.xml$", n):
            ch = ET.fromstring(z.read(n))
            plot = ch.find(".//c:plotArea", NS)
            titulo = "".join(t.text or "" for t in ch.findall(".//c:title//a:t", NS)) or None
            for g in list(plot or []):
                tag = g.tag.split("}")[1]
                if not tag.endswith("Chart"):
                    continue
                direcao = g.find("c:barDir", NS)
                chave = f"{tag}:{direcao.get('val')}" if direcao is not None else tag
                series = []
                for s in g.findall("c:ser", NS):
                    series.append({"nome": "".join(t.text or "" for t in s.findall(".//c:tx//c:v", NS)) or
                                   (s.find(".//c:tx//c:f", NS).text if s.find(".//c:tx//c:f", NS) is not None else None),
                                   "categorias": (s.find(".//c:cat//c:f", NS).text if s.find(".//c:cat//c:f", NS) is not None else None),
                                   "valores": (s.find(".//c:val//c:f", NS).text if s.find(".//c:val//c:f", NS) is not None else
                                               s.find(".//c:yVal//c:f", NS).text if s.find(".//c:yVal//c:f", NS) is not None else None)})
                agrup = g.find("c:grouping", NS)
                visual = MAPA_GRAFICO.get(chave, MAPA_GRAFICO.get(tag, "clusteredColumnChart"))
                if agrup is not None and agrup.get("val") in ("stacked", "percentStacked") and "Column" in visual:
                    visual = "stackedColumnChart"
                spec["graficos"].append({"arquivo": n, "titulo": titulo, "tipo_origem": chave, "visual_pbi": visual, "series": series})
        if re.match(r"xl/pivotTables/pivotTable\d+\.xml$", n):
            pt = ET.fromstring(z.read(n))
            spec["tabelas_dinamicas"].append({"arquivo": n, "nome": pt.get("name"),
                                              "valores": [d.get("name") for d in pt.iter(f"{{{NS['m']}}}dataField")]})
    return spec


# ------------------------------------------------------------------ HTML
class Tabelas(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tabelas, self.pilha, self.linha, self.celula = [], [], None, None
        self.titulos, self._ult_titulo, self._em_titulo = [], None, False
        self.kpis, self._kpi = [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "") + " " + (a.get("id") or "")
        if tag == "table":
            self.pilha.append({"titulo": self._ult_titulo, "linhas": []})
        elif tag == "tr" and self.pilha:
            self.linha = []
        elif tag in ("td", "th") and self.linha is not None:
            self.celula = []
        elif tag in ("h1", "h2", "h3", "h4", "caption"):
            self._em_titulo, self._buf = True, []
        if re.search(r"\b(kpi|metric|stat|card-value|big-number|indicador|valor)\b", cls, re.I) and self._kpi is None:
            self._kpi = {"classe": cls.strip(), "texto": [], "prof": 0, "tag": tag}
        elif self._kpi is not None and tag == self._kpi["tag"]:
            self._kpi["prof"] += 1

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.celula is not None and self.linha is not None:
            self.linha.append(" ".join("".join(self.celula).split()))
            self.celula = None
        elif tag == "tr" and self.linha is not None and self.pilha:
            if self.linha:
                self.pilha[-1]["linhas"].append(self.linha)
            self.linha = None
        elif tag == "table" and self.pilha:
            self.tabelas.append(self.pilha.pop())
        elif tag in ("h1", "h2", "h3", "h4", "caption") and self._em_titulo:
            self._ult_titulo = " ".join("".join(self._buf).split()); self._em_titulo = False
            self.titulos.append(self._ult_titulo)
        if self._kpi is not None and tag == self._kpi["tag"]:
            if self._kpi["prof"] == 0:
                t = " ".join(" ".join(self._kpi["texto"]).split())
                if t and len(t) < 120:
                    self.kpis.append({"classe": self._kpi["classe"], "texto": t})
                self._kpi = None
            else:
                self._kpi["prof"] -= 1

    def handle_data(self, d):
        if self.celula is not None:
            self.celula.append(d)
        if self._em_titulo:
            self._buf.append(d)
        if self._kpi is not None:
            self._kpi["texto"].append(d)


def js_para_json(txt):
    """Converte um literal de objeto JS simples em JSON (chaves sem aspas, aspas simples, virgula final)."""
    t = re.sub(r"//[^\n]*", "", txt)
    t = re.sub(r"(?<=[{,\s])([A-Za-z_]\w*)\s*:", r'"\1":', t)
    t = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", lambda m: json.dumps(m.group(1)), t)
    t = re.sub(r",\s*([}\]])", r"\1", t)
    t = re.sub(r":\s*(function[^{]*\{.*?\}|[A-Za-z_$][\w$.]*\([^)]*\))", ': null', t, flags=re.S)
    return json.loads(t)


def bloco(texto, inicio):
    """Devolve o trecho balanceado {...} a partir de texto[inicio] == '{'."""
    prof, i, em_str = 0, inicio, None
    while i < len(texto):
        ch = texto[i]
        if em_str:
            if ch == "\\":
                i += 1
            elif ch == em_str:
                em_str = None
        elif ch in "'\"`":
            em_str = ch
        elif ch == "{":
            prof += 1
        elif ch == "}":
            prof -= 1
            if prof == 0:
                return texto[inicio:i + 1]
        i += 1
    return None


def ler_html(caminho, saida):
    txt = Path(caminho).read_text(encoding="utf-8", errors="replace")
    p = Tabelas(); p.feed(txt)
    spec = {"origem": str(caminho), "tipo": "html", "titulo": (re.search(r"<title>(.*?)</title>", txt, re.S | re.I) or [None, None])[1],
            "tabelas": [], "graficos": [], "kpis": p.kpis[:40], "titulos": p.titulos[:40], "bibliotecas": []}
    for lib, pad in (("Chart.js", r"new\s+Chart\s*\("), ("ECharts", r"echarts\.init"), ("Plotly", r"Plotly\.(newPlot|react)"),
                     ("Highcharts", r"Highcharts\.chart"), ("ApexCharts", r"new\s+ApexCharts"), ("Google Charts", r"google\.visualization"),
                     ("D3", r"\bd3\.select")):
        if re.search(pad, txt):
            spec["bibliotecas"].append(lib)
    for i, t in enumerate(p.tabelas):
        if len(t["linhas"]) < 2:
            continue
        nome = t["titulo"] or f"tabela_{i + 1}"
        arq = salvar_csv(saida / "dados", nome, t["linhas"])
        cab = t["linhas"][0]
        spec["tabelas"].append({"csv": str(arq.relative_to(saida)), "titulo": t["titulo"], "linhas": len(t["linhas"]) - 1,
                                "colunas": cab, "tipos": {cab[j]: tipo_coluna([l[j] if j < len(l) else "" for l in t["linhas"][1:]])
                                                          for j in range(len(cab))}})
    # Chart.js: new Chart(ctx, { type:'bar', data:{ labels:[...], datasets:[{label, data:[...]}] }, options:{ plugins:{title:{text}} } })
    for m in re.finditer(r"new\s+Chart\s*\([^,]+,\s*", txt):
        b = bloco(txt, m.end())
        if not b:
            continue
        try:
            cfg = js_para_json(b)
        except Exception:
            spec["graficos"].append({"biblioteca": "Chart.js", "erro": "configuracao nao interpretada", "trecho": b[:300]}); continue
        tipo = cfg.get("type", "bar")
        data = cfg.get("data") or {}
        titulo = (((cfg.get("options") or {}).get("plugins") or {}).get("title") or {}).get("text") or \
                 (((cfg.get("options") or {}).get("title") or {}).get("text"))
        if ((cfg.get("options") or {}).get("indexAxis") == "y") and tipo == "bar":
            tipo = "horizontalBar"
        g = {"biblioteca": "Chart.js", "titulo": titulo, "tipo_origem": tipo, "visual_pbi": MAPA_GRAFICO.get(tipo, "clusteredColumnChart"),
             "categorias": data.get("labels"), "series": [{"nome": d.get("label"), "valores": d.get("data")} for d in data.get("datasets", [])]}
        if g["categorias"] and g["series"] and all(isinstance(s["valores"], list) for s in g["series"]):
            linhas = [["Categoria"] + [s["nome"] or f"Serie{k + 1}" for k, s in enumerate(g["series"])]]
            for k, cat in enumerate(g["categorias"]):
                linhas.append([cat] + [s["valores"][k] if k < len(s["valores"]) else "" for s in g["series"]])
            g["csv"] = str(salvar_csv(saida / "dados", f"grafico_{slug(titulo or tipo)}_{len(spec['graficos']) + 1}", linhas).relative_to(saida))
        spec["graficos"].append(g)
    # ECharts: setOption({ title:{text}, xAxis:{data}, series:[{type, name, data}] })
    for m in re.finditer(r"\.setOption\s*\(\s*", txt):
        b = bloco(txt, m.end())
        if not b:
            continue
        try:
            cfg = js_para_json(b)
        except Exception:
            spec["graficos"].append({"biblioteca": "ECharts", "erro": "configuracao nao interpretada", "trecho": b[:300]}); continue
        xa = cfg.get("xAxis") or {}
        xa = xa[0] if isinstance(xa, list) and xa else xa
        tit = cfg.get("title") or {}
        tit = tit[0] if isinstance(tit, list) and tit else tit
        for s in cfg.get("series", []) if isinstance(cfg.get("series"), list) else []:
            tipo = s.get("type", "bar")
            g = {"biblioteca": "ECharts", "titulo": tit.get("text"), "tipo_origem": tipo,
                 "visual_pbi": MAPA_GRAFICO.get(tipo, "clusteredColumnChart"), "categorias": xa.get("data"),
                 "series": [{"nome": s.get("name"), "valores": s.get("data")}]}
            spec["graficos"].append(g)
    # Plotly: Plotly.newPlot(el, [ {x:[...], y:[...], type:'bar', name} ], {title})
    for m in re.finditer(r"Plotly\.(?:newPlot|react)\s*\([^,]+,\s*\[", txt):
        ini, prof, fim = m.end() - 1, 0, None
        for k in range(ini, len(txt)):
            if txt[k] == "[":
                prof += 1
            elif txt[k] == "]":
                prof -= 1
                if prof == 0:
                    fim = k; break
        trecho = txt[ini:(fim or ini) + 1]
        pos = 1
        while True:
            a = trecho.find("{", pos)
            if a < 0:
                break
            b = bloco(trecho, a)
            if not b:
                break
            pos = a + len(b)
            try:
                d = js_para_json(b)
            except Exception:
                continue
            if "x" in d or "y" in d or "values" in d:
                tipo = d.get("type", "scatter")
                spec["graficos"].append({"biblioteca": "Plotly", "tipo_origem": tipo, "titulo": d.get("name"),
                                         "visual_pbi": "lineChart" if tipo == "scatter" and str(d.get("mode", "")).startswith("lines") else MAPA_GRAFICO.get(tipo, "scatterChart"),
                                         "categorias": d.get("x") or d.get("labels"), "series": [{"nome": d.get("name"), "valores": d.get("y") or d.get("values")}]})
    return spec


def resumo(spec):
    L = [f"# Extracao: {Path(spec['origem']).name}", "", f"Tipo: **{spec['tipo']}**", ""]
    if spec["tipo"] == "excel":
        for a in spec["abas"]:
            L.append(f"- Aba **{a['nome']}**{' (oculta)' if a['oculta'] else ''}: {len(a['tabelas'])} tabela(s), {a['formulas']} formula(s)")
            for t in a["tabelas"]:
                L.append(f"  - `{t['csv']}` - {t['linhas']} linhas - colunas: {', '.join(c + ' (' + t['tipos'][c] + ')' for c in t['colunas'])}")
        L += ["", f"Tabelas dinamicas: {len(spec['tabelas_dinamicas'])}", f"KPIs (formulas de agregacao): {len(spec['kpis'])}"]
    else:
        L.append(f"Bibliotecas de grafico: {', '.join(spec['bibliotecas']) or 'nenhuma detectada'}")
        for t in spec["tabelas"]:
            L.append(f"- Tabela `{t['csv']}` ({t['titulo'] or 'sem titulo'}) - {t['linhas']} linhas - {', '.join(t['colunas'])}")
        L.append(f"\nKPIs/cartoes detectados: {len(spec['kpis'])}")
        for k in spec["kpis"][:10]:
            L.append(f"  - {k['texto']}")
    L += ["", f"Graficos: {len(spec['graficos'])}"]
    for g in spec["graficos"]:
        L.append(f"- {g.get('titulo') or '(sem titulo)'}: {g.get('tipo_origem')} -> **{g.get('visual_pbi')}**"
                 + (f" (dados em `{g['csv']}`)" if g.get("csv") else "") + (f" ERRO: {g['erro']}" if g.get("erro") else ""))
    return "\n".join(L)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    origem = Path(sys.argv[1])
    saida = Path(sys.argv[sys.argv.index("--saida") + 1]) if "--saida" in sys.argv else origem.with_suffix("")
    saida.mkdir(parents=True, exist_ok=True)
    ext = origem.suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        spec = ler_xlsx(origem, saida)
    elif ext in (".html", ".htm"):
        spec = ler_html(origem, saida)
    elif ext == ".xls":
        raise SystemExit("Formato .xls antigo: abra no Excel e salve como .xlsx")
    else:
        raise SystemExit(f"extensao nao suportada: {ext}")
    (saida / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    r = resumo(spec)
    (saida / "resumo.md").write_text(r, encoding="utf-8")
    print(r)
    print(f"\nArquivos em {saida}")


if __name__ == "__main__":
    main()

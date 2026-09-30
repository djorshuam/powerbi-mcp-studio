"""
html_dax.py - Modo "HTML Content": transforma um layout.json em MEDIDAS DAX que geram HTML/SVG (cartoes KPI,
barras, colunas, linha com area, realizado x meta, tabela) para o visual HTML Content, com o mesmo estilo do
dashboard HTML (cores do DESIGN.md). Segmentacoes continuam nativas e filtram tudo. Parte da skill powerbi-mcp-studio.

Uso:
    python html_dax.py --layout layout.json --design DESIGN.md [--escuro] [--pasta "4. Visual (HTML)"] \
        --medidas-saida medidas_html.json --layout-saida layout_html.json

Depois:
    1. MCP measure_operations Create com medidas_html.json (tabela _Medidas, pasta indicada)  [Desktop ABERTO]
    2. O relatorio precisa ter o visual HTML Content (AppSource, guid htmlContent443BE3AD55E043BF878BED274D3A6855):
       adicione uma vez pela interface (Mais visuais > Obter mais visuais > "HTML Content") OU copie de outro .pbix com
       python visuais_pbi.py visual-custom --pbix X.pbix --de outro.pbix --guid htmlContent443BE3AD55E043BF878BED274D3A6855
    3. visuais_pbi.py lote --spec layout_html.json + svg_fundo.py (mesmo fluxo)            [Desktop FECHADO]

Campos aceitos no layout: Medida:_Medidas[X] (recomendado) e Coluna:Tabela[Coluna]. Somas implicitas nao
(o padrao de modelagem da skill usa medidas explicitas).
Limites: sem clique para filtrar (use segmentacoes nativas); ate ~50 categorias por grafico.
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
GUID = "htmlContent443BE3AD55E043BF878BED274D3A6855"


def a(n, d=None):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


def ref(spec):
    m = re.fullmatch(r"\s*(\w+)\s*:\s*'?([^'\[]+?)'?\s*\[([^\]]+)\]\s*", spec)
    if not m:
        raise SystemExit(f"campo invalido: {spec}")
    tipo, t, c = m.groups()
    if tipo == "Medida":
        return {"k": "m", "dax": f"[{c}]", "nome": c}
    if tipo == "Coluna":
        return {"k": "c", "dax": f"'{t}'[{c}]", "nome": c, "t": t}
    raise SystemExit(f"'{spec}': no modo HTML use medidas explicitas (Medida:_Medidas[...]); rode modelagem_pbi.py remapear")


def dq(s):
    return s.replace('"', '""')


def fmt_expr(v, nome, pct_hint=False):
    """Formatacao compacta pt-BR em DAX (R$, mil/mi, %)."""
    if pct_hint or re.search(r"%|ating|margem|taxa|perc|conversao", nome, re.I):
        return f'FORMAT({v}, "0.0%")'
    moeda = re.search(r"valor|venda|receita|custo|meta|ticket|preco|faturamento|lucro|despesa", nome, re.I)
    p = '"R$ " & ' if moeda else ""
    return (f'IF(ISBLANK({v}), "-", {p}IF(ABS({v}) >= 1E9, FORMAT({v} / 1E9, "#,0.00") & " bi", IF(ABS({v}) >= 1E6, FORMAT({v} / 1E6, "#,0.00") & " mi", '
            f'IF(ABS({v}) >= 1E4, FORMAT({v} / 1E3, "#,0.0") & " mil", FORMAT({v}, "#,0.##")))))')


def num(v):
    return f'FORMAT({v}, "0.0", "en-US")'


class Gerador:
    def __init__(self, c, pal):
        self.c, self.pal = c, pal
        F = "font-family:Segoe UI,Arial,sans-serif"
        self.base = f"{F};color:{c['texto']};box-sizing:border-box;width:100%;overflow:hidden"
        self.tit = f"font-size:13px;font-weight:600;color:{c['texto']};margin:0 0 6px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"

    def cab(self, titulo):
        return f"<div style='{self.base}'><div style='{self.tit}'>{dq(titulo)}</div>"

    def kpi(self, titulo, m):
        v = m["dax"]
        return (f'VAR _v = {v}\nRETURN\n"{self.cab(titulo)}<div style=\'font-size:34px;font-weight:300;letter-spacing:-0.5px;line-height:1.15;margin-top:4px\'>" & '
                f'{fmt_expr("_v", m["nome"])} & "</div></div>"')

    def barras(self, titulo, cat, m, top=12):
        c = self.c
        linha = (f'"<div style=\'display:flex;align-items:center;gap:8px;margin:6px 0;font-size:12px\'>'
                 f'<div style=\'width:34%;color:{c["mudo"]};white-space:nowrap;overflow:hidden;text-overflow:ellipsis\'>" & {cat["dax"]} & "</div>'
                 f'<div style=\'flex:1;background:{c["trilho"]};border-radius:5px;height:14px\'><div style=\'width:" & {num("DIVIDE([@v], _mx) * 100")} & "%;height:14px;border-radius:5px;background:{self.pal[0]}\'></div></div>'
                 f'<div style=\'width:72px;text-align:right;font-variant-numeric:tabular-nums\'>" & {fmt_expr("[@v]", m["nome"])} & "</div></div>"')
        return (f'VAR _t = FILTER(ADDCOLUMNS(VALUES({cat["dax"]}), "@v", {m["dax"]}), NOT ISBLANK([@v]))\nVAR _mx = MAXX(_t, [@v])\nRETURN\n'
                f'"{self.cab(titulo)}" & CONCATENATEX(TOPN({top}, _t, [@v], DESC), {linha}, "", [@v], DESC) & "</div>"')

    def colunas(self, titulo, cat, ms, tempo, altura=160):
        area = max(40, int(altura) - 26 - 22)  # titulo + rotulos
        c, pal = self.c, self.pal
        ordem = f"{cat['dax']}, ASC" if tempo else "[@v0], DESC"
        cols = ", ".join(f'"@v{i}", {m["dax"]}' for i, m in enumerate(ms))
        barras = " & ".join(
            f'"<div title=\'{dq(m["nome"])}: " & {fmt_expr(f"[@v{i}]", m["nome"])} & "\' style=\'flex:1;max-width:26px;background:{pal[i % len(pal)]};border-radius:4px 4px 0 0;height:" & {num(f"DIVIDE([@v{i}], _mx) * {area}")} & "px\'></div>"'
            for i, m in enumerate(ms))
        item = (f'"<div style=\'flex:1;display:flex;flex-direction:column;align-items:center;min-width:0\'><div style=\'height:{area}px;width:100%;display:flex;align-items:flex-end;justify-content:center;gap:3px\'>" & '
                f'{barras} & "</div><div style=\'font-size:10.5px;color:{c["mudo"]};margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%\'>" & {cat["dax"]} & "</div></div>"')
        leg = "".join(f"<span style='display:inline-flex;align-items:center;gap:4px;margin-left:10px'><span style='width:9px;height:9px;border-radius:2px;background:{pal[i % len(pal)]}'></span>{dq(m['nome'])}</span>" for i, m in enumerate(ms)) if len(ms) > 1 else ""
        mx = " , ".join(f"MAXX(_t, [@v{i}])" for i in range(len(ms)))
        return (f'VAR _t = FILTER(ADDCOLUMNS(VALUES({cat["dax"]}), {cols}), NOT ISBLANK([@v0]))\nVAR _mx = MAX({mx if len(ms) > 1 else mx + ", 0"})\nRETURN\n'
                f'"<div style=\'{self.base};display:flex;flex-direction:column\'><div style=\'display:flex;justify-content:space-between;align-items:center\'><div style=\'{self.tit}\'>{dq(titulo)}</div>'
                f'<div style=\'font-size:11px;color:{c["mudo"]};white-space:nowrap\'>{leg}</div></div>'
                f'<div style=\'display:flex;gap:6px;align-items:flex-end\'>" & CONCATENATEX(_t, {item}, "", {ordem}) & "</div></div>"')

    def linha(self, titulo, cat, m, altura=240):
        c, p = self.c, self.pal[0]
        hsvg = max(60, int(altura) - 26 - 18)
        W, H = 1000, 300
        return (f'VAR _t = FILTER(ADDCOLUMNS(VALUES({cat["dax"]}), "@v", {m["dax"]}), NOT ISBLANK([@v]))\n'
                f'VAR _n = COUNTROWS(_t)\nVAR _t2 = ADDCOLUMNS(_t, "@i", RANKX(_t, {cat["dax"]}, , ASC, DENSE))\n'
                f'VAR _mx = MAXX(_t2, [@v]) * 1.08\nVAR _mn = MIN(0, MINX(_t2, [@v]))\n'
                f'VAR _pts = CONCATENATEX(_t2, {num(f"DIVIDE([@i] - 1, MAX(_n - 1, 1)) * {W}")} & "," & {num(f"{H} - DIVIDE([@v] - _mn, _mx - _mn) * {H}")}, " ", [@i], ASC)\n'
                f'VAR _ult = MAXX(TOPN(1, _t2, [@i], DESC), [@v])\n'
                f'VAR _ini = MINX(_t2, {cat["dax"]})\nVAR _fim = MAXX(_t2, {cat["dax"]})\nRETURN\n'
                f'"<div style=\'{self.base};display:flex;flex-direction:column\'><div style=\'display:flex;justify-content:space-between\'><div style=\'{self.tit}\'>{dq(titulo)}</div>'
                f'<div style=\'font-size:12px;color:{c["mudo"]}\'>ultimo: <b style=\'color:{c["texto"]}\'>" & {fmt_expr("_ult", m["nome"])} & "</b></div></div>'
                f'<svg viewBox=\'0 -10 {W} {H + 20}\' preserveAspectRatio=\'none\' style=\'display:block;width:100%;height:{hsvg}px\'>'
                f'<line x1=\'0\' y1=\'{H}\' x2=\'{W}\' y2=\'{H}\' stroke=\'{c["borda"]}\' stroke-width=\'1\'/>'
                f'<polygon points=\'0,{H} " & _pts & " {W},{H}\' fill=\'{p}\' fill-opacity=\'0.12\'/>'
                f'<polyline points=\'" & _pts & "\' fill=\'none\' stroke=\'{p}\' stroke-width=\'3\' vector-effect=\'non-scaling-stroke\' stroke-linejoin=\'round\'/></svg>'
                f'<div style=\'display:flex;justify-content:space-between;font-size:10.5px;color:{c["mudo"]}\'><span>" & _ini & "</span><span>" & _fim & "</span></div></div>"')

    def tabela(self, titulo, campos, top=15):
        c = self.c
        cats = [f for f in campos if f["k"] == "c"]
        ms = [f for f in campos if f["k"] == "m"]
        if not cats:
            raise SystemExit("tabela HTML precisa de ao menos uma coluna")
        grp = ", ".join(f["dax"] for f in cats)
        cols = ", ".join(f'"@m{i}", {m["dax"]}' for i, m in enumerate(ms))
        th = "".join(f"<th style='text-align:left;padding:5px 6px;color:{c['mudo']};border-bottom:2px solid {self.pal[0]}'>{dq(f['nome'])}</th>" for f in cats)
        th += "".join(f"<th style='text-align:right;padding:5px 6px;color:{c['mudo']};border-bottom:2px solid {self.pal[0]}'>{dq(m['nome'])}</th>" for m in ms)
        td = " & ".join([f'"<td style=\'padding:4px 6px;border-bottom:1px solid {c["borda"]}\'>" & {f["dax"]} & "</td>"' for f in cats] +
                        [f'"<td style=\'padding:4px 6px;text-align:right;border-bottom:1px solid {c["borda"]}\'>" & {fmt_expr(f"[@m{i}]", m["nome"])} & "</td>"' for i, m in enumerate(ms)])
        ordem = "[@m0], DESC" if ms else f"{cats[0]['dax']}, ASC"
        return (f'VAR _t = FILTER(ADDCOLUMNS(SUMMARIZE(\'{cats[0]["t"]}\', {grp}){", " + cols if ms else ""}), {"NOT ISBLANK([@m0])" if ms else "TRUE()"})\nRETURN\n'
                f'"{self.cab(titulo)}<table style=\'width:100%;border-collapse:collapse;font-size:12px\'><tr>{th}</tr>" & '
                f'CONCATENATEX(TOPN({top}, _t, {ordem.split(",")[0]}, {ordem.split(",")[1].strip()}), "<tr>" & {td} & "</tr>", "", {ordem}) & "</table></div>"')


def main():
    if not a("--layout"):
        raise SystemExit(__doc__)
    from svg_fundo import paleta
    from tema_pbi import tokens_de_design, ajustar_modo, clarear, lum
    escuro = "--escuro" in sys.argv
    c = paleta(a("--design"), escuro)
    c["trilho"] = clarear(c["card"], -0.05 if lum(c["card"]) > 0.4 else 0.08)
    pal = [c["p"], "#94A3B8", "#E8833A", "#2A9D8F"]
    if a("--design"):
        t, _ = tokens_de_design(Path(a("--design")).read_text(encoding="utf-8"), "x")
        t, _ = ajustar_modo(t, "escuro" if escuro else "claro")
        pal = [c["p"]] + [x for x in t["colors"]["palette"] if x.upper() != c["p"].upper()][:3]
    g = Gerador(c, pal)
    pasta = a("--pasta", "4. Visual (HTML)")
    spec = json.loads(Path(a("--layout")).read_text(encoding="utf-8"))
    medidas, n = [], 0
    for pg in spec["paginas"]:
        for v in pg["visuais"]:
            if v["tipo"] in ("slicer", "textbox") or not v.get("campos"):
                continue
            campos = [(x.split("=", 1)[0], ref(x.split("=", 1)[1])) for x in v["campos"]]
            cat = next((f for p, f in campos if p in ("Category", "Group", "Rows") and f["k"] == "c"), None)
            ms = [f for p, f in campos if f["k"] == "m"]
            titulo = v.get("titulo") or (ms[0]["nome"] if ms else "")
            tipo = v["tipo"]
            util = v["h"] - 2 * float(a("--padding", 8)) - 12  # espaco do cartao - respiro - margem interna do visual
            tempo = bool(cat and re.search(r"mes|data|date|ano|periodo|semana", cat["nome"], re.I))
            if tipo in ("card", "cardVisual", "kpi", "gauge", "multiRowCard"):
                dax = g.kpi(titulo, ms[0])
            elif tipo in ("tableEx", "pivotTable"):
                dax = g.tabela(titulo, [f for _, f in campos])
            elif tipo in ("lineChart", "areaChart") and cat and len(ms) == 1:
                dax = g.linha(titulo, cat, ms[0], util)
            elif cat and (tempo or len(ms) > 1 or tipo in ("clusteredColumnChart", "stackedColumnChart")) and tipo not in ("clusteredBarChart",):
                dax = g.colunas(titulo, cat, ms, tempo, util)
            elif cat:
                dax = g.barras(titulo, cat, ms[0])
            else:
                dax = g.kpi(titulo, ms[0])
            n += 1
            nome = f"HTML {n:02d} {re.sub(r'[^A-Za-z0-9 ]', '', titulo)[:40]}".strip()
            medidas.append({"name": nome, "tableName": "_Medidas", "expression": dax, "displayFolder": pasta,
                            "description": f"HTML Content: {v['tipo']} '{titulo}' (gerado por html_dax.py)"})
            v["tipo"] = GUID
            v["campos"] = [f"content=Medida:_Medidas[{nome}]"]
            v["html"] = True
    Path(a("--medidas-saida", "medidas_html.json")).write_text(json.dumps(medidas, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(a("--layout-saida", "layout_html.json")).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(medidas)} medidas HTML -> {a('--medidas-saida', 'medidas_html.json')}; layout -> {a('--layout-saida', 'layout_html.json')}")


if __name__ == "__main__":
    main()

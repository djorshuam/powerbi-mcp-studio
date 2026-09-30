"""
svg_fundo.py - Fundo de pagina em SVG sem depender do Figma: extrair, inspecionar, GERAR um layout
moderno a partir dos visuais (cartoes com sombra, cabecalho, KPIs com destaque, grade) e aplicar.
Parte da skill powerbi-mcp-studio.

SVG e texto (XML): o Claude pode editar rotulos, cores e formas direto no arquivo entre "gerar/extrair"
e "aplicar". SVG exportado do Figma com texto em contorno nao tem <text> editavel.

Uso:
    python svg_fundo.py extrair --pbix X.pbix --pagina "P" --saida fundo.svg
    python svg_fundo.py listar fundo.svg
    python svg_fundo.py gerar --pbix X.pbix --pagina "P" --saida fundo.svg [opcoes]
    python svg_fundo.py gerar --layout layout.json --pagina "P" --saida fundo.svg [opcoes]
    python svg_fundo.py previa --svg fundo.svg --plano plano.json --saida previa.png   (precisa Playwright/Chromium)
    python svg_fundo.py aplicar --pbix X.pbix --pagina "P" --arquivo fundo.svg [--plano plano.json] [--visuais-transparentes]

Opcoes de "gerar":
    --design DESIGN.md        cores do cliente/galeria (padrao: neutro azul)
    --estilo cartoes|minimal|contraste   (padrao cartoes)
    --escuro                  versao dark
    --titulo "..." --subtitulo "..."     cabecalho desenhado no fundo (caixas de texto no topo sao ocultadas no aplicar)
    --reorganizar             encaixa os visuais numa grade (margem 24, espaco 16, linhas preservadas) e grava
                              o plano (posicoes novas) em <saida>.plano.json - use no "aplicar --plano"
    --margem 24 --espaco 16 --padding 10 --raio 12

Fluxo recomendado: gerar --reorganizar -> previa (olhar!) -> ajustar -> aplicar --plano ... --visuais-transparentes
"""
import json, random, re, sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pbi_arquivo import Relatorio, EstruturaDesconhecida, ArquivoAberto, dump_json, MSG_LEGADO  # noqa: E402

SVGNS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVGNS)
RES = "Report/StaticResources/RegisteredResources/"
KPI = {"card", "cardVisual", "multiRowCard", "kpi", "gauge"}
HTML = "htmlContent443BE3AD55E043BF878BED274D3A6855"


def eh_kpi(b):
    t = b.get("tipo")
    return t in KPI or (t == HTML and b.get("h", 999) <= 176)
FILTRO = {"slicer", "advancedSlicerVisual"}
IGNORAR = {None, "image", "shape", "actionButton", "pageNavigator", "bookmarkNavigator"}


def opt(nome, padrao=None):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        raise SystemExit(f"{nome} precisa de um valor")
    return padrao


def item_fundo(pj):
    try:
        return pj["objects"]["background"][0]["properties"]["image"]["image"]["url"]["expr"]["ResourcePackageItem"]["ItemName"]
    except (KeyError, IndexError, TypeError):
        return None


# ------------------------------------------------------------------ cores
def paleta(design, escuro):
    from tema_pbi import tokens_de_design, ajustar_modo, clarear, lum, hls, de_hls
    if design:
        t, _ = tokens_de_design(Path(design).read_text(encoding="utf-8"), Path(design).parent.name)
    else:
        t = {"colors": {"primary": "#2F6FDE", "background": "#FFFFFF", "surface": "#FFFFFF", "text": "#1B2B3A",
                        "text_muted": "#5B7086", "border": "#E1E6EC", "good": "#1A7F37", "bad": "#D1242F",
                        "neutral": "#BF8700", "palette": ["#2F6FDE"]}, "name": "padrao"}
    t, _ = ajustar_modo(t, "escuro" if escuro else "claro")
    k = t["colors"]
    p = k["primary"]
    h, l, s = hls(p)
    if escuro:
        fundo = k["background"]
        card = clarear(fundo, 0.05)
        return {"fundo": fundo, "fundo2": de_hls(h, max(0.05, hls(fundo)[1] + 0.02), min(0.5, s)), "card": card,
                "borda": clarear(fundo, 0.12), "texto": k["text"], "mudo": k["text_muted"], "p": p,
                "p_suave": de_hls(h, 0.22, min(0.6, s)), "sombra": "#000000", "sombra_op": 0.35, "filtro": clarear(fundo, 0.03)}
    fundo = k["background"] if lum(k["background"]) < 0.97 else de_hls(h, 0.965, min(0.35, s))
    return {"fundo": fundo, "fundo2": de_hls(h, 0.94, min(0.45, s)), "card": "#FFFFFF" if lum(k["surface"]) > 0.9 else k["surface"],
            "borda": k["border"], "texto": k["text"], "mudo": k["text_muted"], "p": p,
            "p_suave": de_hls(h, 0.92, min(0.7, s)), "sombra": de_hls(h, 0.25, 0.3), "sombra_op": 0.07, "filtro": de_hls(h, 0.975, min(0.4, s))}


# ------------------------------------------------------------------ grade
def reorganizar(caixas, W, H, topo, margem, espaco):
    """Agrupa em linhas pela posicao original e redistribui numa grade limpa, preservando proporcoes."""
    if not caixas:
        return []
    ordem = sorted(caixas, key=lambda b: (b["y"], b["x"]))
    linhas, atual, fim = [], [], None
    for b in ordem:
        if atual and b["y"] >= fim - 0.35 * min(b["h"], max(x["h"] for x in atual)):
            linhas.append(atual); atual = []
        atual.append(b)
        fim = max(x["y"] + x["h"] for x in atual)
    linhas.append(atual)
    alturas = [max(x["h"] for x in ln) for ln in linhas]
    disp_h = H - topo - margem - espaco * (len(linhas) - 1)
    fator = disp_h / sum(alturas)
    out, y = [], topo
    for ln, alt in zip(linhas, alturas):
        h = round(alt * fator / 8) * 8
        if all(eh_kpi(b) for b in ln):
            h = max(h, 144)  # cartoes precisam de altura para titulo + valor
        elif all(b.get("tipo") in FILTRO for b in ln) and all(b["h"] < 120 for b in ln):
            h = min(max(h, 64), 88)  # faixa de filtros suspensos: baixa
        ln = sorted(ln, key=lambda b: b["x"])
        disp_w = W - 2 * margem - espaco * (len(ln) - 1)
        soma = sum(b["w"] for b in ln)
        x = margem
        for i, b in enumerate(ln):
            w = disp_w - (x - margem - espaco * i) if i == len(ln) - 1 else round(b["w"] / soma * disp_w / 8) * 8
            out.append(dict(b, x=x, y=y, w=w, h=h))
            x += w + espaco
        y += h + espaco
    # ultima linha encosta na margem inferior
    delta = (H - margem) - max(b["y"] + b["h"] for b in out)
    ult = max(b["y"] for b in out)
    for b in out:
        if b["y"] == ult:
            b["h"] += delta
    return out


# ------------------------------------------------------------------ desenho
def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def gerar_svg(W, H, caixas, c, estilo="cartoes", titulo=None, subtitulo=None, raio=12):
    F = 'font-family="Segoe UI, Arial, sans-serif"'
    o = [f'<svg xmlns="{SVGNS}" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', "<defs>",
         f'<linearGradient id="g-fundo" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c["fundo"]}"/><stop offset="1" stop-color="{c["fundo2"]}"/></linearGradient>',
         f'<linearGradient id="g-acento" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{c["p"]}"/><stop offset="1" stop-color="{c["p"]}" stop-opacity="0.55"/></linearGradient>',
         "</defs>"]
    if estilo == "minimal":
        o.append(f'<rect id="fundo" width="{W}" height="{H}" fill="{c["fundo"]}"/>')
    else:
        o.append(f'<rect id="fundo" width="{W}" height="{H}" fill="url(#g-fundo)"/>')
        o.append(f'<circle id="deco-1" cx="{W - 60}" cy="-40" r="{H * 0.42:.0f}" fill="{c["p"]}" opacity="0.05"/>')
        o.append(f'<circle id="deco-2" cx="{W * 0.12:.0f}" cy="{H + 80}" r="{H * 0.35:.0f}" fill="{c["p"]}" opacity="0.035"/>')
    if titulo:
        if estilo == "contraste":
            o.append(f'<rect id="cabecalho" width="{W}" height="64" fill="url(#g-acento)"/>')
            o.append(f'<text id="titulo" x="24" y="{36 if subtitulo else 40}" {F} font-size="20" font-weight="600" fill="#FFFFFF">{esc(titulo)}</text>')
            if subtitulo:
                o.append(f'<text id="subtitulo" x="24" y="54" {F} font-size="11.5" fill="#FFFFFF" opacity="0.85">{esc(subtitulo)}</text>')
        else:
            o.append(f'<rect id="acento-titulo" x="24" y="{20 if subtitulo else 22}" width="4" height="{34 if subtitulo else 26}" rx="2" fill="{c["p"]}"/>')
            o.append(f'<text id="titulo" x="38" y="{36 if subtitulo else 42}" {F} font-size="20" font-weight="600" fill="{c["texto"]}">{esc(titulo)}</text>')
            if subtitulo:
                o.append(f'<text id="subtitulo" x="38" y="54" {F} font-size="11.5" fill="{c["mudo"]}">{esc(subtitulo)}</text>')
    for i, b in enumerate(caixas):
        x, y, w, h, tipo = b["x"], b["y"], b["w"], b["h"], b.get("tipo")
        r = raio
        idv = f'data-visual="{esc(b.get("id", ""))}"'
        if estilo != "minimal":  # sombra suave em camadas
            for dy, op in ((1, 1.0), (4, 0.6), (10, 0.35)):
                o.append(f'<rect x="{x}" y="{y + dy}" width="{w}" height="{h}" rx="{r}" fill="{c["sombra"]}" opacity="{c["sombra_op"] * op:.3f}"/>')
        fill = c["filtro"] if tipo in FILTRO else c["card"]
        stroke = f'stroke="{c["borda"]}" stroke-width="1"' if estilo == "minimal" or tipo in FILTRO else ""
        o.append(f'<rect id="card-{i + 1}" {idv} x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" {stroke}/>')
        if eh_kpi(b):
            o.append(f'<clipPath id="clip-{i + 1}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}"/></clipPath>')
            o.append(f'<rect x="{x}" y="{y}" width="{w}" height="4" fill="url(#g-acento)" clip-path="url(#clip-{i + 1})"/>')
        elif tipo not in FILTRO and tipo != HTML and h > 120:  # HTML Content traz o proprio titulo
            o.append(f'<line x1="{x + 14}" y1="{y + 38}" x2="{x + w - 14}" y2="{y + 38}" stroke="{c["borda"]}" stroke-width="1"/>')
    o.append("</svg>")
    return "\n".join(o)


def caixas_do_relatorio(rel, pagina):
    p = rel.pagina(pagina)
    W, H = p["json"].get("width", 1280), p["json"].get("height", 720)
    cx, topo_txt = [], []
    for v in rel.visuais(p):
        tipo = (v["json"].get("visual") or {}).get("visualType")
        pos = v["json"].get("position", {})
        b = {"id": v["id"], "tipo": tipo, "x": pos.get("x", 0), "y": pos.get("y", 0), "w": pos.get("width", 0), "h": pos.get("height", 0)}
        if tipo == "textbox" and b["y"] < 90:
            topo_txt.append(v["id"]); continue
        if tipo in IGNORAR or tipo == "textbox":
            continue
        cx.append(b)
    return W, H, cx, topo_txt


def listar(caminho):
    raiz = ET.parse(caminho).getroot()
    print(f"viewBox={raiz.get('viewBox')} width={raiz.get('width')} height={raiz.get('height')}")
    n_path = 0
    for el in raiz.iter():
        tag = el.tag.split("}")[-1]
        if tag == "text":
            print(f"text  id={el.get('id', '-'):14} x={el.get('x')} y={el.get('y')} size={el.get('font-size')} fill={el.get('fill')}  \"{''.join(el.itertext()).strip()}\"")
        elif tag == "rect" and el.get("id"):
            print(f"rect  id={el.get('id'):14} x={el.get('x', 0)} y={el.get('y', 0)} w={el.get('width')} h={el.get('height')} fill={el.get('fill')}")
        elif tag == "path":
            n_path += 1
    if n_path:
        print(f"{n_path} <path> (formas ou texto em contorno)")


def previa(svg, plano, saida):
    from playwright.sync_api import sync_playwright
    s = Path(svg).read_text(encoding="utf-8")
    W, H = (int(float(v)) for v in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', s).groups())
    caixas = json.loads(Path(plano).read_text(encoding="utf-8")) if plano else []
    over = "".join(f'<div style="position:absolute;left:{b["x"] + b.get("pad", 10)}px;top:{b["y"] + b.get("pad", 10)}px;'
                   f'width:{b["w"] - 2 * b.get("pad", 10)}px;height:{b["h"] - 2 * b.get("pad", 10)}px;border:1px dashed rgba(120,120,140,.45);'
                   f'font:12px Segoe UI,Arial;color:rgba(80,80,100,.8);padding:4px">{esc(b.get("slot") or b.get("id", ""))} · {esc(b.get("tipo", ""))}</div>' for b in caixas)
    html = f'<html><body style="margin:0"><div style="position:relative;width:{W}px;height:{H}px">{s}<div style="position:absolute;inset:0">{over}</div></div></body></html>'
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page(viewport={"width": W, "height": H})
        pg.set_content(html)
        pg.screenshot(path=saida)
        br.close()
    print(f"previa -> {saida}")


def aplicar(rel, pagina, dados, plano, transparentes):
    p = rel.pagina(pagina)
    pj = p["json"]
    atual = item_fundo(pj)
    mud = {}
    if atual and atual.lower().endswith(".svg") and "--novo-arquivo" not in sys.argv:
        outras = [q["nome"] for q in rel.paginas() if q["id"] != p["id"] and item_fundo(q["json"]) == atual]
        if outras:
            raise SystemExit(f"'{atual}' tambem e usado por {outras}. Use --novo-arquivo para dar um fundo proprio a esta pagina.")
        mud[RES + atual] = dados
        print(f"fundo '{atual}' substituido")
    else:
        nome = f"fundo_{re.sub(r'[^A-Za-z0-9]+', '_', pagina)}{random.randint(10**12, 10**13 - 1)}.svg"
        mud[RES + nome] = dados
        rpt = rel.ler_json("Report/definition/report.json")
        pac = rpt.setdefault("resourcePackages", [])
        reg = next((x for x in pac if x.get("type") == "RegisteredResources"), None)
        if reg is None:
            reg = {"name": "RegisteredResources", "type": "RegisteredResources", "items": []}
            pac.append(reg)
        reg.setdefault("items", []).append({"name": nome, "path": nome, "type": "Image"})
        mud["Report/definition/report.json"] = dump_json(rpt)
        pj.setdefault("objects", {})["background"] = [{"properties": {
            "image": {"image": {"name": {"expr": {"Literal": {"Value": f"'{nome}'"}}},
                                "url": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": nome}}},
                                "scaling": {"expr": {"Literal": {"Value": "'Fit'"}}}}},
            "transparency": {"expr": {"Literal": {"Value": "0D"}}}}}]
        pj["objects"]["outspace"] = [{"properties": {"color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}}}}]
        mud[p["arquivo"]] = dump_json(pj)
        print(f"fundo novo '{nome}' na pagina '{pagina}'")
    pos_nova = {b["id"]: b for b in json.loads(Path(plano).read_text(encoding="utf-8"))} if plano else {}
    for v in rel.visuais(p):
        vj, mudou = v["json"], False
        b = pos_nova.get(v["id"])
        if b:
            pad = b.get("pad", 10)
            vj["position"].update(x=b["x"] + pad, y=b["y"] + pad, width=b["w"] - 2 * pad, height=b["h"] - 2 * pad)
            mudou = True
        tipo = (vj.get("visual") or {}).get("visualType")
        if tipo == "textbox" and vj.get("position", {}).get("y", 999) < 90 and "--manter-titulo" not in sys.argv and plano:
            vj["isHidden"] = True; mudou = True
        if transparentes and tipo not in ("textbox",):
            vco = vj.setdefault("visual", {}).setdefault("visualContainerObjects", {})
            vco["background"] = [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
            vco["border"] = [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
            vco["dropShadow"] = [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
            mudou = True
        if mudou:
            mud[v["arquivo"]] = dump_json(vj)
    return rel.gravar(mud)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == "listar":
        return listar(sys.argv[2])
    if cmd == "previa":
        return previa(opt("--svg"), opt("--plano"), opt("--saida", "previa.png"))
    alvo, pagina = opt("--pbix") or opt("--pbip"), opt("--pagina")
    if cmd == "extrair":
        rel = Relatorio(alvo)
        item = item_fundo(rel.pagina(pagina)["json"])
        if not item:
            raise SystemExit(f"pagina '{pagina}' sem imagem de fundo")
        Path(opt("--saida", "fundo.svg")).write_bytes(rel.ler(RES + item))
        print(f"{item} -> {opt('--saida', 'fundo.svg')}")
    elif cmd == "gerar":
        titulo = opt("--titulo")
        if opt("--layout"):
            spec = json.loads(Path(opt("--layout")).read_text(encoding="utf-8"))
            pg = next(x for x in spec["paginas"] if x["nome"] == pagina)
            W, H = pg.get("largura", 1280), pg.get("altura", 720)
            cx = [{"id": v.get("titulo") or f"{v['tipo']}-{i}", "slot": v.get("slot"), "tipo": v["tipo"], "x": v["x"], "y": v["y"], "w": v["w"], "h": v["h"]}
                  for i, v in enumerate(pg["visuais"]) if v["tipo"] != "textbox"]
        else:
            W, H, cx, _ = caixas_do_relatorio(Relatorio(alvo), pagina)
        margem, espaco, pad = float(opt("--margem", 24)), float(opt("--espaco", 16)), float(opt("--padding", 10))
        topo = (80 if titulo else margem)
        if "--reorganizar" in sys.argv:
            cx = reorganizar(cx, W, H, topo, margem, espaco)
        for b in cx:
            b["pad"] = pad
        c = paleta(opt("--design"), "--escuro" in sys.argv)
        svg = gerar_svg(W, H, cx, c, opt("--estilo", "cartoes"), titulo, opt("--subtitulo"), float(opt("--raio", 12)))
        saida = Path(opt("--saida", "fundo.svg"))
        saida.write_text(svg, encoding="utf-8")
        plano = saida.with_suffix(".plano.json")
        plano.write_text(json.dumps(cx, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(cx)} cartao(oes) em {W}x{H} -> {saida} (plano: {plano})")
    elif cmd == "aplicar":
        rel = Relatorio(alvo)
        if not rel.pbir:
            raise EstruturaDesconhecida(MSG_LEGADO)
        bak = aplicar(rel, pagina, Path(opt("--arquivo")).read_bytes(), opt("--plano"), "--visuais-transparentes" in sys.argv)
        print(f"ok. Backup: {bak}")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    try:
        main()
    except EstruturaDesconhecida as e:
        print(f"ESTRUTURA NAO RECONHECIDA: {e} -> aplique pela interface (Formatar pagina > Plano de fundo da tela)"); sys.exit(2)
    except ArquivoAberto as e:
        print(e); sys.exit(1)

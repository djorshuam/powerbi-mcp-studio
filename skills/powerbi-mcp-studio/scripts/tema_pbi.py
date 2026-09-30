"""
tema_pbi.py - Gera um tema do Power BI (theme.json) a partir de um DESIGN.md ou tokens.json
e, opcionalmente, aplica no relatorio (.pbix ou .pbip, formato PBIR). Parte da skill powerbi-mcp-studio.

Uso:
    python tema_pbi.py --design designs/stripe/DESIGN.md --saida tema.json          -> so gera
    python tema_pbi.py --tokens tokens.json --saida tema.json
    python tema_pbi.py --design DESIGN.md --pbix "C:\\...\\Relatorio.pbix"          -> gera e aplica (Desktop FECHADO)
    python tema_pbi.py --design DESIGN.md --pbip "C:\\...\\Projeto"
    python tema_pbi.py ... --nome "Tema Cliente" --dry-run
    python tema_pbi.py --design DESIGN.md --modo escuro --saida tema-escuro.json   -> versao dark
    (sempre ajusta contraste: texto >= 4.5:1, cores de dados >= 3:1 contra o fundo)
    python tema_pbi.py --mostrar --pbix X.pbix                                       -> tema atual do relatorio

tokens.json (quando o DESIGN.md nao tem cabecalho YAML, o Claude escreve este arquivo):
{
  "name": "Cliente",
  "colors": {"primary": "#533afd", "background": "#ffffff", "surface": "#ffffff", "text": "#0d253d",
             "text_muted": "#64748d", "border": "#e3e8ee", "good": "#1a7f37", "bad": "#d1242f",
             "neutral": "#bf8700", "palette": ["#533afd", "#ea2261", "..."]},
  "fonts": {"title": "Segoe UI Semibold", "body": "Segoe UI"},
  "sizes_pt": {"title": 14, "header": 12, "label": 10, "callout": 28},
  "radius": 8
}

Saidas: 0 ok | 2 estrutura nao reconhecida (aplique pela interface: Exibicao > Temas > Procurar temas) | 1 erro.
"""
import colorsys, json, random, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pbi_arquivo import Relatorio, EstruturaDesconhecida, ArquivoAberto, dump_json, MSG_LEGADO  # noqa: E402

# Fontes que existem em qualquer Windows / sao oferecidas pelo Power BI
FONTES_PBI = ["Segoe UI", "Segoe UI Light", "Segoe UI Semibold", "Segoe UI Bold", "DIN", "Arial", "Arial Black",
              "Calibri", "Cambria", "Candara", "Consolas", "Corbel", "Courier New", "Georgia", "Tahoma",
              "Trebuchet MS", "Verdana", "Wingdings"]
EQUIVALENTES = {  # familias web comuns -> fonte disponivel no Power BI
    "inter": "Segoe UI", "sf pro": "Segoe UI", "system-ui": "Segoe UI", "-apple-system": "Segoe UI",
    "helvetica": "Arial", "helvetica neue": "Arial", "roboto": "Segoe UI", "open sans": "Segoe UI",
    "ibm plex sans": "Segoe UI", "geist": "Segoe UI", "manrope": "Segoe UI", "dm sans": "Segoe UI",
    "georgia": "Georgia", "times": "Georgia", "serif": "Georgia", "monospace": "Consolas",
    "sf mono": "Consolas", "jetbrains mono": "Consolas", "menlo": "Consolas", "futura": "Trebuchet MS",
}


# ------------------------------------------------------------------ leitura do DESIGN.md
def frontmatter(texto):
    if not texto.startswith("---"):
        return None
    partes = texto.split("\n---", 1)
    bloco = partes[0][3:]
    try:
        import yaml  # PyYAML, se existir
        return yaml.safe_load(bloco)
    except ImportError:
        return mini_yaml(bloco)
    except Exception:
        return mini_yaml(bloco)


def mini_yaml(bloco):
    """Parser minimo: mapas aninhados por indentacao com valores escalares (suficiente p/ colors/typography)."""
    raiz, pilha = {}, [(-1, None)]
    pilha[0] = (-1, raiz)
    for linha in bloco.splitlines():
        if not linha.strip() or linha.lstrip().startswith("#") or ":" not in linha:
            continue
        ind = len(linha) - len(linha.lstrip())
        chave, _, valor = linha.strip().partition(":")
        chave, valor = chave.strip().strip('"\''), valor.strip()
        while pilha and pilha[-1][0] >= ind:
            pilha.pop()
        pai = pilha[-1][1]
        if not isinstance(pai, dict):
            continue
        if valor == "":
            novo = {}
            pai[chave] = novo
            pilha.append((ind, novo))
        else:
            pai[chave] = valor.strip('"\'')
    return raiz


def cores_do_texto(texto):
    """Linhas '- **Nome** (`#hex`): uso' -> {'nome :: uso': '#HEX'} (o uso ajuda a achar o papel da cor)."""
    cores = {}
    for m in re.finditer(r"\*\*([^*\n]{1,40})\*\*\s*\(`?(#[0-9a-fA-F]{3,6})`?[^)]*\)\s*[:\-—]?\s*([^\n]{0,120})", texto):
        h = hexnorm(m.group(2))
        if h:
            chave = f"{m.group(1).strip().lower()} :: {m.group(3).strip().lower()}"
            cores.setdefault(chave, h)
    return cores


def hexnorm(v):
    if not isinstance(v, str):
        return None
    m = re.fullmatch(r"\s*#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\s*", v)
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.upper()


def hls(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


def lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contraste(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def de_hls(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h % 1, max(0, min(1, l)), max(0, min(1, s)))
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def achar(cores, *padroes, excluir=()):
    for p in padroes:
        for k, v in cores.items():
            kl = k.lower()
            if re.search(p, kl) and not any(re.search(e, kl) for e in excluir):
                return v
    return None


def fonte_pbi(familia):
    avisos = []
    if not familia:
        return "Segoe UI", avisos
    for f in [x.strip().strip('"\'') for x in str(familia).split(",")]:
        fl = f.lower()
        for ok in FONTES_PBI:
            if fl == ok.lower():
                return ok, avisos
        for k, v in EQUIVALENTES.items():
            if fl.startswith(k):
                avisos.append(f"fonte '{f}' substituida por '{v}'")
                return v, avisos
    avisos.append(f"fonte '{familia.split(',')[0].strip()}' nao disponivel no Power BI; usando 'Segoe UI'")
    return "Segoe UI", avisos


def px_pt(v, padrao):
    try:
        return max(8, min(45, round(float(str(v).replace("px", "").replace("rem", "")) * (16 if "rem" in str(v) else 1) * 0.75)))
    except (TypeError, ValueError):
        return padrao


def tokens_de_design(texto, nome_padrao):
    fm = frontmatter(texto) or {}
    avisos = []
    if isinstance(fm.get("colors"), dict):
        cores = {k: hexnorm(v) for k, v in fm["colors"].items() if hexnorm(v)}
    else:
        cores = cores_do_texto(texto)
        if len(cores) >= 3:
            avisos.append("DESIGN.md sem YAML: cores lidas do texto (\"**Nome** (`#hex`): uso\") - revise o resultado")
    if len(cores) < 2:
        raise EstruturaDesconhecida("DESIGN.md sem cores reconheciveis - escreva um tokens.json (ver --help)")
    bg = achar(cores, r"^canvas$", r"^background$", r"^bg$", r"canvas", r"background", r"surface", excluir=(r"dark", r"inverse", r"night")) or "#FFFFFF"
    texto_c = achar(cores, r"^ink$", r"^text$", r"^foreground$", r"^body", r"ink", r"text", r"on-surface", r"on-canvas",
                    excluir=(r"mute", r"secondary", r"subtle", r"on-primary", r"inverse", r"light")) or None
    if texto_c and hls(texto_c)[2] > 0.45 and 0.25 < hls(texto_c)[1] < 0.75:
        neutros = [c for c in cores.values() if hls(c)[2] < 0.3 and contraste(c, bg) >= 4.5]
        texto_c = max(neutros, key=lambda c: contraste(c, bg)) if neutros else None
    if not texto_c or contraste(texto_c, bg) < 4.5:
        candidatos = sorted(cores.values(), key=lambda c: -contraste(c, bg))
        texto_c = candidatos[0] if candidatos and contraste(candidatos[0], bg) >= 4.5 else ("#1F1F1F" if lum(bg) > 0.4 else "#F5F5F5")
    muted = achar(cores, r"mute", r"secondary", r"subtle", r"soft-text", excluir=(r"bg", r"surface", r"canvas")) or texto_c
    borda = achar(cores, r"hairline", r"border", r"divider", r"stroke", r"outline") or de_hls(hls(bg)[0], hls(bg)[1] - 0.1 if lum(bg) > 0.4 else hls(bg)[1] + 0.12, hls(bg)[2])
    surface = achar(cores, r"^surface$", r"card", r"surface", r"canvas-soft", excluir=(r"dark", r"inverse")) or bg

    def saturada(c):
        _, l, s = hls(c)
        return s > 0.25 and 0.18 < l < 0.82

    primaria = achar(cores, r"^primary$", r"^brand$", r"^accent$", r"primary", r"brand", r"accent", excluir=(r"on-", r"text"))
    if not primaria or not saturada(primaria):
        sat = [c for c in cores.values() if saturada(c)]
        if sat:
            primaria = sat[0]
        else:
            primaria = primaria or texto_c
            avisos.append("paleta monocromatica: cores de dados geradas a partir de tons neutros + acento azul")
    good = achar(cores, r"success", r"positive", r"green") or "#1A7F37"
    bad = achar(cores, r"error", r"danger", r"negative", r"critical", r"red") or "#D1242F"
    neutro = achar(cores, r"warning", r"caution", r"amber", r"yellow") or "#BF8700"

    # paleta de dados: primaria + cores saturadas distintas + complementos
    paleta = [primaria]
    for c in cores.values():
        if saturada(c) and all(abs(hls(c)[0] - hls(p)[0]) > 0.06 or abs(hls(c)[1] - hls(p)[1]) > 0.2 for p in paleta):
            paleta.append(c)
    base_h, base_l, base_s = hls(primaria if saturada(primaria) else "#2F6FDE")
    passo = 0
    while len(paleta) < 8:
        passo += 1
        h = base_h + passo * 0.13
        cand = de_hls(h, 0.42 + (passo % 2) * 0.12, max(0.45, base_s * 0.85))
        if all(abs(hls(cand)[0] - hls(p)[0]) > 0.05 for p in paleta):
            paleta.append(cand)
    paleta = paleta[:12]

    tip = fm.get("typography") or {}
    def estilo(*padroes):
        for p in padroes:
            for k, v in tip.items():
                if isinstance(v, dict) and re.search(p, k.lower()):
                    return v
        return {}
    t_titulo = estilo(r"heading-?(sm|md|3|4)", r"title", r"heading", r"display-?(sm|md)", r"h3", r"display")
    t_corpo = estilo(r"^body$", r"body-?(md|base|regular)?$", r"body", r"text", r"paragraph")
    t_label = estilo(r"caption", r"label", r"small", r"body-?sm")
    t_callout = estilo(r"display-?(lg|xl)", r"display", r"heading-?(xl|1)", r"h1")
    f_titulo, a1 = fonte_pbi(t_titulo.get("fontFamily") or t_corpo.get("fontFamily"))
    f_corpo, a2 = fonte_pbi(t_corpo.get("fontFamily") or t_titulo.get("fontFamily"))
    avisos += a1 + [a for a in a2 if a not in a1]
    peso = str(t_titulo.get("fontWeight", "600"))
    if f_titulo == "Segoe UI" and peso.isdigit():
        f_titulo = "Segoe UI Semibold" if int(peso) >= 550 else ("Segoe UI Light" if int(peso) <= 300 else "Segoe UI")

    raio = 8
    arred = fm.get("rounded") or {}
    for k in ("md", "card", "base", "sm"):
        if k in arred:
            try:
                raio = int(float(str(arred[k]).replace("px", "")))
                raio = min(raio, 20)
                break
            except ValueError:
                pass

    return {
        "name": fm.get("name") or nome_padrao,
        "colors": {"primary": primaria, "background": bg, "surface": surface, "text": texto_c, "text_muted": muted,
                   "border": borda, "good": good, "bad": bad, "neutral": neutro, "palette": paleta},
        "fonts": {"title": f_titulo, "body": f_corpo},
        "sizes_pt": {"title": px_pt(t_titulo.get("fontSize"), 14), "header": 12,
                     "label": max(9, min(12, px_pt(t_label.get("fontSize") or t_corpo.get("fontSize"), 10))),
                     "callout": max(20, px_pt(t_callout.get("fontSize"), 28))},
        "radius": raio,
    }, avisos


# ------------------------------------------------------------------ claro/escuro e contraste
def clarear(c, delta):
    h, l, s = hls(c)
    return de_hls(h, l + delta, s)


def ajustar_modo(t, modo, cores_origem=None):
    """Converte os tokens para modo 'escuro' (ou mantem 'claro') e garante contraste minimo."""
    c = dict(t["colors"])
    if modo == "escuro" and lum(c["background"]) > 0.2:
        origem = cores_origem or {}
        escuro = [v for k, v in origem.items() if re.search(r"dark|inverse|night|ink|black", k.lower()) and lum(v) < 0.06]
        bg = escuro[0] if escuro else "#121418"
        c.update(background=bg, surface=clarear(bg, 0.06), border=clarear(bg, 0.16))
        claros = sorted([v for v in origem.values() if lum(v) > 0.6], key=lambda v: -contraste(v, bg))
        c["text"] = claros[0] if claros else "#F2F3F5"
        c["text_muted"] = clarear(c["text"], -0.25)
    bg = c["background"]
    avisos = []
    if contraste(c["text"], bg) < 4.5:
        c["text"] = "#F2F3F5" if lum(bg) < 0.4 else "#1F1F1F"
        avisos.append("texto ajustado para contraste >= 4.5:1")
    if contraste(c["text_muted"], bg) < 3:
        c["text_muted"] = clarear(c["text"], -0.2 if lum(bg) < 0.4 else 0.25)
        avisos.append("texto secundario ajustado para contraste >= 3:1")
    pal = []
    for p in c["palette"]:
        n = 0
        while contraste(p, bg) < 3 and n < 8:
            p = clarear(p, 0.06 if lum(bg) < 0.4 else -0.06); n += 1
        pal.append(p)
    if pal != c["palette"]:
        avisos.append("cores de dados ajustadas para contraste >= 3:1 com o fundo (WCAG para graficos)")
    c["palette"] = pal
    for k in ("good", "bad", "neutral", "primary"):
        n = 0
        while contraste(c[k], bg) < 3 and n < 8:
            c[k] = clarear(c[k], 0.06 if lum(bg) < 0.4 else -0.06); n += 1
    t = dict(t, colors=c)
    return t, avisos


def relatorio_contraste(tema):
    bg = tema["background"]
    linhas = [f"texto/fundo {contraste(tema['foreground'], bg):.1f}:1 (min 4.5)"]
    piores = sorted(((contraste(p, bg), p) for p in tema["dataColors"]))[:2]
    linhas.append("pior cor de dados/fundo " + ", ".join(f"{p} {r:.1f}:1" for r, p in piores) + " (min 3)")
    return linhas


# ------------------------------------------------------------------ tema
def solid(c):
    return {"solid": {"color": c}}


def montar_tema(t, nome=None):
    c, f, s = t["colors"], t["fonts"], t["sizes_pt"]
    nome = nome or f"{t['name']}"
    return {
        "name": nome,
        "dataColors": c["palette"],
        "background": c["background"],
        "foreground": c["text"],
        "tableAccent": c["primary"],
        "good": c["good"], "neutral": c["neutral"], "bad": c["bad"],
        "maximum": c["primary"], "center": c["neutral"], "minimum": c["bad"],
        "textClasses": {
            "callout": {"fontSize": s["callout"], "fontFace": f["title"], "color": c["text"]},
            "title": {"fontSize": s["title"], "fontFace": f["title"], "color": c["text"]},
            "header": {"fontSize": s["header"], "fontFace": f["title"], "color": c["text"]},
            "label": {"fontSize": s["label"], "fontFace": f["body"], "color": c["text_muted"]},
        },
        "visualStyles": {
            "*": {"*": {
                "title": [{"show": True, "fontColor": solid(c["text"]), "fontFamily": f["title"], "fontSize": s["title"]}],
                "background": [{"show": True, "color": solid(c["surface"]), "transparency": 0}],
                "border": [{"show": True, "color": solid(c["border"]), "radius": t.get("radius", 8)}],
                "dropShadow": [{"show": False}],
                "subTitle": [{"show": False}],
            }},
            "page": {"*": {
                "background": [{"color": solid(c["background"]), "transparency": 0}],
            }},
        },
    }


def slug(s):
    return re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_")[:40] or "Tema"


# ------------------------------------------------------------------ aplicar no relatorio
def aplicar(rel, tema, dry):
    if not rel.pbir:
        raise EstruturaDesconhecida(MSG_LEGADO)
    rpt = rel.ler_json("Report/definition/report.json")
    tc = rpt.get("themeCollection")
    if not isinstance(tc, dict) or "baseTheme" not in tc:
        raise EstruturaDesconhecida("report.json sem themeCollection.baseTheme")
    versao = tc["baseTheme"].get("reportVersionAtImport")
    arquivo = f"{slug(tema['name'])}{random.randint(10**15, 10**16 - 1)}.json"
    mudancas = {}
    pacotes = rpt.setdefault("resourcePackages", [])
    reg = next((p for p in pacotes if p.get("type") == "RegisteredResources"), None)
    if reg is None:
        reg = {"name": "RegisteredResources", "type": "RegisteredResources", "items": []}
        pacotes.append(reg)
    antigo = tc.get("customTheme")
    if antigo and antigo.get("type") == "RegisteredResources":
        reg["items"] = [i for i in reg.get("items", []) if i.get("name") != antigo.get("name")]
        mudancas[f"Report/StaticResources/RegisteredResources/{antigo['name']}"] = None
    reg.setdefault("items", []).append({"name": arquivo, "path": arquivo, "type": "CustomTheme"})
    tc["customTheme"] = {"name": arquivo, "reportVersionAtImport": versao, "type": "RegisteredResources"}
    mudancas["Report/definition/report.json"] = dump_json(rpt)
    mudancas[f"Report/StaticResources/RegisteredResources/{arquivo}"] = dump_json(tema)
    print(f"tema '{tema['name']}' -> RegisteredResources/{arquivo}" + (f" (substitui {antigo['name']})" if antigo else ""))
    if dry:
        return None
    return rel.gravar(mudancas)


def opt(nome):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        raise SystemExit(f"{nome} precisa de um valor")
    return None


def main():
    design, tokens, saida = opt("--design"), opt("--tokens"), opt("--saida")
    pbix, pbip, nome = opt("--pbix"), opt("--pbip"), opt("--nome")
    dry = "--dry-run" in sys.argv
    if "--mostrar" in sys.argv:
        rel = Relatorio(pbix or pbip)
        rpt = rel.ler_json("Report/definition/report.json")
        tc = rpt.get("themeCollection", {})
        print(json.dumps(tc, ensure_ascii=False, indent=2))
        ct = tc.get("customTheme")
        if ct:
            t = rel.ler_json(f"Report/StaticResources/RegisteredResources/{ct['name']}")
            print("dataColors:", t.get("dataColors")); print("textClasses:", json.dumps(t.get("textClasses"), ensure_ascii=False))
        return
    if not (design or tokens):
        raise SystemExit(__doc__)
    avisos, origem = [], {}
    modo = opt("--modo") or "claro"
    if modo not in ("claro", "escuro"):
        raise SystemExit("--modo deve ser claro ou escuro")
    if tokens:
        t = json.loads(Path(tokens).read_text(encoding="utf-8"))
    else:
        texto = Path(design).read_text(encoding="utf-8")
        t, avisos = tokens_de_design(texto, Path(design).parent.name)
        fmc = (frontmatter(texto) or {}).get("colors")
        origem = {k: hexnorm(v) for k, v in fmc.items() if hexnorm(v)} if isinstance(fmc, dict) else cores_do_texto(texto)
    t, a2 = ajustar_modo(t, modo, origem)
    avisos += a2
    if modo == "escuro" and not nome:
        nome = f"{t['name']} (escuro)"
    tema = montar_tema(t, nome)
    for a in avisos:
        print("aviso:", a)
    for l in relatorio_contraste(tema):
        print("contraste:", l)
    print(f"paleta: {' '.join(tema['dataColors'])}")
    print(f"fundo {tema['background']}  texto {tema['foreground']}  fontes {t['fonts']['title']} / {t['fonts']['body']}")
    if saida:
        Path(saida).write_bytes(dump_json(tema))
        print(f"tema salvo em {saida}")
    if pbix or pbip:
        bak = aplicar(Relatorio(pbix or pbip), tema, dry)
        if bak:
            print(f"ok. Backup: {bak}. Abra o relatorio e confira (Exibicao > Temas mostra o tema ativo).")


if __name__ == "__main__":
    try:
        main()
    except EstruturaDesconhecida as e:
        print(f"ESTRUTURA NAO RECONHECIDA: {e}\n-> Gere com --saida e aplique pela interface: Exibicao > Temas > Procurar temas.")
        sys.exit(2)
    except ArquivoAberto as e:
        print(e); sys.exit(1)

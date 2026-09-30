"""
mockup_cores.py - Extrai a paleta de um MOCKUP (PNG/JPG de tela, print de outro dashboard, identidade visual)
e gera um DESIGN.md com os papeis de cor (fundo, cartao, texto, primaria, paleta de dados), pronto para
tema_pbi.py, svg_fundo.py e gerar_html.py. Parte da skill powerbi-mcp-studio.

Uso:
    python mockup_cores.py mockup.png --nome "Cliente X" --saida clientes/x/DESIGN.md

Requer Pillow (pip install pillow). O Claude revisa o resultado olhando a imagem: a extracao acerta
as cores, a interpretacao de papeis (qual e a primaria) pode precisar de ajuste manual no DESIGN.md.
"""
import colorsys, sys
from collections import Counter
from pathlib import Path


def hexa(rgb):
    return "#%02X%02X%02X" % rgb


def hls(rgb):
    return colorsys.rgb_to_hls(*(c / 255 for c in rgb))


def lum(rgb):
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (x / 255 for x in rgb)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("Pillow nao instalado: pip install pillow  (ou o Claude le as cores da imagem e escreve o DESIGN.md)")
    a = lambda n, d=None: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
    img = Image.open(sys.argv[1]).convert("RGB")
    img.thumbnail((480, 480))
    q = img.quantize(colors=40, method=Image.Quantize.MEDIANCUT).convert("RGB")
    cont = Counter({c: n for n, c in q.getcolors(1 << 16)})
    total = sum(cont.values())
    cores = [(c, n / total) for c, n in cont.most_common() if n / total >= 0.002]
    sat = lambda c: hls(c)[2] > 0.35 and 0.18 < hls(c)[1] < 0.8
    fundo = cores[0][0]
    escuro = lum(fundo) < 0.2
    cartao = next((c for c, _ in cores[1:] if not sat(c) and abs(lum(c) - lum(fundo)) < 0.15), fundo)
    neutras = [(c, p) for c, p in cores if not sat(c)]
    # texto ocupa poucos pixels: mediana do 1% mais escuro (fundo claro) ou mais claro (fundo escuro), sem as saturadas
    px = [c for c in (img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()) if not sat(c)]
    px.sort(key=lum, reverse=escuro)
    extremos = px[:max(1, len(px) // 100)]
    texto = extremos[len(extremos) // 2]
    mudo = min((c for c, _ in neutras if c not in (fundo, cartao, texto)), key=lambda c: abs(lum(c) - (lum(fundo) + lum(texto)) / 2), default=texto)
    saturadas = []
    for c, p in cores:  # saturadas distintas, da mais frequente para a menos
        if sat(c) and all(abs(hls(c)[0] - hls(x)[0]) > 0.04 or abs(hls(c)[1] - hls(x)[1]) > 0.15 for x, _ in saturadas):
            saturadas.append((c, p))
    prim = saturadas[0][0] if saturadas else texto
    dados = [hexa(c) for c, _ in saturadas[:8]]
    nome = a("--nome", Path(sys.argv[1]).stem)
    linhas = ["---", "version: alpha", f"name: {nome}", f"description: Paleta extraida de {Path(sys.argv[1]).name} (revisar papeis).", "colors:",
              f'  primary: "{hexa(prim)}"', f'  canvas: "{hexa(fundo)}"', f'  surface: "{hexa(cartao)}"', f'  ink: "{hexa(texto)}"',
              f'  ink-mute: "{hexa(mudo)}"']
    linhas += [f'  data-{i + 1}: "{c}"' for i, c in enumerate(dados)]
    if escuro:
        linhas.append(f'  dark-canvas: "{hexa(fundo)}"')
    linhas += ["typography:", "  heading-md:", '    fontFamily: "Segoe UI, sans-serif"', "    fontSize: 18px", "    fontWeight: 600",
               "  body:", '    fontFamily: "Segoe UI, sans-serif"', "    fontSize: 14px", "rounded:", "  md: 10px", "---", "",
               f"## Overview\nPaleta extraida automaticamente do mockup{' (tema escuro)' if escuro else ''}. Frequencia das cores:", ""]
    linhas += [f"- `{hexa(c)}` {p * 100:.1f}%" for c, p in cores[:12]]
    saida = Path(a("--saida", "DESIGN.md"))
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"fundo {hexa(fundo)}  cartao {hexa(cartao)}  texto {hexa(texto)}  primaria {hexa(prim)}  dados {' '.join(dados)}")
    print(f"-> {saida}{'  (mockup escuro: use --escuro/--modo escuro)' if escuro else ''}")


if __name__ == "__main__":
    main()

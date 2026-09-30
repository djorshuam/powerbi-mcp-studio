"""
icone_pbi.py - Icones Phosphor (1.512 icones x 6 pesos, MIT, offline) prontos para Power BI.
Parte da skill powerbi-mcp-studio. Fonte: icones/phosphor.json.gz (phosphoricons.com).

Uso:
    python icone_pbi.py --buscar hospital                 -> procura por nome, tag ou categoria
    python icone_pbi.py --buscar "seta cima"              -> termos em portugues comuns sao traduzidos
    python icone_pbi.py --icone chart-bar --peso fill --cor #533AFD --saida icone.svg
    python icone_pbi.py --icone chart-bar --formato dax   -> medida DAX (categoria de dados "URL da imagem")
    python icone_pbi.py --icone chart-bar --formato dax --cor-medida "[Cor Status]"   -> cor dinamica
    python icone_pbi.py --icone chart-bar --formato html  -> <svg> inline para visuais HTML
    python icone_pbi.py --lote heart,users,bed --peso duotone --cor #0D253D --pasta icones_out

Pesos: regular, thin, light, bold, fill, duotone.
"""
import gzip, json, re, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "icones" / "phosphor.json.gz"
PESOS = ("regular", "thin", "light", "bold", "fill", "duotone")
PT = {  # buscas frequentes em portugues -> termos do Phosphor
    "seta": "arrow", "cima": "up", "baixo": "down", "esquerda": "left", "direita": "right",
    "grafico": "chart", "gráfico": "chart", "barra": "bar", "linha": "line", "pizza": "pie",
    "usuario": "user", "usuário": "user", "pessoas": "users", "dinheiro": "money", "moeda": "currency",
    "calendario": "calendar", "calendário": "calendar", "relogio": "clock", "relógio": "clock",
    "casa": "house", "hospital": "hospital", "leito": "bed", "cama": "bed", "coracao": "heart",
    "coração": "heart", "alerta": "warning", "aviso": "warning", "sucesso": "check", "erro": "x",
    "filtro": "funnel", "busca": "magnifying", "pesquisa": "magnifying", "arquivo": "file",
    "pasta": "folder", "email": "envelope", "telefone": "phone", "carrinho": "shopping-cart",
    "loja": "storefront", "caminhao": "truck", "caminhão": "truck", "fabrica": "factory",
    "fábrica": "factory", "medico": "stethoscope", "médico": "stethoscope", "remedio": "pill",
    "remédio": "pill", "meta": "target", "alvo": "target", "tendencia": "trend", "tendência": "trend",
    "subindo": "trend-up", "caindo": "trend-down", "config": "gear", "configuracao": "gear",
    "tempo": "timer", "estrela": "star", "banco": "bank", "cartao": "credit-card", "cartão": "credit-card",
}


def carregar():
    if not BASE.exists():
        raise SystemExit(f"Base de icones nao encontrada: {BASE}")
    with gzip.open(BASE, "rt", encoding="utf-8") as f:
        return json.load(f)


def buscar(dados, termo):
    termos = [PT.get(t, t) for t in termo.lower().split()]
    res = []
    for nome, m in dados["meta"].items():
        texto = " ".join([nome] + m["t"] + m["c"]).lower()
        if all(t in texto for t in termos):
            pontos = sum(3 if t in nome else 1 for t in termos)
            res.append((-pontos, nome, m))
    return [(n, m) for _, n, m in sorted(res)]


def svg(dados, nome, peso, cor, tamanho, aspas="\""):
    if peso not in PESOS:
        raise SystemExit(f"peso invalido: {peso}. Use {PESOS}")
    corpo = dados["svg"][peso].get(nome)
    if corpo is None:
        sugestoes = [n for n, _ in buscar(dados, nome.replace("-", " "))[:5]]
        raise SystemExit(f"icone '{nome}' nao existe. Parecidos: {sugestoes}")
    q = aspas
    s = (f"<svg xmlns={q}http://www.w3.org/2000/svg{q} viewBox={q}0 0 256 256{q} width={q}{tamanho}{q} "
         f"height={q}{tamanho}{q} fill={q}{cor}{q}>{corpo}</svg>")
    if q == "'":
        s = s.replace('"', "'")
    return s


def dax(dados, nome, peso, cor, tamanho, cor_medida=None):
    corpo = svg(dados, nome, peso, "__COR__", tamanho, aspas="'")
    corpo = corpo.replace("#", "%23")
    antes, depois = corpo.split("__COR__")
    cor_expr = f'SUBSTITUTE({cor_medida}, "#", "%23")' if cor_medida else f'"{cor.replace("#", "%23")}"'
    return (f"// Icone Phosphor '{nome}' ({peso}). Medida -> Categoria de dados: URL da imagem.\n"
            f"// Use em tabela/matriz (Formatar > Imagem) ou no visual Imagem com URL dinamica.\n"
            f"VAR _cor = {cor_expr}\n"
            f"RETURN\n    \"data:image/svg+xml;utf8,{antes}\" & _cor & \"{depois}\"")


def opt(nome, padrao=None):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        raise SystemExit(f"{nome} precisa de um valor")
    return padrao


def main():
    dados = carregar()
    peso, cor, tam = opt("--peso", "regular"), opt("--cor", "#1F1F1F"), opt("--tamanho", "48")
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", cor):
        raise SystemExit("--cor no formato #RRGGBB")
    if opt("--buscar"):
        achados = buscar(dados, opt("--buscar"))
        for n, m in achados[:40]:
            print(f"{n:32} [{', '.join(m['c'])}]  {' '.join(m['t'][:6])}")
        print(f"{len(achados)} encontrado(s)" + (" (mostrando 40)" if len(achados) > 40 else ""))
        return
    if opt("--lote"):
        pasta = Path(opt("--pasta", "icones_out")); pasta.mkdir(parents=True, exist_ok=True)
        for n in opt("--lote").split(","):
            p = pasta / f"{n.strip()}-{peso}.svg"
            p.write_text(svg(dados, n.strip(), peso, cor, tam), encoding="utf-8")
            print(p)
        return
    nome = opt("--icone")
    if not nome:
        raise SystemExit(__doc__)
    fmt = opt("--formato", "svg")
    if fmt == "dax":
        saida = dax(dados, nome, peso, cor, tam, opt("--cor-medida"))
    elif fmt == "html":
        saida = svg(dados, nome, peso, cor, tam, aspas="'")
    else:
        saida = svg(dados, nome, peso, cor, tam)
    if opt("--saida"):
        Path(opt("--saida")).write_text(saida, encoding="utf-8")
        print(f"salvo em {opt('--saida')}")
    else:
        print(saida)


if __name__ == "__main__":
    main()

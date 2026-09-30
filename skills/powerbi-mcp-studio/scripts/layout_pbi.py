"""
layout_pbi.py - Biblioteca de layouts de mercado (layouts/): listar, recomendar e instanciar
um modelo com os campos reais do modelo semantico. Parte da skill powerbi-mcp-studio.

Uso:
    python layout_pbi.py listar
    python layout_pbi.py recomendar "diretoria acompanha metas mensais"
    python layout_pbi.py mostrar executivo                      -> slots do modelo (o que preencher)
    python layout_pbi.py instanciar --modelo executivo --mapa mapa.json --saida layout.json [--pagina "Visao Geral"]
    python layout_pbi.py encaixar --layout rascunho.json --saida layout.json   -> rascunho de mockup na grade
        (rascunho: {"paginas":[{"nome","largura_origem","altura_origem","visuais":[{"tipo","titulo","x","y","w","h","campos"?}]}]}
         com x/y/w/h medidos na imagem do mockup, em pixels da imagem)

mapa.json (slot -> campos e titulo; slots sem mapeamento sao removidos, a menos que --manter-vazios):
{
  "kpi1": {"campos": ["Values=Medida:Vendas[Total Vendas]"], "titulo": "Receita"},
  "tendencia": {"campos": ["Category=Coluna:Calendario[Mes]", "Y=Medida:Vendas[Total Vendas]"]},
  "comparativo1": {"tipo": "clusteredBarChart", "campos": ["Category=Coluna:Vendas[Regiao]", "Y=Medida:Vendas[Total Vendas]"]}
}
Depois: visuais_pbi.py lote --spec layout.json  ->  svg_fundo.py gerar (sem --reorganizar) + aplicar  ->  tema_pbi.py
"""
import json, re, sys, unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "layouts"
SINONIMOS = {
    "executivo": "diretoria conselho ceo presidente resumo mensal visao geral kpi board executivo",
    "scorecard": "meta metas farol semaforo aderencia indicadores okr acompanhamento status sentido",
    "operacional": "tempo real monitoramento tv noc plantao sala controle operacao fila alerta",
    "funil-comercial": "vendas comercial funil pipeline crm conversao vendedor marketing leads",
    "financeiro-dre": "financeiro dre resultado receita despesa margem ebitda orcado realizado controladoria cfo contabil",
    "geografico": "mapa regiao estado uf municipio unidade filial loja logistica rede geografico",
    "detalhe-drill": "detalhe drill lista auditoria registro item operacao exportar",
    "analitico-filtro-lateral": "analise explorar analista filtro filtros segmentacao investigacao",
    "comparativo-periodos": "comparar periodo anterior ano passado yoy mom variacao sazonalidade evolucao",
    "z-classico": "geral gestor area painel padrao simples",
}


def norm(s):
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def modelos():
    out = {}
    for d in sorted(p for p in BASE.iterdir() if p.is_dir() and (p / "layout.json").exists()):
        spec = json.loads((d / "layout.json").read_text(encoding="utf-8"))
        md = (d / "LAYOUT.md").read_text(encoding="utf-8") if (d / "LAYOUT.md").exists() else ""
        out[d.name] = {"spec": spec, "md": md}
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd, ms = sys.argv[1], modelos()
    if cmd == "listar":
        for k, m in ms.items():
            pub = re.search(r"\*\*Publico:\*\* (.*?)\s{2}", m["md"])
            uso = re.search(r"\*\*Quando usar:\*\* (.*)", m["md"])
            print(f"{k:26} {pub.group(1) if pub else '':34} {uso.group(1) if uso else ''}")
    elif cmd == "recomendar":
        termos = set(re.findall(r"\w+", norm(" ".join(sys.argv[2:]))))
        pont = []
        for k, m in ms.items():
            texto = set(re.findall(r"\w+", norm(m["md"] + " " + SINONIMOS.get(k, ""))))
            pont.append((len(termos & texto) + 2 * len(termos & set(SINONIMOS.get(k, "").split())), k))
        pont.sort(reverse=True)
        for p, k in pont[:3]:
            print(f"{k:26} (afinidade {p})  -> layouts/{k}/LAYOUT.md, previa: layouts/{k}/previa.png")
    elif cmd == "mostrar":
        m = ms[sys.argv[2]]
        print(m["md"])
    elif cmd == "instanciar":
        a = lambda n, d=None: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
        m = ms.get(a("--modelo")) or sys.exit(f"modelo invalido. Use: {', '.join(ms)}")
        mapa = json.loads(Path(a("--mapa")).read_text(encoding="utf-8")) if a("--mapa") else {}
        pg = json.loads(json.dumps(m["spec"]["paginas"][0]))
        if a("--pagina"):
            pg["nome"] = a("--pagina")
        vis = []
        for v in pg["visuais"]:
            cfg = mapa.get(v["slot"])
            if not cfg and "--manter-vazios" not in sys.argv:
                continue
            v = dict(v)
            if cfg:
                v["campos"] = cfg.get("campos", [])
                v["titulo"] = cfg.get("titulo", v["titulo"])
                v["tipo"] = cfg.get("tipo", v["tipo"])
            vis.append(v)
        faltando = [v["slot"] for v in pg["visuais"] if v["slot"] not in mapa]
        pg["visuais"] = vis
        Path(a("--saida", "layout.json")).write_text(json.dumps({"paginas": [pg]}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(vis)} visual(is) -> {a('--saida', 'layout.json')}" + (f"  (slots sem campo: {faltando})" if faltando else ""))
    elif cmd == "encaixar":
        # rascunho (ex.: caixas estimadas de um mockup) -> grade limpa, mantendo linhas e proporcoes
        a = lambda n, d=None: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from svg_fundo import reorganizar
        spec = json.loads(Path(a("--layout")).read_text(encoding="utf-8"))
        for pg in spec["paginas"]:
            W, H = pg.get("largura", 1280), pg.get("altura", 720)
            sx, sy = W / pg.get("largura_origem", W), H / pg.get("altura_origem", H)
            vs = [dict(v, x=v["x"] * sx, y=v["y"] * sy, w=v["w"] * sx, h=v["h"] * sy) for v in pg["visuais"]]
            topo = 80 if pg.get("titulo", True) else 24
            novos = reorganizar(vs, W, H, topo, 24, 16)
            for v in novos:
                v.update({k: round(v[k]) for k in ("x", "y", "w", "h")})
            pg["visuais"] = novos
            pg.pop("largura_origem", None); pg.pop("altura_origem", None)
        Path(a("--saida", "layout.json")).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"encaixado na grade -> {a('--saida', 'layout.json')}")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

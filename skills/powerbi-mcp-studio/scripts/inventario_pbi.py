"""
inventario_pbi.py - Inventario do relatorio (.pbix ou .pbip, formato PBIR): paginas, visuais,
posicoes e quais tabelas/colunas/medidas cada visual usa. Base para auditoria (campos sem uso),
dicionario e conversoes. Somente leitura - pode rodar com o Power BI aberto.

Uso:
    python inventario_pbi.py --pbix "C:\\...\\Relatorio.pbix"                 -> resumo no terminal
    python inventario_pbi.py --pbix X.pbix --json inventario.json             -> completo em JSON
    python inventario_pbi.py --pbix X.pbix --campos                           -> lista de campos usados (Tabela[Campo])

Para cruzar com o modelo (achar medidas/colunas sem uso), o Claude compara a lista de --campos
com INFO.VIEW.MEASURES()/INFO.VIEW.COLUMNS() via MCP (ver references/auditoria-modelo.md).
"""
import json, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pbi_arquivo import Relatorio, EstruturaDesconhecida  # noqa: E402


def campos_em(obj, achados, aliases=None):
    """Percorre o JSON e coleta referencias {Column|Measure|HierarchyLevel: {Expression:{SourceRef}, Property}}."""
    aliases = dict(aliases or {})
    if isinstance(obj, dict):
        # From: [{Name:'d', Entity:'Tabela'}] define aliases usados em SourceRef.Source
        for f in obj.get("From", []) if isinstance(obj.get("From"), list) else []:
            if isinstance(f, dict) and "Name" in f and "Entity" in f:
                aliases[f["Name"]] = f["Entity"]
        for tipo in ("Column", "Measure", "Aggregation", "HierarchyLevel"):
            v = obj.get(tipo)
            if isinstance(v, dict) and "Property" in v:
                sr = (v.get("Expression") or {}).get("SourceRef") or {}
                ent = sr.get("Entity") or aliases.get(sr.get("Source"))
                if ent:
                    achados.add(("Medida" if tipo == "Measure" else "Coluna", ent, v["Property"]))
        for v in obj.values():
            campos_em(v, achados, aliases)
    elif isinstance(obj, list):
        for v in obj:
            campos_em(v, achados, aliases)


def inventario(rel):
    rpt = rel.ler_json("Report/definition/report.json")
    filtros_rel = set()
    campos_em(rpt.get("filterConfig", {}), filtros_rel)
    paginas = []
    for p in rel.paginas():
        pj = p["json"]
        filtros_pg = set()
        campos_em(pj.get("filterConfig", {}), filtros_pg)
        vis = []
        for v in rel.visuais(p):
            vj = v["json"]
            c = set()
            campos_em(vj, c)
            pos = vj.get("position", {})
            tipo = (vj.get("visual") or {}).get("visualType") or ("grupo" if "visualGroup" in vj else "?")
            titulo = None
            try:
                titulo = vj["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"].strip("'")
            except (KeyError, IndexError, TypeError):
                pass
            vis.append({"id": v["id"], "tipo": tipo, "titulo": titulo,
                        "x": round(pos.get("x", 0)), "y": round(pos.get("y", 0)),
                        "w": round(pos.get("width", 0)), "h": round(pos.get("height", 0)),
                        "oculto": bool(vj.get("isHidden")), "campos": sorted(c)})
        paginas.append({"id": p["id"], "nome": p["nome"], "largura": pj.get("width"), "altura": pj.get("height"),
                        "oculta": pj.get("visibility") == "HiddenInViewMode",
                        "filtros": sorted(filtros_pg), "visuais": vis})
    return {"arquivo": str(rel.caminho), "formato": rel.tipo, "tema": rpt.get("themeCollection"),
            "filtros_relatorio": sorted(filtros_rel), "paginas": paginas}


def main():
    alvo = None
    for flag in ("--pbix", "--pbip"):
        if flag in sys.argv:
            alvo = sys.argv[sys.argv.index(flag) + 1]
    if not alvo:
        raise SystemExit(__doc__)
    rel = Relatorio(alvo)
    try:
        inv = inventario(rel)
    except EstruturaDesconhecida as e:
        print(f"ESTRUTURA NAO RECONHECIDA: {e}"); sys.exit(2)
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"inventario salvo em {out}")
    uso = defaultdict(list)
    for p in inv["paginas"]:
        for v in p["visuais"]:
            for c in v["campos"]:
                uso[tuple(c)].append(f"{p['nome']}/{v['tipo']}")
        for c in p["filtros"]:
            uso[tuple(c)].append(f"{p['nome']}/filtro-pagina")
    for c in inv["filtros_relatorio"]:
        uso[tuple(c)].append("filtro-relatorio")
    if "--campos" in sys.argv:
        for (tipo, t, n), onde in sorted(uso.items()):
            print(f"{tipo}\t{t}[{n}]\t{len(onde)} uso(s)\t{', '.join(sorted(set(onde)))}")
        return
    print(f"{inv['arquivo']} ({inv['formato']})")
    for p in inv["paginas"]:
        print(f"\n[{p['nome']}] {p['largura']}x{p['altura']}{' (oculta)' if p['oculta'] else ''} - {len(p['visuais'])} visuais")
        for v in p["visuais"]:
            nomes = ", ".join(f"{t}[{n}]" for _, t, n in v["campos"])
            print(f"  {v['tipo']:24} ({v['x']},{v['y']} {v['w']}x{v['h']}){' oculto' if v['oculto'] else ''}  {nomes}")
    print(f"\n{len(uso)} campos distintos usados no relatorio.")


if __name__ == "__main__":
    main()

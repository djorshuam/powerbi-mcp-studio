"""
tmdl_pbi.py - Grava MEDIDAS direto no modelo de um projeto .pbip (arquivos TMDL), com o Power BI Desktop FECHADO.
Util quando nao ha Desktop aberto para o MCP. Parte da skill powerbi-mcp-studio.

Uso:
    python tmdl_pbi.py medidas --pbip "C:\\...\\Projeto" --arquivo medidas.json [--substituir] [--dry-run]

medidas.json: [{"name": "...", "tableName": "_Medidas", "expression": "...", "formatString": "...",
               "displayFolder": "...", "description": "..."}]   (mesmo formato do MCP measure_operations Create)

- Respeita o formato do Desktop: tabulacao, CRLF, expressao multilinha entre ```, descricao em ///, lineageTag novo.
- Medida que ja existe: pula (ou substitui com --substituir). Backup em <projeto>/_backup_claude/<data-hora>/.
- Ao reabrir o .pbip o Desktop carrega as medidas; valide com DAX (MCP) em seguida.
"""
import json, re, shutil, sys, uuid
from datetime import datetime
from pathlib import Path


def nome_tmdl(n):
    return n if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n) else "'" + n.replace("'", "''") + "'"


def bloco(m):
    L = []
    if m.get("description"):
        for linha in str(m["description"]).splitlines():
            L.append(f"\t/// {linha}")
    expr = m["expression"].replace("\r\n", "\n").strip("\n")
    if "\n" in expr:
        L.append(f"\tmeasure {nome_tmdl(m['name'])} = ```")
        L += [f"\t\t\t{l}" for l in expr.split("\n")]
        L.append("\t\t\t```")
    else:
        L.append(f"\tmeasure {nome_tmdl(m['name'])} = {expr}")
    if m.get("formatString"):
        L.append(f"\t\tformatString: {m['formatString']}")
    if m.get("displayFolder"):
        L.append(f"\t\tdisplayFolder: {m['displayFolder']}")
    L.append(f"\t\tlineageTag: {uuid.uuid4()}")
    return L


def existe(texto, nome):
    return re.search(r"^\tmeasure " + re.escape(nome_tmdl(nome)) + r" =", texto, re.M) is not None


def remover(texto, nome):
    linhas = texto.split("\n")
    out, i = [], 0
    alvo = f"\tmeasure {nome_tmdl(nome)} ="
    while i < len(linhas):
        if linhas[i].startswith(alvo):
            while out and out[-1].startswith("\t///"):
                out.pop()
            i += 1
            while i < len(linhas) and (linhas[i].startswith("\t\t") or linhas[i].strip() == "```"):
                i += 1
            while i < len(linhas) and linhas[i].strip() == "":
                i += 1
            continue
        out.append(linhas[i]); i += 1
    return "\n".join(out)


def main():
    a = lambda n, d=None: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
    if len(sys.argv) < 2 or sys.argv[1] != "medidas":
        raise SystemExit(__doc__)
    base = Path(a("--pbip"))
    base = base if base.is_dir() else base.parent
    sm = next(base.glob("*.SemanticModel"), None) or sys.exit(f"nenhum *.SemanticModel em {base}")
    tabelas = sm / "definition" / "tables"
    medidas = json.loads(Path(a("--arquivo")).read_text(encoding="utf-8"))
    por_tabela = {}
    for m in medidas:
        por_tabela.setdefault(m.get("tableName", "_Medidas"), []).append(m)
    for t, ms in por_tabela.items():
        arq = tabelas / f"{t}.tmdl"
        if not arq.exists():
            raise SystemExit(f"tabela {t} nao encontrada ({arq}). Crie a tabela pelo Desktop/MCP antes.")
        bruto = arq.read_bytes()
        crlf = b"\r\n" in bruto
        texto = bruto.decode("utf-8-sig").replace("\r\n", "\n")
        novos = []
        for m in ms:
            if existe(texto, m["name"]):
                if "--substituir" not in sys.argv:
                    print(f"[pula] {t}[{m['name']}] ja existe (use --substituir)"); continue
                texto = remover(texto, m["name"])
            novos += bloco(m) + [""]
            print(f"[+] {t}[{m['name']}]")
        if not novos:
            continue
        linhas = texto.split("\n")
        # insere depois do cabecalho da tabela (linha 'table' + lineageTag + linha em branco)
        pos = next((i for i, l in enumerate(linhas) if l.startswith("\tlineageTag:")), 0) + 1
        while pos < len(linhas) and linhas[pos].strip() == "":
            pos += 1
        linhas[pos:pos] = novos
        saida = "\n".join(linhas)
        if crlf:
            saida = saida.replace("\n", "\r\n")
        if "--dry-run" in sys.argv:
            print(f"(dry-run) {arq.name}: {len(novos)} linhas novas"); continue
        bak = base / "_backup_claude" / datetime.now().strftime("%Y%m%d-%H%M%S") / arq.relative_to(base)
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(arq, bak)  # fora de definition/ (o Desktop pode recusar arquivos estranhos la)
        arq.write_bytes(saida.encode("utf-8"))
    print("Pronto. Abra o .pbip no Power BI Desktop e valide as medidas.")


if __name__ == "__main__":
    main()

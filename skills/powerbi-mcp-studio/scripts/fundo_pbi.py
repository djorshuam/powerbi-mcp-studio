"""
fundo_pbi.py - Troca a imagem de fundo de paginas do Power BI (.pbix OU .pbip).
Fonte da imagem: frame do Figma (API) ou arquivo local. Parte da skill powerbi-mcp-studio.

SEMPRE com o Power BI Desktop FECHADO para o arquivo alvo (o Desktop trava o arquivo
e, ao salvar, regravaria a copia dele por cima da alteracao).

Uso:
    python fundo_pbi.py --pbix "C:\\...\\Relatorio.pbix" <Pagina> --frame 12:34
    python fundo_pbi.py --pbix X.pbix <Pagina> --arquivo fundo.svg      -> imagem local, sem Figma
    python fundo_pbi.py --pbix X.pbix [Paginas...] --config config.json -> usa o mapa pagina->frame do cliente
    python fundo_pbi.py --pbip "C:\\projeto" [Paginas...]               -> projeto .pbip (pasta com *.Report)
    python fundo_pbi.py --exportar C:\\fundos <Pagina> --frame 12:34     -> so baixa (caminho 2: aplicar pela tela)
    python fundo_pbi.py --listar --pbix X.pbix                          -> lista paginas e o fundo de cada uma
    ... --dry-run                                                       -> mostra o que faria, sem gravar

config.json (por cliente; ver config.example.json):
    {"figma_file_key": "<chave da URL do Figma>", "paginas": {"<displayName da pagina>": "<node-id>"}}
Procurado em: --config, depois ./config.json, depois na raiz do projeto.

Codigos de saida:  0 ok | 2 estrutura nao reconhecida -> caminho 2 | 1 outros erros

Token: FIGMA_TOKEN no .env (pasta atual ou do projeto) ou variavel de ambiente
(Figma > Settings > Security > Personal access tokens, escopo File content - read only).
Nunca imprima nem commite o token.
"""
import io, json, os, shutil, sys, time, urllib.request, urllib.error, zipfile
from datetime import datetime
from pathlib import Path

FIGMA_FILE_KEY = None   # vem do config.json ou de --figma-file
MAPA = {}               # displayName -> node-id, vem do config.json
ROOT = Path.cwd()       # pasta do projeto .pbip (--pbip) ou pasta atual

RES_PREFIX = "Report/StaticResources/RegisteredResources/"
FORMATOS = ("svg", "png", "jpg", "pdf")


class EstruturaDesconhecida(Exception):
    """O arquivo nao tem o formato esperado -> caminho 2."""


# ---------------------------------------------------------------- Figma
def figma_get(url, token):
    req = urllib.request.Request(url, headers={"X-Figma-Token": token} if token else {})
    for t in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and t < 3:
                time.sleep(5 * (t + 1)); continue
            raise SystemExit(f"Erro {e.code} na API do Figma: {e.read()[:300]!r}")
    raise SystemExit("Falha repetida na API do Figma")


def exportar_frame(node, fmt, token):
    extra = "&svg_outline_text=true" if fmt == "svg" else "&scale=1"
    meta = json.loads(figma_get(
        f"https://api.figma.com/v1/images/{FIGMA_FILE_KEY}?ids={node}&format={fmt}{extra}", token))
    url = (meta.get("images") or {}).get(node)
    if not url:
        raise SystemExit(f"Figma nao devolveu imagem para {node}: {meta}")
    return figma_get(url, None)


# ---------------------------------------------------------------- leitura de paginas
def item_de_fundo(page_cfg):
    try:
        return page_cfg["objects"]["background"][0]["properties"]["image"]["image"]["url"]["expr"][
            "ResourcePackageItem"]["ItemName"]
    except (KeyError, IndexError, TypeError):
        return None


def paginas_pbix(z):
    """{displayName: ItemName|None}. Aceita PBIR (definition/pages/*/page.json) e legado (Report/Layout)."""
    nomes = z.namelist()
    pages = [n for n in nomes if n.startswith("Report/definition/pages/") and n.endswith("/page.json")]
    out = {}
    if pages:
        for n in pages:
            d = json.loads(z.read(n).decode("utf-8-sig"))
            out[d.get("displayName")] = item_de_fundo(d)
        return out
    if "Report/Layout" in nomes:
        lay = json.loads(z.read("Report/Layout").decode("utf-16-le").lstrip("\ufeff"))
        for s in lay.get("sections", []):
            cfg = json.loads(s.get("config") or "{}")
            out[s.get("displayName")] = item_de_fundo(cfg)
        return out
    raise EstruturaDesconhecida("nem Report/definition/pages nem Report/Layout encontrados")


def paginas_pbip():
    report = next(ROOT.glob("*.Report"), None)
    if not report:
        raise SystemExit(f"Nenhuma pasta *.Report em {ROOT}")
    out = {}
    for pj in (report / "definition" / "pages").glob("*/page.json"):
        d = json.loads(pj.read_text(encoding="utf-8"))
        out[d.get("displayName")] = item_de_fundo(d)
    return report / "StaticResources" / "RegisteredResources", out


# ---------------------------------------------------------------- escrita no .pbix
def regravar_pbix(caminho, trocas):
    """trocas = {nome_entrada: bytes}. Preserva ordem, compressao e metadados de todas as entradas."""
    with zipfile.ZipFile(caminho) as z:
        infos = z.infolist()
        nomes = [i.filename for i in infos]
        faltando = [n for n in trocas if n not in nomes]
        if faltando:
            raise EstruturaDesconhecida(f"entradas nao encontradas no pbix: {faltando}")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as novo:
            for i in infos:
                dados = trocas.get(i.filename)
                if dados is None:
                    dados = z.read(i.filename)
                zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
                zi.compress_type = i.compress_type
                zi.external_attr = i.external_attr
                zi.create_system = i.create_system
                novo.writestr(zi, dados)
    # valida antes de gravar por cima
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as t:
        if t.testzip() is not None or t.namelist() != nomes:
            raise SystemExit("Validacao do zip regravado falhou; original intacto.")
    checar_livre(caminho)
    bak = caminho.with_name(f"{caminho.name}.{datetime.now():%Y%m%d-%H%M%S}.bak")
    shutil.copy2(caminho, bak)
    with open(caminho, "r+b") as f:          # grava no proprio arquivo (sem .tmp que pode nao ser apagavel)
        f.write(buf.getvalue())
        f.truncate()
    return bak


def checar_livre(caminho):
    """Falha cedo, sem criar nada, se o Power BI Desktop estiver com o arquivo aberto."""
    try:
        with open(caminho, "r+b"):
            pass
    except PermissionError:
        raise SystemExit("O arquivo esta aberto no Power BI Desktop (bloqueado). Salve, feche e rode de novo.")


# ---------------------------------------------------------------- main
def carregar_env():
    for env in (Path.cwd() / ".env", ROOT / ".env"):
        if env.exists():
            for linha in env.read_text(encoding="utf-8").splitlines():
                linha = linha.strip()
                if linha and not linha.startswith("#") and "=" in linha:
                    k, v = linha.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def carregar_config(caminho):
    global FIGMA_FILE_KEY, MAPA
    candidatos = [Path(caminho)] if caminho else [Path.cwd() / "config.json", ROOT / "config.json"]
    for c in candidatos:
        if c.exists():
            cfg = json.loads(c.read_text(encoding="utf-8"))
            FIGMA_FILE_KEY = cfg.get("figma_file_key") or FIGMA_FILE_KEY
            MAPA = cfg.get("paginas") or {}
            return
    if caminho:
        raise SystemExit(f"config nao encontrado: {caminho}")


def listar(pbix):
    if pbix:
        with zipfile.ZipFile(pbix) as z:
            paginas = paginas_pbix(z)
    else:
        _, paginas = paginas_pbip()
    for nome, item in paginas.items():
        print(f"{nome!r:40} fundo: {item or '(sem imagem de fundo)'}")


def opt(nome):
    if nome in sys.argv:
        i = sys.argv.index(nome)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        raise SystemExit(f"{nome} precisa de um valor")
    return None


def main():
    global ROOT, FIGMA_FILE_KEY
    pbix, frame, arquivo, exportar = opt("--pbix"), opt("--frame"), opt("--arquivo"), opt("--exportar")
    pbip, config, figma_file = opt("--pbip"), opt("--config"), opt("--figma-file")
    if pbip:
        ROOT = Path(pbip)
    carregar_env()
    carregar_config(config)
    if figma_file:
        FIGMA_FILE_KEY = figma_file
    dry = "--dry-run" in sys.argv
    valores = {pbix, frame, arquivo, exportar, pbip, config, figma_file}
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a not in valores]

    if "--listar" in sys.argv:
        return listar(pbix)
    if not arquivo and not dry and not FIGMA_FILE_KEY:
        raise SystemExit("Informe o arquivo do Figma: figma_file_key no config.json ou --figma-file <chave>.")

    if frame or arquivo:
        if len(args) != 1:
            raise SystemExit("--frame/--arquivo exigem exatamente uma pagina")
        alvo = {args[0]: frame}
    else:
        alvo = {k: v for k, v in MAPA.items() if not args or k in args}
        for a in args:
            if a not in MAPA:
                raise SystemExit(f"Pagina '{a}' nao esta em 'paginas' do config.json; use --frame NODE")
    if not alvo:
        raise SystemExit("Nada a fazer")

    token = os.environ.get("FIGMA_TOKEN")
    if not token and not arquivo and not dry:
        raise SystemExit("Defina FIGMA_TOKEN no .env ou como variavel de ambiente.")

    def imagem(node, fmt):
        if arquivo:
            p = Path(arquivo)
            if p.suffix.lstrip(".").lower() != fmt:
                raise SystemExit(f"--arquivo e .{p.suffix.lstrip('.')} mas o fundo atual e .{fmt}")
            return p.read_bytes()
        return exportar_frame(node, fmt, token)

    # ---- caminho 2: so exportar para uma pasta
    if exportar:
        pasta = Path(exportar); pasta.mkdir(parents=True, exist_ok=True)
        for nome, node in alvo.items():
            fmt = "svg"
            destino = pasta / f"{nome}.{fmt}"
            print(f"[{nome}] frame {node} -> {destino}")
            if not dry:
                destino.write_bytes(exportar_frame(node, fmt, token))
        print("Exportado. Aplique pelo Power BI: Formatar pagina > Plano de fundo da tela > Imagem > Procurar.")
        return

    # ---- caminho 1a: .pbix
    if pbix:
        caminho = Path(pbix)
        try:
            with zipfile.ZipFile(caminho) as z:
                paginas = paginas_pbix(z)
                nomes = set(z.namelist())
        except zipfile.BadZipFile:
            raise EstruturaDesconhecida("o arquivo nao e um zip valido")
        if not dry:
            checar_livre(caminho)
        trocas = {}
        for nome, node in alvo.items():
            if nome not in paginas:
                print(f"[pula] pagina '{nome}' nao existe. Paginas: {list(paginas)}"); continue
            item = paginas[nome]
            if not item:
                print(f"[pula] '{nome}' sem imagem de fundo - defina uma vez no Desktop"); continue
            entrada = RES_PREFIX + item
            if entrada not in nomes:
                raise EstruturaDesconhecida(f"fundo '{item}' nao esta em {RES_PREFIX}")
            fmt = Path(item).suffix.lstrip(".").lower()
            if fmt not in FORMATOS:
                print(f"[pula] '{nome}': formato {fmt} nao suportado"); continue
            print(f"[{nome}] {'arquivo ' + arquivo if arquivo else 'frame ' + str(node)} -> {entrada}")
            outras = [p for p, it in paginas.items() if it == item and p != nome and p not in alvo]
            if outras:
                print(f"   ATENCAO: o mesmo arquivo de fundo tambem e usado por {outras} - elas mudam junto.")
            if not dry:
                trocas[entrada] = imagem(node, fmt)
        if trocas:
            bak = regravar_pbix(caminho, trocas)
            print(f"   ok: {len(trocas)} fundo(s) trocados. Backup: {bak.name}")
        print("Pronto. Abra o .pbix no Power BI Desktop para conferir.")
        return

    # ---- caminho 1b: .pbip
    recursos, paginas = paginas_pbip()
    for nome, node in alvo.items():
        item = paginas.get(nome)
        if nome not in paginas:
            print(f"[pula] pagina '{nome}' nao encontrada"); continue
        if not item:
            print(f"[pula] '{nome}' sem imagem de fundo - defina uma vez no Desktop"); continue
        destino = recursos / item
        fmt = destino.suffix.lstrip(".").lower()
        print(f"[{nome}] frame {node} -> {destino.name}")
        if dry:
            continue
        dados = imagem(node, fmt)
        if destino.exists():
            shutil.copy2(destino, destino.with_suffix(destino.suffix + ".bak"))
        destino.write_bytes(dados)
        print(f"   ok: {len(dados)/1024:.0f} KB")
    print("Pronto. Abra o .pbip no Power BI Desktop para conferir.")


if __name__ == "__main__":
    try:
        main()
    except EstruturaDesconhecida as e:
        print(f"ESTRUTURA NAO RECONHECIDA: {e}\n-> Use o caminho 2: --exportar <pasta> e aplique pela tela.")
        sys.exit(2)

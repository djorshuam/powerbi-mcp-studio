"""
pbi_arquivo.py - Acesso uniforme a relatorios Power BI em .pbix (zip) ou .pbip (pasta).
Usado por tema_pbi.py, visuais_pbi.py e inventario_pbi.py. Python 3.9+, sem dependencias.

Nomes internos sempre no formato do zip: "Report/definition/report.json", "Report/StaticResources/...".
No .pbip, "Report/" e mapeado para a pasta "<Nome>.Report/".

Regras de seguranca:
  - so grava com o Power BI Desktop FECHADO (o Desktop trava o arquivo e regravaria a copia dele ao salvar);
  - .pbix: backup <arquivo>.<data-hora>.bak, preserva ordem/compressao/metadados de todas as entradas,
    valida o zip antes de gravar;
  - .pbip: backup .bak de cada arquivo alterado.
"""
import io, json, shutil, zipfile
from datetime import datetime
from pathlib import Path


MSG_LEGADO = ("relatorio no formato antigo (Report/Layout). Para editar por script, converta para PBIR uma vez: "
              "Power BI Desktop > Arquivo > Opcoes e configuracoes > Opcoes > Recursos em versao previa > marcar "
              "'Armazenar relatorios PBIX usando o formato de metadados aprimorado (PBIR)', reiniciar, abrir o arquivo, fazer qualquer alteracao e SALVAR (a conversao e silenciosa, sem aviso). "
              "Alternativa: Salvar como .pbip. Sem converter: faca a alteracao pela interface.")


class EstruturaDesconhecida(Exception):
    """Formato interno inesperado -> use o caminho pela interface (tela)."""


class ArquivoAberto(Exception):
    """O Power BI Desktop esta com o arquivo aberto."""


class Relatorio:
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        if self.caminho.is_dir() or self.caminho.suffix.lower() == ".pbip":
            base = self.caminho if self.caminho.is_dir() else self.caminho.parent
            rep = next(base.glob("*.Report"), None)
            if not rep:
                raise EstruturaDesconhecida(f"nenhuma pasta *.Report em {base}")
            self.tipo, self.pasta = "pbip", rep
        elif self.caminho.suffix.lower() == ".pbix":
            if not zipfile.is_zipfile(self.caminho):
                raise EstruturaDesconhecida("o .pbix nao e um zip valido")
            self.tipo = "pbix"
            with zipfile.ZipFile(self.caminho) as z:
                self._infos = z.infolist()
                self._dados = {i.filename: z.read(i.filename) for i in self._infos}
        else:
            raise EstruturaDesconhecida(f"extensao nao suportada: {self.caminho}")

    # ------------------------------------------------------------ leitura
    def _p(self, nome):
        return self.pasta / nome[len("Report/"):] if nome.startswith("Report/") else self.pasta.parent / nome

    def nomes(self):
        if self.tipo == "pbix":
            return list(self._dados)
        return ["Report/" + p.relative_to(self.pasta).as_posix() for p in self.pasta.rglob("*") if p.is_file()]

    def existe(self, nome):
        return nome in self._dados if self.tipo == "pbix" else self._p(nome).exists()

    def ler(self, nome):
        if self.tipo == "pbix":
            if nome not in self._dados:
                raise KeyError(nome)
            return self._dados[nome]
        return self._p(nome).read_bytes()

    def ler_json(self, nome):
        return json.loads(self.ler(nome).decode("utf-8-sig"))

    @property
    def pbir(self):
        """True se o relatorio usa o formato PBIR (definition/pages/*/page.json)."""
        return self.existe("Report/definition/report.json")

    def paginas(self):
        """Lista de dicts {id, nome, arquivo, json} na ordem do pages.json (PBIR)."""
        if not self.pbir:
            raise EstruturaDesconhecida(MSG_LEGADO)
        ordem = []
        if self.existe("Report/definition/pages/pages.json"):
            ordem = self.ler_json("Report/definition/pages/pages.json").get("pageOrder", [])
        achadas = {}
        for n in self.nomes():
            if n.startswith("Report/definition/pages/") and n.endswith("/page.json"):
                pid = n.split("/")[3]
                achadas[pid] = n
        ids = [i for i in ordem if i in achadas] + [i for i in achadas if i not in ordem]
        out = []
        for pid in ids:
            d = self.ler_json(achadas[pid])
            out.append({"id": pid, "nome": d.get("displayName"), "arquivo": achadas[pid], "json": d})
        return out

    def pagina(self, nome_ou_id):
        for p in self.paginas():
            if nome_ou_id in (p["nome"], p["id"]):
                return p
        raise SystemExit(f"Pagina '{nome_ou_id}' nao encontrada. Paginas: {[p['nome'] for p in self.paginas()]}")

    def visuais(self, pagina):
        pref = f"Report/definition/pages/{pagina['id']}/visuals/"
        out = []
        for n in sorted(self.nomes()):
            if n.startswith(pref) and n.endswith("/visual.json"):
                d = self.ler_json(n)
                out.append({"id": n.split("/")[5], "arquivo": n, "json": d})
        return out

    # ------------------------------------------------------------ escrita
    def checar_livre(self):
        alvo = self.caminho if self.tipo == "pbix" else self.pasta / "definition" / "report.json"
        try:
            with open(alvo, "r+b"):
                pass
        except PermissionError:
            raise ArquivoAberto("O arquivo esta aberto no Power BI Desktop. Salve, feche e rode de novo.")

    def gravar(self, mudancas):
        """mudancas = {nome: bytes | None}. None apaga; nome novo e acrescentado no fim. Devolve o backup."""
        if not mudancas:
            return None
        self.checar_livre()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if self.tipo == "pbix":
            # SecurityBindings (blob DPAPI) valida a definicao do relatorio: qualquer mudanca em
            # Report/definition/* ou Report/Layout com ele presente -> "arquivo corrompido"
            # (MashupValidationError). Testado 30/09/2026 (PBI Desktop 2.158, set/2026): trocar imagem
            # ou acrescentar arquivo e seguro; mexer em report.json/pages.json/page.json/visual.json exige remover.
            mexe_definicao = any(n.startswith("Report/definition/") or n == "Report/Layout" for n in mudancas)
            if mexe_definicao and "SecurityBindings" in self._dados and "SecurityBindings" not in mudancas:
                mudancas = dict(mudancas, SecurityBindings=None)
                print("aviso: SecurityBindings removido (obrigatorio ao alterar a definicao do relatorio). "
                      "Se o relatorio tinha rotulo de sensibilidade, reaplique no Power BI Desktop e salve.")
            # extensao nova (ex.: .png) precisa de <Default Extension> no [Content_Types].xml
            ct = "[Content_Types].xml"
            if ct in self._dados:
                xml = self._dados[ct].decode("utf-8-sig")
                for nome, dados in mudancas.items():
                    ext = nome.rsplit(".", 1)[-1].lower() if "." in nome.split("/")[-1] else None
                    if dados is not None and ext and f'Extension="{ext}"' not in xml:
                        xml = xml.replace("<Override", f'<Default Extension="{ext}" ContentType="" /><Override', 1)
                bom = self._dados[ct].startswith(b"\xef\xbb\xbf")
                novo_ct = (b"\xef\xbb\xbf" if bom else b"") + xml.encode("utf-8")
                if novo_ct != self._dados[ct]:
                    mudancas = dict(mudancas, **{ct: novo_ct})
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as novo:
                vistos = set()
                for i in self._infos:
                    vistos.add(i.filename)
                    dados = mudancas.get(i.filename, self._dados[i.filename])
                    if dados is None:
                        continue
                    zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
                    zi.compress_type, zi.external_attr, zi.create_system = i.compress_type, i.external_attr, i.create_system
                    novo.writestr(zi, dados)
                for nome, dados in mudancas.items():
                    if nome not in vistos and dados is not None:
                        zi = zipfile.ZipInfo(nome, date_time=datetime.now().timetuple()[:6])
                        zi.compress_type = zipfile.ZIP_DEFLATED
                        novo.writestr(zi, dados)
            with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as t:
                if t.testzip() is not None:
                    raise SystemExit("Validacao do zip regravado falhou; original intacto.")
            bak = self.caminho.with_name(f"{self.caminho.name}.{stamp}.bak")
            n = 2
            while bak.exists():
                bak = self.caminho.with_name(f"{self.caminho.name}.{stamp}-{n}.bak"); n += 1
            shutil.copy2(self.caminho, bak)
            with open(self.caminho, "r+b") as f:
                f.write(buf.getvalue())
                f.truncate()
            # recarrega o estado
            self.__init__(self.caminho)
            return bak
        # pbip: backups FORA das pastas de definicao (o Desktop pode recusar arquivos estranhos em definition/)
        bak_dir = self.pasta.parent / "_backup_claude" / stamp
        for nome, dados in mudancas.items():
            p = self._p(nome)
            if p.exists():
                destino = bak_dir / p.relative_to(self.pasta.parent)
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, destino)
            if dados is None:
                if p.exists():
                    try:
                        p.unlink()
                    except PermissionError:  # ambiente sem permissao de apagar: tira da pasta do projeto
                        lixo = self.pasta.parent / "_to_delete" / stamp / p.relative_to(self.pasta.parent)
                        lixo.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(p), str(lixo))
                        print(f"[aviso] sem permissao para apagar; movido para {lixo}")
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(dados)
        return str(bak_dir)


def dump_json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")

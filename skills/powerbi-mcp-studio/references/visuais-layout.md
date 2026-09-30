# Paginas e visuais por script (visuais_pbi.py)

Cria paginas e visuais, move/redimensiona e importa posicoes do Figma, direto no .pbix ou .pbip (formato **PBIR**). Escrita so com o Desktop **fechado**. Testado em 30/09/2026 (Power BI Desktop 2.158): pagina com cartao, cartao com contagem distinta, rosca, colunas, linhas, tabela, segmentacao e caixa de texto abriu e renderizou com dados.

## Comandos
```
python scripts/visuais_pbi.py tipos                                     # tipos de visual e papeis aceitos
python scripts/visuais_pbi.py listar --pbix X.pbix [--pagina "P"]       # ids, tipo, posicao
python scripts/visuais_pbi.py nova-pagina --pbix X.pbix --nome "Vendas" [--largura 1280 --altura 720]
python scripts/visuais_pbi.py criar --pbix X.pbix --pagina "Vendas" --tipo clusteredColumnChart \
    --campo "Category=Coluna:Vendas[Região]" --campo "Y=Medida:Vendas[Total Vendas]" --x 24 --y 216 --w 600 --h 280 --titulo "Vendas por regiao"
python scripts/visuais_pbi.py lote --pbix X.pbix --spec layout.json    # varias paginas/visuais (ver conversao-dashboard.md)
python scripts/visuais_pbi.py mover --pbix X.pbix --plano plano.json   # [{"pagina","visual": id|titulo,"x","y","w","h"}]
python scripts/visuais_pbi.py figma --pbix X.pbix --pagina "P" --frame 12:34 --figma-file CHAVE
```
Campos: `Papel=Tipo:Tabela[Campo]` com Tipo = `Medida`, `Coluna`, `Soma`, `Media`, `Contagem`, `ContagemDistinta`, `Min`, `Max`.

## Posicionar pelo Figma
No frame da pagina, desenhe retangulos e **nomeie cada um com o id do visual** (de `listar`) ou com o **titulo** do visual. O script le as caixas pela API do Figma, converte a escala do frame para a da pagina e grava x/y/largura/altura. Nomes que nao batem sao ignorados.

## Regra critica do .pbix: SecurityBindings
O `.pbix` tem uma parte `SecurityBindings` (blob protegido) que **valida a definicao do relatorio**. Qualquer mudanca em `Report/definition/*` (report.json, pages.json, page.json, visual.json) com ela presente faz o Desktop recusar: *"Esse arquivo esta corrompido ou foi criado por uma versao nao reconhecida"* (`MashupValidationError`). Diagnostico feito em 30/09/2026:
| Mudanca | SecurityBindings presente | Abre? |
|---|---|---|
| substituir imagem de fundo | sim | ✅ |
| acrescentar arquivo novo | sim | ✅ |
| reformatar `pages.json` (mesmo conteudo) | sim | ❌ |
| pagina + visual novos | sim | ❌ |
| pagina + visual novos | **removido** | ✅ |
O `pbi_arquivo.py` remove o `SecurityBindings` automaticamente quando a mudanca toca a definicao e avisa. Consequencia: se o relatorio tinha **rotulo de sensibilidade**, reaplique no Desktop e salve. No .pbip nao existe esse problema.

## Depois de gerar
- Abrir, conferir e **salvar pelo Desktop** (Ctrl+S) — ele regrava tudo no formato dele.
- Ajustes finos (formatacao condicional, rotulos, cores por ponto) sao mais rapidos pela interface.
- Visual novo nasce com o estilo do tema: aplique o tema antes ou depois, tanto faz.

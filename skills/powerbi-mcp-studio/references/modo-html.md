# Modo HTML Content (dashboard HTML dentro do Power BI)

> **Padrao da skill: visuais nativos.** O HTML Content nao e clicavel (nao filtra/destaca outros visuais, sem drill nem tooltip nativo) — use so quando o usuario pedir explicitamente a aparencia do HTML e aceitar isso.

Duas saidas para a mesma pagina:

| Saida | Como fica | Quando preferir |
|---|---|---|
| **Visuais nativos** (`visuais_pbi.py lote`) | graficos padrao do Power BI + fundo SVG + tema | interacao completa (clique filtra, drill, tooltip), Q&A, exportar dados, manutencao por qualquer analista |
| **HTML Content** (`html_dax.py`) | o mesmo visual do dashboard HTML (cartoes, linha com area em SVG, colunas arredondadas, barras, tabela) gerado por medidas DAX | identidade visual forte, layout livre, paridade com o HTML entregue ao cliente |

Pode entregar os dois — **em .pbix por padrao** (ex.: `Relatorio.pbix` nativo e `Relatorio HTML.pbix`) — ou paginas diferentes do mesmo relatorio.

## Fluxo
```
python scripts/html_dax.py --layout layout.json --design DESIGN.md --medidas-saida medidas_html.json --layout-saida layout_html.json
```
1. **Medidas** (pasta `4. Visual (HTML)` da `_Medidas`):
   - **.pbix (padrao)** → Desktop aberto → MCP `measure_operations` Create com `medidas_html.json`.
   - So se o arquivo for .pbip e o Desktop estiver fechado → `python scripts/tmdl_pbi.py medidas --pbip <pasta> --arquivo medidas_html.json` (grava no TMDL).
2. **Visual HTML Content** no relatorio (AppSource, guid `htmlContent443BE3AD55E043BF878BED274D3A6855`, autor Daniel Marsh-Patrick):
   - copiar de outro relatorio que ja tenha: `python scripts/visuais_pbi.py visual-custom --pbix X.pbix --de outro.pbix`
   - ou adicionar uma vez pela interface: Visualizacoes → ... → Obter mais visuais → "HTML Content".
3. **Pagina**: `visuais_pbi.py lote --spec layout_html.json` (visuais sem titulo/fundo/cabecalho: o titulo vem no HTML) → `svg_fundo.py gerar/aplicar` → `tema_pbi.py`.
4. **Validar** com o Desktop aberto: cada medida HTML via DAX (`EVALUATE ROW("h", [HTML 01 ...])` nao pode dar erro) e print da pagina (revisor-visual).

## Como as medidas funcionam
- Cartao: titulo + valor formatado em pt-BR (R$, mil/mi/bi, %) com `FORMAT`.
- Barras/colunas: `ADDCOLUMNS(VALUES(Dim[Col]), "@v", [Medida])` + `CONCATENATEX` gerando `<div>` com altura em **px** calculada do tamanho do slot (altura em % colapsa no visual) (numeros de CSS com `FORMAT(x, "0.0", "en-US")` para usar ponto decimal).
- Linha: `RANKX` para indice, `CONCATENATEX` montando os pontos de um `<polyline>`/`<polygon>` SVG com `viewBox` e `preserveAspectRatio='none'`.
- Tabela: `SUMMARIZE` + `TOPN` + `CONCATENATEX` em `<table>`.
- Respeitam filtros de segmentacoes nativas e de outras paginas. **Nao** filtram outros visuais por clique (use segmentacoes). Sem JavaScript (o visual sanitiza).

## Cuidados
- Medidas HTML so aceitam medidas explicitas (`Medida:_Medidas[...]`) — rode `modelagem_pbi.py remapear` antes.
- Textos com aspas duplas sao escapados; evite `<script>` e estilos externos (nao funcionam no visual).
- Desempenho: cada medida roda uma consulta; ate ~50 categorias por grafico. Tabelas grandes → visual nativo.

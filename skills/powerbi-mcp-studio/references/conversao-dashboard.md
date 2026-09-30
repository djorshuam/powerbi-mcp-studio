# Conversao de dashboard Excel/HTML → Power BI

Muita gente mantem "dashboards" em Excel (abas + graficos + SOMA) ou em HTML (Chart.js, ECharts, Plotly, tabelas). O fluxo abaixo transforma isso num relatorio Power BI com modelo, medidas e paginas. O agente `agents/conversor-dashboard.md` executa este roteiro de ponta a ponta.

## Visao geral
```
Excel/HTML ──extrair_dashboard.py──► dados/*.csv + spec.json + resumo.md
                                          │
          MCP (Desktop ABERTO, relatorio em branco ou existente)
          ├─ tabelas a partir dos CSV (Power Query M)
          ├─ tipos, relacoes, tabela de datas
          └─ medidas (traduz SOMA/MEDIA/CONT e KPIs para DAX)
                                          │  salvar (.pbix)  → fechar
          visuais_pbi.py lote --spec layout.json   (Desktop FECHADO)
          tema_pbi.py --design DESIGN.md           (opcional)
          fundo_pbi.py / icones                    (opcional)
                                          │  reabrir → conferir (tela) → validar numeros (DAX x origem)
```

## Passo a passo
1. **Extrair**: `python scripts/extrair_dashboard.py <arquivo.xlsx|.html> --saida <pasta>`. Leia o `resumo.md` e o `spec.json`:
   - Excel: abas → tabelas detectadas (bloco com cabecalho + ≥3 linhas), tipos por coluna, formulas de agregacao (KPIs), graficos (tipo, titulo, series com referencias `'Aba'!$D$2:$D$37`), tabelas dinamicas, nomes definidos. `.xls` antigo: pedir para salvar como `.xlsx`.
   - HTML: `<table>` → CSV, cartoes/KPIs (classes kpi/metric/card...), graficos Chart.js/ECharts/Plotly (tipo, titulo, categorias, series; Chart.js com dados embutidos vira CSV proprio).
   - Dados que vem de API/JS dinamico nao aparecem no HTML salvo: pedir a fonte (CSV/planilha/banco) ao usuario.
2. **Planejar e mostrar ao usuario** (antes de construir): tabelas → fato/dimensoes, medidas (cada KPI/serie vira medida DAX, citando a formula de origem na descricao), paginas e visuais (cada grafico → `visual_pbi` sugerido; cartoes → `card`; filtros → `slicer`). Para Excel "largo" (meses em colunas), planejar `Table.UnpivotOtherColumns` no M.
3. **Onde os dados vao morar**: CSV extraido e bom para prototipo. Para producao, apontar o M para a **origem real** (a propria planilha com `Excel.Workbook`, pasta do SharePoint, banco). Perguntar.
4. **Modelo via MCP** (Desktop aberto; relatorio em branco serve):
   - `table_operations` → `Create` com `name`, `mExpression` e `columns` (nome, `dataType`, `sourceColumn`). Exemplo testado:
     ```
     let
         Fonte = Csv.Document(File.Contents("C:\...\Vendas.csv"), [Delimiter=";", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
         Cabecalho = Table.PromoteHeaders(Fonte, [PromoteAllScalars=true]),
         Tipos = Table.TransformColumnTypes(Cabecalho, {{"Mês", type date}, {"Vendas", Int64.Type}}, "en-US")
     in Tipos
     ```
     (o extrator grava CSV em UTF-8 com BOM, separador `;`, datas ISO e numeros com ponto → cultura `en-US` no `TransformColumnTypes`.)
   - `partition_operations` → `RefreshWithXMLA` (Full) → conferir `COUNTROWS`.
   - Dimensoes (ex.: Regiao, Produto) com `DISTINCT` ou no M; tabela de datas `CALENDAR` + marcar como tabela de datas; relacoes 1:* unidirecionais.
   - Medidas: `measure_operations` → `Create` com `formatString` e `description` citando a origem (ex.: "Painel!B1 =SUM(Vendas!D2:D37)").
   - **Validar numeros**: cada KPI da origem (valor na celula/ cartao) contra a medida via DAX. Diferenca = parar e investigar.
5. **Salvar**: pedir ao usuario Ctrl+S (relatorio novo pede nome/pasta) ou fazer pela tela.
6. **Paginas e visuais** (Desktop fechado): montar `layout.json` e rodar `python scripts/visuais_pbi.py lote --pbix X.pbix --spec layout.json`. Seguir `boas-praticas-visuais.md` (grade de 8 px, cartoes no topo, graficos no meio, tabela embaixo).
   ```json
   {"paginas": [{"nome": "Visao Geral", "visuais": [
     {"tipo": "card", "titulo": "Total de vendas", "campos": ["Values=Medida:Vendas[Total Vendas]"], "x": 24, "y": 80, "w": 280, "h": 120},
     {"tipo": "clusteredColumnChart", "titulo": "Vendas por regiao", "campos": ["Category=Coluna:Vendas[Região]", "Y=Medida:Vendas[Total Vendas]"], "x": 24, "y": 216, "w": 600, "h": 280},
     {"tipo": "slicer", "campos": ["Values=Coluna:Vendas[Produto]"], "x": 1000, "y": 80, "w": 256, "h": 120}]}]}
   ```
   Papeis por tipo: `python scripts/visuais_pbi.py tipos`.
7. **Identidade**: `tema_pbi.py` com o DESIGN.md do cliente (ou da galeria), fundo/icones se fizer sentido.
8. **Reabrir e conferir** pela tela; ajustar layout com `visuais_pbi.py mover` ou pela interface.

## Limites (dizer ao usuario)
- Formatacao condicional, rotulos customizados, interacoes finas e bookmarks nao sao convertidos automaticamente — o visual nasce com o padrao do tema.
- Graficos Excel que apontam para faixas calculadas (formulas em cascata) precisam ter a logica reescrita como medida DAX.
- Macros VBA e scripts JS com logica de negocio nao sao traduzidos automaticamente: o Claude le e propoe o equivalente em M/DAX, com validacao.
- Visuais HTML muito customizados (D3) viram o visual nativo mais proximo, ou um visual HTML (medida que gera HTML) se o cliente usar o visual "HTML Content".

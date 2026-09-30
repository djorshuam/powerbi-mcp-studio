# Planilha (+ mockup opcional) → dashboard em HTML ou Power BI

O fluxo "melhor dos mundos": o usuario sobe uma planilha (xlsx/csv) e, se quiser, uma imagem de referencia (mockup, print de outro painel, manual de marca). O Claude le os dados, recomenda os visuais, monta a pagina e entrega **HTML interativo** (na hora, sem Power BI) e/ou **Power BI** (.pbix com modelo, medidas, pagina, fundo e tema). O agente `agents/construtor-dashboard.md` executa tudo.

## Visao geral
```
planilha.xlsx ──► recomendar_visuais.py ──► recomendacoes.md (perfil, visuais e porque, medidas)
                        │                    mapa.json · medidas.json · tabelas_mcp.json
mockup.png (opcional) ──► Claude le a imagem ──► rascunho.json ──► layout_pbi.py encaixar
                      └─► mockup_cores.py ──► DESIGN.md (paleta do mockup)
                        ▼
          layout_pbi.py instanciar ──► layout.json   (ou o layout encaixado do mockup)
             ├─► gerar_html.py  ──► dashboard.html  (ECharts, filtros, clique para filtrar, mesmo fundo/tema)
             └─► Power BI: MCP (tabelas + medidas) → salvar → visuais_pbi lote → svg_fundo → tema_pbi → abrir
```

## 1. Ler e recomendar
```
python scripts/recomendar_visuais.py --xlsx planilha.xlsx --objetivo "diretoria acompanha vendas contra a meta" --saida rec/
```
- Perfila cada coluna: **data**, **geografia** (UF, cidade, regional...), **identificador** (pedido, codigo, CPF...), **medida** (moeda, quantidade, percentual, meta), **dimensao** com cardinalidade (baixa ≤6, media ≤20, alta ≤60).
- Cria **medidas derivadas** que um analista faria: Atingimento (valor/meta), Margem % ((valor-custo)/valor), Ticket medio (valor/pedidos) — DAX para o Power BI e formula para o HTML (`medidas.json`).
- Sugere visuais **com o porque** (poucas categorias → colunas/rosca; muitas → barras horizontais ordenadas; data → linha mensal; geografia → mapa; etapa → funil; meta → realizado x meta; percentual nunca soma).
- Escolhe o **layout de mercado** pelo objetivo e pelos dados e preenche o `mapa.json`.
- Modelo Power BI existente: `--bim modelo.bim` (usa as medidas que ja existem); `--consulta-perfil` gera o DAX de cardinalidade para rodar no MCP.
- **Mostre o `recomendacoes.md` ao usuario** e ajuste o que ele pedir antes de construir (trocar visual, layout, titulo).

## 2. Mockup (opcional)
1. **Olhe a imagem** (Read). Identifique cabecalho, filtros, cartoes, graficos, tabelas; para cada bloco estime x, y, largura e altura em pixels da imagem e o tipo de visual equivalente (`visuais_pbi.py tipos`).
2. Escreva o rascunho: `{"paginas":[{"nome":"...","largura_origem":<px da imagem>,"altura_origem":<px>,"visuais":[{"tipo":"card","titulo":"Receita","x":..,"y":..,"w":..,"h":..}]}]}`.
3. `python scripts/layout_pbi.py encaixar --layout rascunho.json --saida layout_mockup.json` — escala para 1280x720 e encaixa na grade (margem 24, espaco 16, KPIs ≥128 px, faixa de filtros baixa), mantendo as linhas do mockup.
4. Preencha os campos de cada caixa com as sugestoes do passo 1 (mesma sintaxe do `mapa.json`: `"campos": ["Values=Soma:T[C]"]`).
5. Paleta: `python scripts/mockup_cores.py mockup.png --nome "Cliente" --saida clientes/<c>/DESIGN.md` (Pillow). **Confira olhando a imagem**: a extracao acerta fundo e cor de destaque; texto e papeis podem precisar de ajuste manual (o tema corrige contraste de qualquer forma).
6. Sem mockup: use o layout recomendado e um estilo da galeria `designs/` (ou o DESIGN.md do cliente).

## 3a. Entregar em HTML (minutos)
```
python scripts/layout_pbi.py instanciar --modelo executivo --mapa rec/mapa.json --pagina "Visao Geral" --saida rec/layout.json
python scripts/gerar_html.py --layout rec/layout.json --dados rec/extraido --medidas rec/medidas.json \
       --design designs/<estilo>/DESIGN.md --titulo "Vendas 2026" --subtitulo "..." --saida dashboard.html [--echarts echarts.min.js]
```
- Um arquivo so, dados embutidos, graficos ECharts, KPIs formatados em pt-BR (R$, mil/mi, %), segmentacoes, **clique num grafico filtra o resto**, botao limpar filtros, escala para qualquer tela, mesmo fundo SVG e paleta do Power BI.
- `--echarts` embute a biblioteca (offline). Sem ela, carrega do jsdelivr.
- No Claude: publique como **Artifact** (pagina privada com link) quando o usuario quiser compartilhar; senao entregue o arquivo.
- Teste antes de entregar: renderize (Playwright) e confira 2–3 numeros contra a planilha, e um filtro.
- Limite pratico: ~50 mil linhas embutidas (arquivo cresce). Acima disso, agregue antes ou va de Power BI.

## 3b. Entregar em Power BI (.pbix por padrao)
Siga o padrao de `modelagem.md`: `modelagem_pbi.py plano` + `remapear` antes de criar a pagina (o mapa passa a apontar para `_Medidas`, dimensoes e `Calendario`).

1. Power BI Desktop aberto com relatorio **em branco** (ou o do cliente). MCP: conectar.
2. Tabelas: para cada item de `rec/tabelas_mcp.json` → `table_operations` Create (`name`, `mExpression`, `columns`). **Ajuste o caminho do CSV** no M para o local definitivo (ou troque por `Excel.Workbook(File.Contents(...))` apontando para a planilha original / SharePoint). A coluna `<Data> Mes` ja vem no M.
3. `partition_operations` RefreshWithXMLA → conferir `COUNTROWS`.
4. Medidas: cada item de `rec/medidas.json` → `measure_operations` Create (`name`, `tableName`, `expression` = `dax`, `formatString` = `formato`, `description` = `porque`).
5. **Validar numeros** via DAX contra a planilha (mesmos KPIs do HTML).
6. Usuario salva (Ctrl+S; relatorio novo pede nome) e fecha.
7. `visuais_pbi.py lote --pbix X.pbix --spec rec/layout.json` → `svg_fundo.py gerar --pbix ... --design ... --titulo ...` → `previa` → `aplicar --plano ... --visuais-transparentes` → `tema_pbi.py --design ...`.
8. Reabrir, conferir (revisor-visual) e salvar pelo Desktop.

## Qualidade antes de entregar (sempre)
- Numeros: 3+ KPIs batendo com a planilha (e um valor filtrado).
- Visual: previa renderizada olhada; nenhum rotulo cortado; titulos informativos.
- Explicar ao usuario em 3–5 linhas o que foi escolhido e por que (a partir do `recomendacoes.md`).

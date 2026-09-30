# Padrao de modelagem (aplicar sempre, salvo pedido contrario)

Todo modelo que a skill cria ou reorganiza segue este padrao:

1. **Modelo estrela**: uma tabela fato (eventos/transacoes) no centro e dimensoes (quem, o que, onde, como) em volta, relacoes **1:* com filtro unico** da dimensao para a fato. Nada de muitos-para-muitos nem bidirecional sem motivo documentado.
2. **Tabela Calendario** (DAX `CALENDAR` do 1o ao ultimo ano da fato), **marcada como tabela de datas**, com Ano, Trimestre, Mes (ordenado por Mes Num), Ano Mes, Dia da Semana (ordenado). Relacao com a data da fato. Desligar data/hora automatica.
3. **Tabela `_Medidas`** so com medidas, organizadas em **pastas** (`displayFolder`): `1. Base` (somas, contagens), `2. Indicadores` (razoes, atingimento, margem), `3. Tempo` (acumulados, ano anterior), `4. Visual` (medidas de texto/HTML/cor). Cada medida com `formatString` e `description`.
4. **Medidas explicitas**: visuais nunca usam soma implicita de coluna; derivadas reutilizam as medidas base (`DIVIDE([Total Venda], [Total Meta])`).
5. **Colunas tecnicas ocultas**: chaves e numericos da fato ficam ocultos (o usuario ve medidas e atributos das dimensoes).
6. **Exibicao de modelo** organizada em estrela: fato no centro, dimensoes em volta, `Calendario` e `_Medidas` no topo (feito pela interface; o layout do diagrama nao e editado por script).

## A partir de uma planilha (tabela achatada)
```
python scripts/modelagem_pbi.py plano --rec rec/ --csv-no-pc "C:\...\Pedidos.csv" --saida rec/modelo_estrela.json
python scripts/modelagem_pbi.py remapear --plano rec/modelo_estrela.json --mapa rec/mapa.json --saida rec/mapa_estrela.json
```
O plano traz: M da fato e de cada dimensao (dimensoes referenciam a consulta da fato com `Table.Distinct` pela chave), DAX do Calendario e da `_Medidas`, relacoes, medidas com pastas, colunas a ocultar, **passos na ordem** e o **de-para** de campos para os visuais. Grupos de dimensao reconhecidos: local (UF/cidade/regional), produto (produto/categoria/marca), cliente, vendedor, canal; demais descritivas de baixa/media cardinalidade viram dimensao propria.

Execucao via MCP (Desktop aberto), seguindo `passos`:
1. `table_operations` Create — fato e dimensoes (`mExpression` + `columns`); `_Medidas` e `Calendario` com `daxExpression`.
2. `table_operations` MarkAsDateTable (Calendario, coluna Date); `column_operations` Update `sortByColumn`.
3. `RefreshWithXMLA`; conferir linhas e unicidade das chaves das dimensoes (`COUNTROWS` = `DISTINCTCOUNT(chave)`).
4. `relationship_operations` Create; `measure_operations` Create (tabela `_Medidas`); `column_operations` Update `isHidden`.
5. Validar KPIs contra a planilha (inclusive filtrando por uma dimensao).
Se a fato ja existia com medidas: `measure_operations` Move para `_Medidas` + Update (expressao sobre as base, pasta, formato).

## Modelo existente
Auditar (`modelo_pbi.py auditoria`) e propor a migracao para o padrao em etapas, com OK do usuario — mover medidas para `_Medidas` e criar pastas e seguro; trocar relacoes e criar dimensoes muda campos de visuais existentes (remapear visuais com `visuais_pbi.py` ou pela interface).

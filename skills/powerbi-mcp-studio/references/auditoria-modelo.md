# Auditoria, dicionario, checklist de publicacao e desempenho

Tudo somente leitura. Entrada: o modelo exportado pelo MCP + o relatorio (.pbix/.pbip).

## 0. Exportar o modelo (Desktop aberto)
MCP `database_operations` → `{"operation": "ExportToBimFile", "bimFilePath": "C:\\...\\modelo.bim"}` (JSON com tabelas, colunas, medidas com expressoes, relacoes, estado/erros).

## 1. Auditoria
```
python scripts/modelo_pbi.py auditoria --bim modelo.bim --pbix "C:\...\Relatorio.pbix" --saida auditoria.md
```
Aponta, com nota 0–100:
- **Erros**: medidas/colunas com estado de erro (ex.: coluna referenciada que nao existe mais).
- **Relacoes**: criadas automaticamente (AutoDetected), bidirecionais, muitos-para-muitos, inativas.
- **Sem uso**: medidas que nenhum visual/filtro usa nem sao usadas por medidas usadas (dependencia transitiva); colunas calculadas sem uso (ignora chaves de relacao e "classificar por").
- **Risco no DAX**: FILTER na tabela inteira, IFERROR, divisao com `/`, iteradores aninhados, comparacao com VALUES.
- **Documentacao/formato**: medidas sem formato ou descricao, chaves tecnicas visiveis, falta tabela de datas marcada, data/hora automatica ligada.
O inventario de uso vem de `inventario_pbi.py` (visuais, filtros de pagina e de relatorio). Atencao: outro relatorio conectado ao mesmo modelo (modelo publicado compartilhado) pode usar o que aparece como "sem uso" — confirmar antes de apagar.

Consultas equivalentes ao vivo (MCP `dax_query_operations`, uteis para conferir):
```
EVALUATE FILTER(SELECTCOLUMNS(INFO.MEASURES(), "Nome", [Name], "Estado", [State], "Erro", [ErrorMessage]), [Estado] <> 1)
EVALUATE FILTER(SELECTCOLUMNS(INFO.COLUMNS(), "Coluna", [ExplicitName], "Estado", [State], "Erro", [ErrorMessage]), [Estado] <> 1)
EVALUATE INFO.VIEW.RELATIONSHIPS()
EVALUATE SELECTCOLUMNS(FILTER(INFO.CALCDEPENDENCY(), [OBJECT_TYPE] = "MEASURE"), "Medida", [OBJECT], "Usa", [REFERENCED_OBJECT])
```

## 2. Dicionario do modelo
```
python scripts/modelo_pbi.py dicionario --bim modelo.bim --pbix "C:\...\Relatorio.pbix" --saida dicionario.md
```
Tabelas (tipo de origem), relacoes, cada medida (descricao, formato, pasta, DAX, se e usada no relatorio) e colunas. Publique como documento (tipo Docs, se disponivel) para o cliente. Medidas sem descricao: proponha descricoes e grave via MCP (`measure_operations` → `Update` com `description`) **com OK do usuario**.

## 3. Checklist antes de publicar
```
python scripts/modelo_pbi.py checklist --bim modelo.bim --pbix "C:\...\Relatorio.pbix"
```
Gera as consultas DAX; rode cada uma via MCP e confira:
1. Valores das medidas usadas no relatorio (erro/blank inesperado?).
2. Linhas por tabela (tabela vazia = refresh/filtro de origem quebrado).
3. Chaves duplicadas no lado 1 das relacoes (quebram o proximo refresh).
4. Valores da fato sem correspondencia na dimensao (viram "(Em branco)" nos visuais).
Mais: data de atualizacao visivel e correta, filtros de pagina/relatorio intencionais, RLS testada (`dax_query_operations` com `impersonation`), paginas ocultas de rascunho removidas, auditoria sem erros.

## 4. Desempenho
Por medida (ou por visual), com cache frio:
1. `dax_query_operations` → `ClearCache`.
2. `Execute` com `getExecutionMetrics: true` a consulta do visual (ex.: `EVALUATE SUMMARIZECOLUMNS(Dim[Col], "M", [Medida])`) ou `EVALUATE ROW("M", [Medida])`.
3. Leia `reportedExecutionMetrics.durationMs`, `totalCpuTimeMs`, `approximatePeakMemConsumptionKB` (as metricas "calculated" podem vir vazias no Desktop — use as "reported").
Referencia: < 100 ms otimo · 100–1000 ms ok · > 1 s investigar (FILTER em tabela inteira, iteradores aninhados, colunas de alta cardinalidade, relacoes bidirecionais, muitos visuais na pagina). Reescreva, meça de novo e registre antes/depois.

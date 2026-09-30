# Modelo via MCP `powerbi-modeling` (Desktop ABERTO)

O servidor oficial da Microsoft conversa com o motor tabular que o Desktop sobe junto com o arquivo aberto. Le e escreve no modelo. Funciona igual para .pbix e .pbip. Instalacao: `instalacao.md`.

## Toda sessao
1. `connection_operations` → `{"operation":"ListLocalInstances"}` — confira `parentWindowTitle`.
2. `Connect` com a `connectionString` devolvida. **A porta muda a cada abertura** do Desktop — reconecte depois de fechar/reabrir.
3. Duvida de parametros: `{"operation":"Help"}` em qualquer ferramenta (traz exemplos prontos).

Nao invente nomes de tabela, coluna ou medida: liste antes (modelos reais tem acentos, espacos, prefixos como `00_Medidas`).

## Receitas
- **Alterar o M de uma particao** (ex.: tabela de-para feita com `#table`):
  1. `table_operations` → `ExportTMDL` com `includeChildren:true` e `maxReturnCharacters:-1`. Use o M **exato** como base, sem reescrever de memoria.
  2. Tire a indentacao de tabs do TMDL (o `expression` comeca em `let`).
  3. `partition_operations` → `Update` com `tableName`, `name`, `expression`.
  4. Reexporte e compare linha a linha. O aviso "column mappings were not updated" so importa se nomes/tipos de coluna mudaram.
- **Atualizar dados**: `partition_operations` → `RefreshWithXMLA`, `refreshDefinitions:[{tableName, refreshType:"Full"}]`. Mais confiavel que clicar em Atualizar pela tela; os visuais se redesenham sozinhos.
- **Validar com DAX**: `dax_query_operations` → `Execute`, `resultMode:"Inline"`. Tabela → `EVALUATE ...`; escalar → `EVALUATE ROW("x", [Medida])`. `Validate` checa sintaxe sem executar.
- **Achar lacunas de de-para** (padrao util): `ADDCOLUMNS(SUMMARIZE(Fato, Fato[Chave1], Fato[Chave2]), "Atributo", LOOKUPVALUE(DePara[Atributo], DePara[Chave1], Fato[Chave1], DePara[Chave2], Fato[Chave2]))` → linhas com blank = faltando no de-para.
- **Medidas**: `Create`/`Update` exigem `TableName`. Mudar de tabela = `Move`, nunca apagar e recriar. `Delete` tem cascade `true` por padrao — conferir.
- **Lote**: `options: {useTransaction:true}`.

## Armadilhas comuns
- **Relacao AutoDetected pela chave errada.** O Desktop cria relacoes sozinho (nome `AutoDetected_...`). Se a chave real e composta (ex.: Motor+Indicador) e a relacao usa so uma coluna, o refresh quebra quando surge um valor repetido ("contem um valor duplicado ... lado de uma relacao muitos para um"). Desativar nao resolve (o lado 1 continua exigindo unicidade). Confirme que nada depende dela e proponha excluir. `relationship_operations` → `Find` pela tabela, `Get` para ver as colunas.
- Erros antigos que aparecem junto no refresh (coluna inexistente em medida ou coluna calculada) nao bloqueiam o resto; apontar, nao corrigir sem pedido.
- Meta/valor que vem 0 ou vazio da origem: corrigir na fonte, nao mascarar no modelo.

## Antes de gravar
Confirmar o relatorio → dizer o que vai mudar (com o codigo exato) → validar → sugerir salvar antes de lote → gravar → reexportar e conferir → pedir refresh/salvar.

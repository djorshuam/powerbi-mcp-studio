# Layouts de mercado + fundo SVG: do zero a uma pagina desenhada

Duas bibliotecas se combinam: **estrutura** (`layouts/`, 10 modelos de pagina usados no mercado de BI) × **estilo** (`designs/`, 74 linguagens visuais). O Claude recomenda a combinacao, mostra previas e monta a pagina.

## Modelos (layouts/INDEX.md)
executivo · z-classico · scorecard · operacional (escuro) · analitico-filtro-lateral · funil-comercial · financeiro-dre · geografico · detalhe-drill · comparativo-periodos. Cada pasta tem `LAYOUT.md` (publico, quando usar, slots, boas praticas), `layout.json` (grade 12 colunas, 1280x720, margem 24, espaco 16, cabecalho 80, KPIs com 128 px minimo) e `previa.png`.

## Fluxo completo (testado 30/09/2026: abriu no Power BI com dados, fundo e tema)
```
python scripts/layout_pbi.py recomendar "diretoria acompanha metas mensais"      # top 3 modelos
python scripts/layout_pbi.py mostrar executivo                                     # slots a preencher
# Claude monta mapa.json com os campos REAIS (liste o modelo via MCP antes; nao invente nomes)
python scripts/layout_pbi.py instanciar --modelo executivo --mapa mapa.json --pagina "Visao Geral" --saida layout.json
# --- Desktop FECHADO a partir daqui ---
python scripts/visuais_pbi.py lote --pbix X.pbix --spec layout.json
python scripts/svg_fundo.py gerar --pbix X.pbix --pagina "Visao Geral" --design designs/<estilo>/DESIGN.md \
       --titulo "Visao Geral" --subtitulo "Atualizado diariamente" --saida fundo.svg
python scripts/svg_fundo.py previa --svg fundo.svg --plano fundo.plano.json --saida previa.png   # OLHE antes de aplicar
python scripts/svg_fundo.py aplicar --pbix X.pbix --pagina "Visao Geral" --arquivo fundo.svg --plano fundo.plano.json --visuais-transparentes
python scripts/tema_pbi.py --design designs/<estilo>/DESIGN.md --pbix X.pbix
```
Mapa: `{"kpi1": {"campos": ["Values=Medida:T[M]"], "titulo": "Receita"}, "tendencia": {"campos": ["Category=Coluna:Cal[Mes]", "Y=Medida:T[M]"]}}` — slot sem mapeamento sai da pagina (ou `--manter-vazios`); `"tipo"` troca o visual do slot.

## Pagina que ja existe
`svg_fundo.py gerar --pbix X.pbix --pagina "P" --reorganizar ...` le as posicoes atuais, encaixa na grade mantendo as linhas e proporcoes, e o `aplicar --plano` move os visuais para dentro dos cartoes. Caixa de texto de titulo no topo e ocultada (o titulo passa a ser desenhado no fundo; `--manter-titulo` para nao ocultar).

## Estilos do fundo (`--estilo`)
- `cartoes` (padrao): degrade suave + formas decorativas discretas, cartoes brancos com sombra em camadas, faixa de destaque no topo dos KPIs, divisor sob o titulo dos graficos, filtros em cartao tonalizado.
- `minimal`: fundo liso, cartoes com borda fina, sem sombra.
- `contraste`: cabecalho em faixa colorida (degrade da cor primaria) com titulo branco.
- `--escuro` em qualquer um (combine com `tema_pbi.py --modo escuro`).
Cores sempre do DESIGN.md (`--design`); sem ele, neutro azul.

## Regras de qualidade (checar na previa)
- Nenhum cartao encostando em outro; margens iguais nas bordas.
- KPIs com altura suficiente para valor + rotulo (>= 128 px em 1280x720).
- Titulo nao duplicado (fundo × caixa de texto).
- No maximo 8 visuais por pagina; tabela embaixo, KPIs em cima.
- Visuais transparentes (fundo/borda/sombra desligados) para o cartao do SVG aparecer.

## Editar o SVG a mao
SVG e XML: ids estaveis (`titulo`, `subtitulo`, `card-N`, `acento-titulo`, `deco-1`). O Claude pode trocar textos, cores, raio e remover decoracoes com Edit/sed e reaplicar. Fundos exportados do Figma com texto em contorno so permitem editar formas e cores.

## Prototipo no Claude Design (opcional)
Se a conta tiver o tipo de artefato **Design**, monte 2–3 opcoes de pagina como pranchetas 1280x720 com os nomes reais dos KPIs para o cliente aprovar antes de construir; depois converta a opcao escolhida em `layout.json` (posicoes das caixas) e siga o fluxo acima. A marca do cliente pode viver num artefato **Design System** e no `clientes/<cliente>/DESIGN.md` (versao portatil para os scripts).

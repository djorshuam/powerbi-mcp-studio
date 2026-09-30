# Biblioteca de layouts

Estruturas de pagina usadas no mercado de BI, prontas para combinar com qualquer estilo da galeria `designs/`.
Todas em grade de 12 colunas, 1280x720, margem 24, espaco 16, cabecalho de 80 px (titulo desenhado no fundo).

Uso: `python scripts/layout_pbi.py recomendar "<publico ou objetivo>"` · `layout_pbi.py instanciar --modelo <pasta> --mapa mapa.json --saida layout.json` · veja `references/layouts.md`.

| Modelo | Pasta | Publico | Quando usar | Previa |
|---|---|---|---|---|
| **Executivo** | `executivo` | diretoria, conselho | visao mensal/semanal de poucos numeros-chave | [ver](executivo/previa.png) |
| **Z classico** | `z-classico` | gestores | painel geral de uma area | [ver](z-classico/previa.png) |
| **Scorecard / farol** | `scorecard` | gestao por metas | acompanhar muitos indicadores contra meta (farol verde/amarelo/vermelho) | [ver](scorecard/previa.png) |
| **Operacional / NOC** | `operacional` | salas de controle, TV, plantao | monitoramento quase em tempo real | [ver](operacional/previa.png) |
| **Analitico com filtro lateral** | `analitico-filtro-lateral` | analistas | exploracao livre com muitos filtros | [ver](analitico-filtro-lateral/previa.png) |
| **Funil comercial** | `funil-comercial` | vendas, marketing | pipeline, conversao por etapa e desempenho da equipe | [ver](funil-comercial/previa.png) |
| **Financeiro (DRE)** | `financeiro-dre` | controladoria, CFO | demonstrativo de resultado, orcado x realizado | [ver](financeiro-dre/previa.png) |
| **Geografico** | `geografico` | redes de unidades, logistica | comparar desempenho por local | [ver](geografico/previa.png) |
| **Detalhe / drill-through** | `detalhe-drill` | operacao, auditoria | pagina de apoio aberta a partir de outra | [ver](detalhe-drill/previa.png) |
| **Comparativo de periodos** | `comparativo-periodos` | gestores | este periodo x anterior x mesmo periodo do ano passado | [ver](comparativo-periodos/previa.png) |

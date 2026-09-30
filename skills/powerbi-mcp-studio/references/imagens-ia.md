# Geracao de imagens com IA (fundos, ilustracoes, rascunhos de layout)

Quando a sessao tem um conector/MCP de geracao de imagens (ex.: Higgsfield, Kairogen ou outro — procure com ToolSearch por "generate image"), o Claude pode gerar:

| Uso | Bom para | Cuidado |
|---|---|---|
| **Rascunho de layout** ("sugestao de visao") | mostrar 2–3 propostas de pagina antes de construir: onde ficam KPIs, graficos, filtros | e so referencia visual; numeros e textos gerados sao falsos — nunca usar como entregavel |
| **Fundo decorativo** (textura, gradiente, faixa de cabecalho) | pagina de capa, relatorio de marketing | contraste com os visuais; prefira fundo discreto; gere em 16:9 (1280×720 ou 1920×1080) |
| **Ilustracao/ícone de capa** | capa, pagina "sobre", estados vazios | estilo coerente com o DESIGN.md; nada de logos/marcas de terceiros |
| **Imagem de produto/unidade** | cards de catalogo, hotsite | direitos de uso; prefira fotos reais do cliente |

## Fluxo
1. Ler o DESIGN.md (cores hex, clima, estilo) e montar o prompt a partir dele: "fundo para dashboard 16:9, minimalista, tons {canvas} e {primary} a 10% de opacidade, sem texto, sem numeros, area central limpa".
2. Estimar custo/creditos quando a ferramenta cobrar e confirmar com o usuario.
3. Gerar 2–3 opcoes, mostrar, deixar escolher.
4. Baixar a escolhida e aplicar: `fundo_pbi.py --pbix X.pbix "<Pagina>" --arquivo fundo.png` (a pagina precisa ter fundo definido uma vez, e o formato precisa ser o mesmo do fundo atual — senao, caminho 2 pela interface).
5. Conferir contraste dos visuais sobre o fundo (`boas-praticas-visuais.md`).

## Rascunho de layout sem IA de imagem
Mais preciso e barato: desenhar o wireframe como **SVG** (retangulos com rotulos "KPI", "Tendencia", "Tabela") nas cores do tema e mostrar na conversa — ou ja gerar o `layout.json` e criar a pagina de verdade com `visuais_pbi.py lote` numa copia do relatorio.

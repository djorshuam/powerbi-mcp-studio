# Boas praticas de construcao de visuais

Checklist para montar ou revisar paginas. Use ao planejar `layout.json`, ao desenhar fundos no Figma e ao revisar um relatorio existente (com `inventario_pbi.py` para ver posicoes e tamanhos).

## Tela e grade
| Uso | Tamanho da pagina | Observacao |
|---|---|---|
| Padrao (monitor/Teams/servico) | **1280 × 720** (16:9) | o mais seguro; tudo o resto escala |
| Alta densidade / TV | 1920 × 1080 | mesma proporcao, fontes proporcionalmente maiores |
| Relatorio longo (rolagem) | 1280 × 1440–2160 | Formatar pagina → Tipo "Personalizado"; bom para detalhe |
| Celular | Layout movel (Exibicao → Layout movel) | reorganize so o essencial: 3–5 cartoes + 1 grafico |
| Impressao/PDF A4 paisagem | 1123 × 794 | exportar PDF sem cortar |
- **Grade de 8 px**: posicoes e tamanhos multiplos de 8; margem externa 16–24 px; espaco entre visuais 16 px.
- Leitura em **Z/F**: o mais importante em cima a esquerda. Topo: titulo + filtros + cartoes (KPIs). Meio: tendencias e comparacoes. Base: detalhe (tabela/matriz).
- No maximo **6–8 visuais por pagina**; mais que isso vira outra pagina ou drill-through.
- Alinhe bordas e iguale alturas dentro da mesma linha (Formatar → Posicao para valores exatos).

## Bordas, cantos e sombras
- Escolha **um** jeito de separar visuais: borda fina (1 px, cor da borda do tema) **ou** fundo de cartao contrastando com a pagina **ou** sombra suave — nao os tres.
- Cantos arredondados 4–12 px, iguais em todos os visuais (o tema aplica o `radius`).
- Sem sombras pesadas nem bordas escuras: competem com os dados.
- Fundo da pagina por imagem (Figma) + visuais transparentes e o jeito mais limpo de ter "cards" desenhados.

## Cor e contraste
- Texto: contraste ≥ **4,5:1** (WCAG AA); titulos grandes ≥ 3:1. Elementos graficos (barras, linhas, icones) ≥ **3:1** contra o fundo. `tema_pbi.py` ja garante isso para o tema.
- **Cor com significado**: verde = bom, vermelho = ruim, ambar = atencao, cinza = neutro/sem dado. Use sempre do mesmo jeito em todo o relatorio (e respeite o "sentido" do indicador: menor pode ser melhor).
- 1 cor de destaque + neutros. Destaque so no que importa (a barra do mes atual, a unidade selecionada).
- **Daltonismo**: nunca so cor para diferenciar — some icone, rotulo ou padrao. Evite par vermelho/verde puro; prefira azul/laranja para comparacoes neutras.
- Paleta categorica: ate 6–8 categorias; acima disso agrupe em "Outros".

## Claro × escuro
- **Claro**: padrao para escritorio, impressao e reunioes com projetor.
- **Escuro**: salas de controle, TV, NOC, uso noturno; reduz brilho. Exige mais contraste e cores menos saturadas.
- Gere os dois: `tema_pbi.py --modo claro` e `--modo escuro`. Fundos do Figma precisam de versao escura tambem (frame separado).
- Nao misture paginas claras e escuras no mesmo relatorio sem motivo.

## Tipografia
- Uma familia (Segoe UI e a mais segura no Power BI; outras fontes so se instaladas em todas as maquinas e no servico).
- Hierarquia: titulo da pagina 20–24 pt · titulo de visual 12–14 pt · rotulos 9–11 pt · numero de KPI 28–40 pt.
- Numeros: separador de milhar, casas decimais consistentes por tipo (%, moeda, inteiro), unidades no titulo ("R$ mil") em vez de em cada rotulo.

## Escolha do visual
| Pergunta | Visual |
|---|---|
| Quanto? (um numero) | Cartao / cartao novo (cardVisual) com comparacao a meta |
| Como evolui? | Linha (tempo continuo), colunas (periodos discretos) |
| Quem e maior? | Barras horizontais ordenadas (rotulos longos) |
| Qual a composicao? | Barras 100% empilhadas; pizza/rosca so com ≤ 5 fatias |
| Relacao entre duas medidas? | Dispersao |
| Onde? | Mapa preenchido/bolhas (com dados geograficos limpos) |
| Detalhe/auditoria | Tabela ou matriz, com formatacao condicional discreta |
| Meta × realizado | KPI, medidor (com parcimonia), barras com linha de meta |
- Evite 3D, eixos cortados sem aviso, dois eixos Y sem necessidade, pizza com muitas fatias, gauge para tudo.

## Acessibilidade e uso
- Texto alternativo em cada visual (Formatar → Geral → Texto alternativo).
- Ordem de tabulacao coerente (Exibicao → Selecao → Ordem de tabulacao).
- Titulos que respondem a pergunta ("Vendas caem 8% no Sul") > titulos genericos ("Vendas por regiao").
- Tooltips com contexto (meta, variacao), filtros visiveis (painel ou segmentacoes) e data de atualizacao na pagina.

## Revisao rapida (use em auditoria de layout)
1. Tudo alinhado na grade? 2. Mais de 8 visuais? 3. Contraste ok? 4. Cores com significado consistente? 5. KPIs no topo? 6. Titulos informativos? 7. Filtros e data de atualizacao visiveis? 8. Funciona no celular (se for usado la)?

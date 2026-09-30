# powerbi-mcp-studio

Skill para o Claude operar relatorios do Power BI Desktop de ponta a ponta.

| Capacidade | Como |
|---|---|
| **Planilha (+ mockup opcional) → dashboard HTML interativo ou Power BI completo**, com visuais recomendados a partir dos dados e numeros validados | `recomendar_visuais.py` + `layout_pbi.py` + `gerar_html.py` + MCP; agente `construtor-dashboard` |
| **Modo HTML Content**: a mesma pagina com o visual do dashboard HTML, via medidas DAX que geram HTML/SVG (alternativa aos visuais nativos) | `html_dax.py`, `visuais_pbi.py visual-custom`, `tmdl_pbi.py` |
| Padrao de modelagem: estrela, Calendario marcado, `_Medidas` com pastas, medidas explicitas | `modelagem_pbi.py` + MCP |
| Paleta a partir de um mockup/print e encaixe do rascunho na grade | `mockup_cores.py`, `layout_pbi.py encaixar` |
| Modelo semantico (medidas, M, relacoes, refresh, DAX) | MCP oficial da Microsoft `powerbi-modeling-mcp` |
| Auditoria (erros, relacoes arriscadas, itens sem uso, DAX de risco, nota 0–100), dicionario, checklist de publicacao, desempenho | `modelo_pbi.py` + `inventario_pbi.py` + MCP |
| Criar paginas e visuais, mover, posicionar pelo Figma | `visuais_pbi.py` |
| 10 layouts de mercado (executivo, scorecard, NOC, DRE, funil...) + fundo SVG com cartoes, sombra e cabecalho nas posicoes dos visuais | `layout_pbi.py` + `svg_fundo.py` + `layouts/` |
| Tema do Power BI a partir de DESIGN.md, com contraste WCAG e modo escuro | `tema_pbi.py` + galeria `designs/` (74 estilos) |
| Fundos de pagina vindos do Figma ou de imagem | `fundo_pbi.py` |
| 1.512 icones Phosphor × 6 pesos, offline → SVG, DAX ou HTML | `icone_pbi.py` |
| Converter dashboard Excel/HTML em Power BI | `extrair_dashboard.py` + agente `conversor-dashboard` |
| Boas praticas de layout, contraste, claro/escuro, imagens por IA, prototipo no Claude Design | `references/` |
| Controle de tela (fechar/reabrir, conferir, interface) | computer use do app Claude |

Funciona com **.pbix (padrao)** e **.pbip** (formato PBIR). Validado em 30/09/2026 no Power BI Desktop 2.158 (set/2026): paginas, visuais, fundos SVG e temas gerados por script abriram e renderizaram com dados.

## Estrutura
```
powerbi-mcp-studio/
├── SKILL.md                     roteador: qual ferramenta, ordem aberto/fechado, seguranca
├── agents/                      construtor-dashboard, designer-powerbi, auditor-powerbi, revisor-visual, conversor-dashboard
├── references/                  instalacao, modelo-mcp, auditoria-modelo, visuais-layout, layouts, design-tema,
│                                boas-praticas-visuais, planilha-para-dashboard, modelagem, modo-html, fundo-pagina, icones, conversao-dashboard, imagens-ia, controle-tela
├── scripts/                     pbi_arquivo (base), visuais_pbi, layout_pbi, svg_fundo, tema_pbi, fundo_pbi,
│                                inventario_pbi, modelo_pbi, icone_pbi, extrair_dashboard, recomendar_visuais,
│                                gerar_html, mockup_cores, modelagem_pbi, html_dax, tmdl_pbi   (Python 3.9+, sem dependencias*)
├── layouts/                     INDEX.md + 10 modelos (LAYOUT.md, layout.json, previa.png)
├── designs/                     INDEX.md + 74 DESIGN.md (MIT, VoltAgent/awesome-design-md)
├── icones/                      phosphor.json.gz (MIT, Phosphor Icons)
├── vendor/                      echarts.min.js (Apache 2.0) para HTML offline
├── config.example.json
└── clientes/_exemplo/           config.json, receitas.md, DESIGN.md do cliente
```
*Opcionais: Playwright/Chromium (`svg_fundo.py previa`), Pillow (`mockup_cores.py`), echarts.min.js local (`gerar_html.py --echarts`, offline).

## Importar no Claude
- **Claude (app/web)**: Configuracoes → Capacidades/Skills → enviar o `powerbi-mcp-studio.zip` (a pasta com o `SKILL.md` na raiz do zip). Os agentes (`agents/`) sao usados pelo Claude Code; no app a skill segue o mesmo roteiro direto.
- **Claude Code**: descompactar em `~/.claude/skills/powerbi-mcp-studio/` e copiar `agents/*.md` para `~/.claude/agents/`.

## Instalar num cliente
1. Copiar a pasta para `~/.claude/skills/powerbi-mcp-studio/` (todas as sessoes) ou `<projeto>/.claude/skills/`. O agente vai em `~/.claude/agents/` (ou empacote tudo como plugin).
2. `references/instalacao.md`: Node.js + MCP `powerbi-modeling` no Claude Desktop/Code.
3. Python 3.9+ na maquina.
4. Figma (opcional): token + conector — `references/fundo-pagina.md` secao A.
5. Controle de tela (opcional): app Claude para desktop com Computer use ligado — `references/controle-tela.md`.
6. Criar `clientes/<cliente>/` a partir de `_exemplo`.

## Aviso importante (.pbix)
Ao alterar paginas/visuais/tema de um .pbix, os scripts removem a parte `SecurityBindings` (sem isso o Desktop acusa "arquivo corrompido"). Se o relatorio tinha rotulo de sensibilidade, reaplique no Desktop. Sempre ha backup `.bak`.

## Licencas de terceiros
- Galeria de design: MIT © VoltAgent (`designs/LICENSE-awesome-design-md.txt`). Analises inspiradas em marcas reais — use como inspiracao.
- Icones: MIT © Phosphor Icons (`icones/LICENSE-phosphor.txt`).
- ECharts (dashboards HTML offline): Apache 2.0 © The Apache Software Foundation (`vendor/LICENSE-echarts.txt`, `vendor/NOTICE-echarts.txt`).

---
name: powerbi-mcp-studio
description: Criar e operar dashboards Power BI (.pbix/.pbip) e HTML de ponta a ponta - planilha ou mockup viram dashboard pronto (recomendacao de visuais a partir dos dados), modelo via MCP oficial da Microsoft, auditoria e dicionario do modelo, paginas e visuais por script, temas a partir de DESIGN.md (galeria com 74 estilos), fundos do Figma, layouts de mercado com fundo SVG gerado, icones Phosphor, conversao de dashboards Excel/HTML e controle de tela. Use para montar um dashboard a partir de planilha/mockup; criar ou corrigir medidas, M, relacoes ou DAX; auditar, documentar ou otimizar um modelo; criar paginas/visuais; aplicar identidade visual; converter planilha ou HTML em Power BI; ou instalar a conexao do Claude com o Power BI.
---

# powerbi-mcp-studio

Ferramentas, **sempre a mais confiavel primeiro**: MCP > script > tela.

| Precisa de... | Ferramenta | Desktop | Leia |
|---|---|---|---|
| **Planilha (+ mockup) → dashboard HTML ou Power BI** | `recomendar_visuais.py` → `layout_pbi.py` → `gerar_html.py` / MCP + visuais; `mockup_cores.py`, `layout_pbi.py encaixar` | ambos | `references/planilha-para-dashboard.md`, `agents/construtor-dashboard.md` |
| **Modo HTML Content** (opcional, so sob pedido: nao e clicavel e nao filtra outros visuais) | `html_dax.py` + `visuais_pbi.py visual-custom` + `tmdl_pbi.py` | ambos | `references/modo-html.md` |
| Gravar medidas num .pbip sem Desktop aberto (so .pbip; no .pbix use MCP) | `scripts/tmdl_pbi.py` | **fechado** | `references/modo-html.md` |
| Recomendar visualizacoes a partir dos dados (ou de um modelo) | `scripts/recomendar_visuais.py` | — | `references/planilha-para-dashboard.md` |
| **Padrao de modelagem** (estrela, Calendario, `_Medidas` com pastas) — aplicar sempre | `scripts/modelagem_pbi.py` + MCP | aberto | `references/modelagem.md` |
| Medidas, colunas, M, relacoes, refresh, DAX | MCP `powerbi-modeling` | aberto | `references/modelo-mcp.md` |
| Auditoria, dicionario, checklist de publicacao, desempenho | `scripts/modelo_pbi.py` + MCP | aberto p/ exportar | `references/auditoria-modelo.md` |
| Paginas e visuais (criar, mover, posicionar pelo Figma) | `scripts/visuais_pbi.py` | **fechado** | `references/visuais-layout.md` |
| Pagina desenhada: layout de mercado + fundo SVG com cartoes | `scripts/layout_pbi.py` + `svg_fundo.py` + `layouts/` (10 modelos) | **fechado** | `references/layouts.md` |
| Tema (cores, fontes, contraste, claro/escuro) | `scripts/tema_pbi.py` + `designs/` | **fechado** | `references/design-tema.md` |
| Fundo de pagina (Figma ou imagem) | `scripts/fundo_pbi.py` | **fechado** | `references/fundo-pagina.md` |
| Icones | `scripts/icone_pbi.py` (Phosphor offline) | — | `references/icones.md` |
| Converter dashboard Excel/HTML | `scripts/extrair_dashboard.py` + MCP + visuais | ambos | `references/conversao-dashboard.md`, `agents/conversor-dashboard.md` |
| Boas praticas de layout, contraste, tela | — | — | `references/boas-praticas-visuais.md` |
| Imagens por IA (rascunhos, fundos) | MCP de imagem, se houver | — | `references/imagens-ia.md` |
| Fechar/reabrir, conferir, Formatar pagina | controle de tela | aberto | `references/controle-tela.md` |
| Instalar o MCP / conectores | — | — | `references/instalacao.md`, `fundo-pagina.md` (Figma) |

## Agentes (agents/)
| Agente | Quando |
|---|---|
| `construtor-dashboard` | planilha/mockup → HTML e/ou Power BI completo |
| `designer-powerbi` | escolher layout e estilo, 2–3 propostas com previa, montar a escolhida |
| `auditor-powerbi` | parecer independente antes de publicar (somente leitura) |
| `revisor-visual` | conferir prints/paginas contra as boas praticas e devolver correcoes |
| `conversor-dashboard` | Excel-painel ou HTML existente → Power BI |
Use o agente quando o ambiente permitir subagentes e a tarefa for grande; senao siga o mesmo roteiro diretamente.

Leia a referencia antes de agir. Cliente com pasta em `clientes/<cliente>/`: leia `receitas.md`, use `config.json` e `DESIGN.md` de la. Os scripts rodam com Python 3.9+ sem dependencias; `inventario_pbi.py` le o relatorio (paginas, visuais, campos usados) e e somente leitura.

## 0. Formato padrao: .pbix
- **Entregue e trabalhe em .pbix por padrao.** Use .pbip so se o usuario pedir, se o arquivo ja for .pbip, ou como contorno pontual com o OK dele (ex.: gravar medidas sem o Desktop aberto) — e depois volte ao .pbix se ele preferir.
- Medidas e modelo num .pbix: sempre via **MCP com o Desktop aberto** (o modelo do .pbix e binario). `tmdl_pbi.py` e so para .pbip.
- Paginas, visuais, tema e fundo num .pbix: scripts com o Desktop fechado (formato PBIR; ver secao 1).

## 1. Descobrir o ambiente
- MCP `ListLocalInstances`: confirme o relatorio pelo `parentWindowTitle` (pode haver varias instancias; conecte na certa). Nada responde → `instalacao.md`.
- **MCP `powerbi-modeling` ausente nesta sessao** (nenhuma ferramenta `powerbi-modeling`/`ListLocalInstances`): nao pare em "nao tenho acesso". Explique em 1 frase que o MCP roda no computador da pessoa e conduza a instalacao: (1) Node.js LTS; (2) instalador automatico `https://github.com/djorshuam/powerbi-mcp-studio/raw/main/instalar/instalar-mcp-windows.ps1` (botao direito → Executar com PowerShell) ou o JSON manual de `references/instalacao.md` (peca o conteudo atual do arquivo e devolva mesclado); (3) fechar o app pelo icone da bandeja e reabrir; (4) testar. Enquanto isso, ofereca o que funciona sem MCP (planilha → HTML, temas, layouts, auditoria de arquivo enviado).
- Formato: `.pbix` (o mais comum) ou `.pbip`. Os scripts de arquivo exigem formato **PBIR** (paginas em `Report/definition/pages/*/page.json`, padrao nos Desktops recentes); formato legado (`Report/Layout`) → codigo 2. **Relatorios novos saem no formato legado se a previa 'PBIR para PBIX' estiver desligada** (Opcoes > Recursos em versao previa): peca ao usuario para ligar, reabrir e salvar uma vez (converte), ou salvar como .pbip; senao, faca pela interface.

## 2. Ordem quando a tarefa mistura caminhos
1. **Aberto**: modelo via MCP → `RefreshWithXMLA` → validar com DAX; exportar `.bim` se for auditar.
2. **Salvar** (Ctrl+S). Publicacao em andamento → esperar o "Exito".
3. **Fechar** o Desktop (o arquivo fica travado e o Desktop regravaria a copia dele por cima).
4. **Fechado**: `visuais_pbi.py`, `tema_pbi.py`, `fundo_pbi.py` (sempre `--dry-run` antes). Cada um gera `.bak`.
5. **Reabrir**, reconectar o MCP (porta nova), conferir e salvar pelo Desktop.

## 3. Seguranca de arquivo (.pbix)
- Scripts recusam gravar com o arquivo aberto, validam o zip e guardam `.bak` com data-hora.
- Mudou a definicao do relatorio (paginas, visuais, tema)? O script **remove o `SecurityBindings`** — sem isso o Desktop diz "arquivo corrompido". Avise o usuario: rotulo de sensibilidade, se existia, precisa ser reaplicado. Trocar so imagem de fundo mantem o `SecurityBindings`.
- Abriu com erro: fechar, restaurar o `.bak` (renomear de volta) e usar o caminho pela interface. Backups de .pbip ficam em `<projeto>/_backup_claude/` (nunca dentro de `definition/`).
- Erro "contem formato de relatorio aprimorado (PBIR)" ao abrir com duplo clique = **outra instalacao antiga do Power BI** associada ao .pbix (veja a versao no log). Solucao: desinstalar a antiga ou mudar o "Abrir com". Contorno: abrir o Power BI e depois o arquivo.
- Nunca editar o arquivo de origem de um cliente sem copia.

## 4. Regras
- **Paginas saem com visuais NATIVOS** (clique filtra, drill, tooltip, exportar). `visuais_pbi.py` aplica o acabamento padrao (titulo 12pt a esquerda, visual transparente sobre o cartao do fundo SVG, sem grade, rotulos nas barras, legenda so com 2+ series, segmentacoes suspensas no cabecalho). Tendencia = `areaChart`; realizado x meta = `lineClusteredColumnComboChart` (Y colunas, Y2 linha); ranking = `clusteredBarChart`. HTML Content so se o usuario pedir, avisando que nao interage.
- Modelos criados ou reorganizados seguem `references/modelagem.md`: estrela, Calendario marcado, `_Medidas` com pastas, medidas explicitas, colunas tecnicas ocultas.
- Nao fazer alteracoes de brinde; apontar e perguntar.
- Dizer o que vai mudar antes; validar DAX antes de gravar; numeros novos validados contra a origem.
- MCP recusou/erro → nao repetir sozinho. Usuario recusou → abortar.
- Tokens (`FIGMA_TOKEN`) nunca no chat, codigo ou repositorio.
- Tela: print antes/depois de acoes importantes; resultado inesperado → parar e avisar.
- Galeria de design = inspiracao; num entregavel, nao reproduzir a identidade de outra marca.

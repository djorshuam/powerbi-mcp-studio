# Changelog

## [1.0.1] - 2026-10-01
Instalação mais fácil, a partir do primeiro uso real.
- `dist/powerbi-mcp-studio.zip`: zip pronto para o app Claude (o "Download ZIP" do GitHub é recusado pelo app).
- `instalar/instalar-mcp-windows.ps1`: configura o MCP do Power BI no Claude Desktop sozinho (instala o Node.js via winget, cria a pasta do npm, faz backup e mescla a configuração).
- `INSTALACAO.md`: passo a passo por ambiente (app desktop, web, Claude Code) e tabela de problemas comuns.
- Skill: quando o MCP não está instalado, conduz a instalação; tabela sintoma → correção no SKILL.md.

## [1.0.0] - 2026-09-30
Primeira versão pública.
- Planilha → modelo estrela + `Calendario` + `_Medidas` com pastas + páginas prontas (visuais nativos com acabamento).
- Recomendação de visuais a partir dos dados; versão HTML interativa (ECharts).
- Edição direta de `.pbix` e `.pbip` (páginas, visuais, fundos, temas) com backup e validação.
- 10 layouts de mercado com fundo SVG gerado; 74 estilos DESIGN.md; temas com contraste WCAG e modo escuro.
- Auditoria do modelo (nota 0–100), dicionário de dados e checklist de publicação.
- Fundos do Figma, 1.512 ícones Phosphor, conversão de dashboards Excel/HTML.
- 5 agentes do Claude Code; instalador `npx` e manifesto de plugin.
- Modo HTML Content opcional.

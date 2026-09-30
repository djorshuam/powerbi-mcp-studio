# Contribuindo

Obrigado pelo interesse! Issues e pull requests são bem-vindos.

- **Bugs:** abra uma issue com a versão do Power BI Desktop, o formato (`.pbix`/`.pbip`), o comando/pedido e a mensagem de erro. Não anexe relatórios com dados sensíveis.
- **Novos layouts ou estilos:** siga o formato de `skills/powerbi-mcp-studio/layouts/` (LAYOUT.md + layout.json + previa.png) ou `designs/` (DESIGN.md).
- **Scripts:** Python 3.9+, somente biblioteca padrão (dependências opcionais precisam de fallback). Todo script que grava arquivo deve usar `pbi_arquivo.Relatorio.gravar()` (backup + validação).
- Antes do PR: `python -m py_compile skills/powerbi-mcp-studio/scripts/*.py` e `node bin/install.js --projeto`.

# Instalação passo a passo

Escolha onde você usa o Claude. A skill sozinha **não instala o MCP**: o MCP do Power BI é um programa que roda no seu computador e é configurado uma vez.

| Onde | O que funciona |
|---|---|
| **App Claude Desktop** (inclusive plano gratuito, se o seu plano permitir MCP local) | planilha → dashboard HTML, temas, layouts, auditoria; **com o MCP**: ler e alterar o modelo do Power BI aberto |
| **App Claude web** | tudo que não depende do seu computador (envie os arquivos na conversa) |
| **Claude Code** (plano pago) | tudo, incluindo agentes e edição direta de `.pbix`/`.pbip` na sua pasta |

## App Claude Desktop (Windows)

1. **Instale a skill:** baixe [powerbi-mcp-studio.zip](https://github.com/djorshuam/powerbi-mcp-studio/raw/main/dist/powerbi-mcp-studio.zip) → *Configurações → Capacidades → Skills* → enviar. (Não use o "Code → Download ZIP" do GitHub.)
2. **Instale o Node.js LTS:** [nodejs.org](https://nodejs.org).
3. **Configure o MCP do Power BI (automático):** baixe [instalar-mcp-windows.ps1](https://github.com/djorshuam/powerbi-mcp-studio/raw/main/instalar/instalar-mcp-windows.ps1), clique com o botão direito → **Executar com PowerShell**. Ele faz backup da sua configuração e só acrescenta o Power BI.
   <details><summary>Prefere fazer à mão?</summary>

   *Configurações → Desenvolvedor → Editar configuração*. Se o arquivo estiver vazio, cole:
   ```json
   {
     "mcpServers": {
       "powerbi-modeling": {
         "command": "C:\\Program Files\\nodejs\\npx.cmd",
         "args": ["-y", "@microsoft/powerbi-modeling-mcp@latest", "--start", "--readwrite", "--require-confirmation"]
       }
     }
   }
   ```
   Se já tiver conteúdo, **não cole por cima**: acrescente só o bloco `"powerbi-modeling"` dentro de `mcpServers` (ou peça ao Claude para mesclar). Caminho com `\\`; confira o seu com `where npx`.
   </details>
4. **Feche o Claude Desktop de verdade** (ícone perto do relógio → Sair) e abra de novo.
5. **Teste:** abra um `.pbix` no Power BI Desktop e peça: *"use a /powerbi-mcp-studio e identifique o arquivo Power BI aberto"*. Na primeira vez, aceite os termos do MCP da Microsoft.

**Não apareceu?** Em *Configurações → Desenvolvedor* o servidor `powerbi-modeling` deve estar listado. Se estiver com erro, confira o Node (`node -v` ≥ 18). Se a opção Desenvolvedor não existir, o seu plano/versão não oferece MCP local.

## Claude Code

```bash
npx github:djorshuam/powerbi-mcp-studio
claude mcp add powerbi-modeling --scope user -- npx -y @microsoft/powerbi-modeling-mcp@latest --start --readwrite --require-confirmation
```
O `npx github:` precisa do **Git** instalado. Sem Git: descompacte o zip acima em `~/.claude/skills/` e copie `agents/*.md` para `~/.claude/agents/`.

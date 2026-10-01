# Instalação passo a passo

Escolha onde você usa o Claude. A skill sozinha **não instala o MCP**: o MCP do Power BI é um programa que roda no seu computador e é configurado uma vez.

| Onde | O que funciona |
|---|---|
| **App Claude Desktop** (inclusive plano gratuito, se o seu plano permitir MCP local) | planilha → dashboard HTML, temas, layouts, auditoria; **com o MCP**: ler e alterar o modelo do Power BI aberto |
| **App Claude web** | tudo que não depende do seu computador (envie os arquivos na conversa) |
| **Claude Code** (plano pago) | tudo, incluindo agentes e edição direta de `.pbix`/`.pbip` na sua pasta |

## App Claude Desktop (Windows)

1. **Instale a skill:** baixe [powerbi-mcp-studio.zip](https://github.com/djorshuam/powerbi-mcp-studio/raw/main/dist/powerbi-mcp-studio.zip) → *Configurações → Capacidades → Skills* → enviar. (Não use o "Code → Download ZIP" do GitHub.)
2. **Node.js:** o instalador do passo 3 instala sozinho se faltar (via winget). Se preferir, instale a versão LTS em [nodejs.org](https://nodejs.org).
3. **Configure o MCP do Power BI (automático):** baixe [instalar-mcp-windows.ps1](https://github.com/djorshuam/powerbi-mcp-studio/raw/main/instalar/instalar-mcp-windows.ps1), clique com o botão direito → **Executar com PowerShell**. Ele faz backup da sua configuração e só acrescenta o Power BI.
   <details><summary>Prefere fazer à mão?</summary>

   *Configurações → Servidores MCP locais (em versões antigas: Desenvolvedor) → Editar configuração*. Se o arquivo estiver vazio, cole:
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

**Não apareceu?** Em *Configurações → Servidores MCP locais* o servidor `powerbi-modeling` deve estar listado. Se estiver com erro, confira o Node (`node -v` ≥ 18). Erro `npm error enoent ... AppData\Roaming\npm` no log: rode `mkdir "%APPDATA%\npm"` no Prompt de Comando (ou `New-Item -ItemType Directory -Force "$env:APPDATA\npm"` no PowerShell) e reabra o app. Se essa opção não existir, o seu plano/versão não oferece MCP local.

## Claude Code

```bash
npx github:djorshuam/powerbi-mcp-studio
claude mcp add powerbi-modeling --scope user -- npx -y @microsoft/powerbi-modeling-mcp@latest --start --readwrite --require-confirmation
```
O `npx github:` precisa do **Git** instalado. Sem Git: descompacte o zip acima em `~/.claude/skills/` e copie `agents/*.md` para `~/.claude/agents/`.

## Problemas comuns (vistos em instalações reais)

| O que aparece | Por quê | Como resolver |
|---|---|---|
| App recusa o zip: *"A skill cannot contain a plugin manifest"* / *"SKILL.md must be in the top-level folder"* | Baixou o repositório inteiro pelo **Code → Download ZIP** do GitHub | Baixe o zip certo: [dist/powerbi-mcp-studio.zip](https://github.com/djorshuam/powerbi-mcp-studio/raw/main/dist/powerbi-mcp-studio.zip) |
| Skill instalada, mas o Claude diz que *"não tem conexão com o Power BI"* | A skill não instala o MCP; ele roda no seu computador | Siga os passos 2 a 5 acima (Node.js + instalador do MCP) |
| `npx` não funciona / *"Node não encontrado"* | Node.js não instalado | O instalador instala via winget; ou baixe a versão LTS em [nodejs.org](https://nodejs.org) |
| Log do MCP: `npm error enoent ... AppData\Roaming\npm` | Node recém-instalado sem a pasta do npm | **Prompt de Comando:** `mkdir "%APPDATA%\npm"` · **PowerShell:** `New-Item -ItemType Directory -Force "$env:APPDATA\npm"` · depois feche o app pela bandeja e reabra |
| `'New-Item' não é reconhecido...` | Comando de PowerShell digitado no Prompt de Comando (cmd) | Use a versão do cmd (`mkdir ...`) ou abra o **PowerShell** |
| Script `.ps1` bloqueado ao executar | Política de execução do Windows | `powershell -ExecutionPolicy Bypass -File "$HOME\Downloads\instalar-mcp-windows.ps1"` |
| Servidor `powerbi-modeling` não aparece em *Servidores MCP locais* | JSON inválido ou app não foi fechado de verdade | Feche pelo ícone perto do relógio → **Sair**; confira o JSON (o instalador valida e faz backup) |
| Claude não acha o relatório | Power BI Desktop fechado ou ainda carregando | Abra o `.pbix`, espere carregar e peça de novo |

**Ver o log do MCP:** *Configurações → Servidores MCP locais → powerbi-modeling → ver logs* (ou a pasta `%APPDATA%\Claude\logs`, arquivo `mcp-server-powerbi-modeling.log`). Mande o log ao Claude: a skill sabe interpretar os erros acima.

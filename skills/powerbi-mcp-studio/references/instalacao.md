# Instalacao do MCP powerbi-modeling (setup do cliente)

Fonte: skill powerbi-modeling. Use so quando o MCP ainda nao estiver instalado.


## Como conduzir

Quem pede isso normalmente quer usar o Power BI, nao aprender a configurar
servidor MCP. Muita gente nunca editou um JSON na vida. Entao:

- **Um passo de cada vez**, e espere a resposta antes de seguir
- **Peca o que voce precisa ver** (versao do Node, conteudo do arquivo)
  em vez de supor
- **Entregue pronto**: conteudo completo para substituir, nao trechos
  para a pessoa encaixar
- **Explique o porque** em uma linha quando algo parecer arbitrario
- Sem jargao desnecessario, sem despejar tudo de uma vez

## O que voce consegue fazer neste ambiente

**Com terminal e sistema de arquivos** (Claude Code): execute os passos
voce mesmo, e so peca confirmacao no que for irreversivel.

**Sem eles** (Claude Desktop, onde o codigo roda isolado): voce nao edita
o arquivo de configuracao nem roda comandos na maquina da pessoa. Guie
passo a passo e entregue o JSON pronto para colar. **Nao finja ter feito**
e nao diga "instalei" quando quem aplicou foi ela.

## Passo 1 - Cliente alvo

Pergunte se ainda nao estiver claro: **Claude Desktop ou Claude Code?** A
configuracao mora em lugares diferentes. Se usa os dois, faca um de cada vez.

## Passo 2 - Node.js

Unico pre-requisito. Nao precisa de Python nem de driver ADOMD.

```
node --version
```

Se faltar, ofereca instalar - nunca instale sem perguntar:

```
winget install --id OpenJS.NodeJS.LTS --exact --accept-package-agreements --accept-source-agreements
```

Depois de instalar, **o PATH da janela atual continua velho**. Reabra o
terminal, ou use o caminho completo `C:\Program Files\nodejs\npx.cmd`.

## Passo 3 - Escolher o modo

Confirme com o usuario. O comportamento e este:

| Flags | Leitura e DAX | Escrita no modelo |
|---|---|---|
| `--start` | direta | bloqueada |
| `--start --readwrite` | direta | permitida, **sem aviso nenhum** |
| `--start --readwrite --require-confirmation` | direta | pede aprovacao |

Recomende a terceira: leitura flui sem atrito e so alteracao pede
aprovacao. A segunda deixa a IA mexer num arquivo de trabalho real sem
perguntar - so use se o usuario insistir, e avise do risco.

## Passo 4a - Claude Code

```
claude mcp add powerbi-modeling --scope user -- npx -y @microsoft/powerbi-modeling-mcp@latest --start --readwrite --require-confirmation
```

**Discuta o escopo antes de rodar.** Sao 21 ferramentas:

- `--scope user` - toda sessao, em qualquer pasta
- `--scope project` - so na pasta atual, gravado em `.mcp.json` (versionavel)
- `--scope local` - so na pasta atual, nao versionado

Em escopo global essas 21 ferramentas entram no contexto de **todas** as
sessoes, inclusive projetos sem nada a ver com Power BI. Se o usuario se
importa com consumo de contexto, prefira `project`.

## Passo 4b - Claude Desktop

Aqui voce nao consegue editar o arquivo. Conduza com paciencia: a pessoa
pode nunca ter mexido em JSON, e um erro de virgula derruba **todos** os
servidores dela de uma vez.

### Como abrir o arquivo (sem cacar pasta)

O caminho mais facil e pela propria interface:

> Settings -> **Servidores MCP locais** -> botao **Editar configuracao**

Isso abre o `claude_desktop_config.json` direto. Ofereca esse caminho
primeiro. Se a pessoa preferir abrir na mao, o arquivo fica em
`%APPDATA%\Claude\claude_desktop_config.json`, ou, na versao da Microsoft
Store, em
`%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json`

### Peca o conteudo atual antes de mandar colar nada

**Nao mande a pessoa fazer o merge sozinha.** Diga algo como:

> Abre o arquivo pelo botao "Editar configuracao", copia tudo o que estiver
> la e cola aqui pra mim. Se estiver vazio, e so me dizer. Eu te devolvo o
> conteudo completo, ja com o Power BI incluido e sem quebrar o que voce
> ja tem.

Ai voce faz o merge e devolve **o arquivo inteiro, pronto para substituir**,
nao um pedaco para encaixar. Peca para ela salvar e depois confirme se
salvou antes de seguir.

Se o arquivo estiver vazio, ou se ela disser que nao existe, o conteudo e
este:

```json
{
  "mcpServers": {
    "powerbi-modeling": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": ["-y", "@microsoft/powerbi-modeling-mcp@latest",
               "--start", "--readwrite", "--require-confirmation"]
    }
  }
}
```

### Cuidados ao montar o JSON

- **Caminho completo do `npx.cmd`.** O Claude Desktop nem sempre resolve
  comandos pelo PATH no Windows; `"npx"` puro falha sem mensagem util. Se
  o Node estiver em outro lugar, peca o resultado de `where npx`.
- **Barras duplas.** Em JSON o caminho vai com `\\`, nunca `\` sozinha.
- **Preserve o que ja existe.** Se houver outros servidores, mantenha
  todos e so acrescente a nova entrada, com virgula separando.
- **Valide o JSON antes de entregar.** Se ficar invalido, o Desktop ignora
  o arquivo inteiro e a pessoa perde todos os servidores de uma vez -
  avise disso, para ela entender por que vale a pena conferir.
- Sugira guardar uma copia do conteudo antigo no chat, como backup, antes
  de substituir.

## Passo 5 - Verificar antes de mandar reiniciar

Nao mande o usuario reiniciar as cegas. Se voce tem terminal, rode o
comando exato que foi gravado e faca o handshake MCP: `initialize`,
`notifications/initialized`, `tools/list`. **Espere 21 ferramentas** e
`serverInfo.name` igual a `powerbi-modeling-mcp`.

A primeira execucao baixa o pacote via npx e demora mais. E normal.

## Passo 6 - Reiniciar e testar na ordem certa

Fechar e reabrir o cliente **por completo**. Depois:

1. "liste as medidas do meu Power BI" - sem prompt
2. "quantas linhas tem a tabela X" - DAX, tambem sem prompt
3. so entao criar uma medida, que deve pedir aprovacao

**Antes do teste 3, peca para salvar o `.pbix`.**

## Problemas comuns

| Sintoma | Causa provavel | Correcao |
|---|---|---|
| `connection closed` | `"npx"` sem caminho completo, ou Node ausente | Usar `C:\Program Files\nodejs\npx.cmd` |
| Erro de certificado / TLS | Proxy corporativo interceptando | `NODE_OPTIONS=--use-system-ca` |
| "Nenhuma instancia encontrada" | Power BI fechado, ou sem arquivo aberto | Abrir um `.pbix` |
| Operacao volta "declined" | O usuario recusou a confirmacao | Abortar, nao repetir |
| Porta antiga nao responde | A porta muda a cada abertura | Rodar `ListLocalInstances` de novo |

### Nunca desligue a verificacao de TLS

Se der erro de certificado, **nao** use `NODE_TLS_REJECT_UNAUTHORIZED=0`:
isso desativa a checagem em todo processo Node da maquina e expoe o
usuario a interceptacao.

O certo e `NODE_OPTIONS=--use-system-ca`, que faz o Node confiar no
repositorio de certificados do Windows - onde a CA da empresa ja costuma
estar - **mantendo** a verificacao ligada:

```
[Environment]::SetEnvironmentVariable('NODE_OPTIONS','--use-system-ca','User')
```

Se encontrar `NODE_TLS_REJECT_UNAUTHORIZED=0` ja configurado, avise o
usuario e ofereca trocar pela opcao acima.

## Remover

Claude Code: `claude mcp remove powerbi-modeling --scope user`

Claude Desktop: apagar a entrada do `claude_desktop_config.json` e reiniciar.

---



### Erro `npm error enoent ... AppData\Roaming\npm` no log do MCP
Node recem-instalado sem a pasta do npm. Correcao: no PowerShell, `New-Item -ItemType Directory -Force "$env:APPDATA\npm"`; depois fechar o Claude Desktop pela bandeja e reabrir.

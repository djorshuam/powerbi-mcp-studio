# Fundo de pagina: Figma (ou imagem) → Power BI

A tecnica: desenhar o "esqueleto" da pagina (titulos, cards, molduras, icones) no Figma e usar como **imagem de fundo** da pagina do Power BI; os visuais ficam por cima. Resultado: layout de design profissional sem pesar o relatorio. O `scripts/fundo_pbi.py` automatiza a troca da imagem.

---

## A. Setup do Figma (uma vez por maquina/cliente)

Sao duas coisas diferentes — o script precisa so da primeira; a segunda e para o Claude **editar** o design.

### A1. Chave de API (Personal Access Token) — para o script exportar frames
1. No Figma (web ou desktop): clique no **avatar/nome** no canto superior esquerdo → **Settings**.
2. Aba **Security** → secao **Personal access tokens** → **Generate new token**.
3. Nome: algo como `powerbi-mcp-studio`. **Expiracao**: escolha uma e anote a data (token vencido = erro 403 no script).
4. Escopos: marque **File content → Read-only**. Nada mais e necessario.
5. Clique **Generate token** e **copie na hora** — o Figma nao mostra de novo.
6. Guarde num arquivo `.env` na pasta do projeto/relatorio (ou onde o script for rodado):
   ```
   FIGMA_TOKEN=figd_xxxxxxxxxxxxxxxxxxxxxxxx
   ```
   ou como variavel de ambiente do usuario no Windows:
   ```
   [Environment]::SetEnvironmentVariable('FIGMA_TOKEN','figd_...','User')
   ```
7. **Nunca** cole o token no chat, em codigo ou em repositorio. Se usar Git, ponha `.env` no `.gitignore`. Vazou? Revogue em Settings → Security e gere outro.

Teste rapido (PowerShell), deve devolver seu e-mail:
```
curl.exe -s -H "X-Figma-Token: $env:FIGMA_TOKEN" https://api.figma.com/v1/me
```

### A2. Conector do Figma no Claude — para o Claude ler e editar o design
- **Claude (app/web)**: Settings → **Connectors** → procurar **Figma** → **Connect** → autorizar com a conta Figma. Depois, na conversa, confira que as ferramentas do Figma aparecem (menu de ferramentas/conectores).
- **Claude Code**: servidor MCP remoto oficial do Figma:
  ```
  claude mcp add --transport http figma https://mcp.figma.com/mcp
  ```
  e autentique quando pedir (`/mcp` mostra o status). Alternativa local: o servidor MCP do app desktop do Figma (Preferences → habilitar o Dev Mode MCP server). Confira a URL/versao atual na documentacao do Figma — muda com frequencia.
- Antes de editar com o conector, carregue a skill de uso que o proprio Figma fornece (`/figma-use` ou `get_figma_skill`).

### A3. Identificar arquivo e frame
- **Chave do arquivo** (`figma_file_key`): trecho da URL `figma.com/design/<CHAVE>/Nome-do-arquivo`.
- **Node-id do frame**: selecione o frame → copie o link → `...?node-id=1740-22` → use **`1740:22`** (hifen vira dois-pontos).
- Nome da pagina no Power BI: rode `python fundo_pbi.py --listar --pbix "<arquivo>"`.

Registre no `config.json` do cliente (ver `config.example.json`):
```json
{ "figma_file_key": "AbC123...", "paginas": { "Visao Geral": "1740:22", "Detalhe": "1758:20" } }
```

---

## B. Desenhar para o Power BI
- **Frame do mesmo tamanho (ou proporcao) da pagina** do Power BI (Formatar pagina → Configuracoes da tela; 16:9 = 1280×720 ou multiplos, ex.: 1920×1080). Assim as coordenadas do Figma viram direto posicao/tamanho dos visuais (aplicando a escala).
- Deixe **"buracos"** (cards vazios, molduras) onde os visuais vao ficar; o Power BI desenha por cima.
- Texto vira contorno no SVG exportado (o script usa `svg_outline_text`), entao a fonte nao precisa estar instalada na maquina de quem abre.
- SVG fica nitido em qualquer zoom e e leve; prefira ao PNG.

### Regra de ouro: nunca editar o frame original
1. Duplicar (`clone()`) o frame e posicionar **abaixo** do original (mesmo x, `y + altura + 200`), nome `<original> (<mudanca>)`.
2. Editar **so a copia**. Na copia os filhos tem IDs novos: ache pelo indice — `copia.children[original.children.findIndex(n => n.id === ID)]`.
3. Apontar o `config.json` para o node-id da copia. O original fica como historico/rollback.
4. Remover elemento: `visible = false` (reversivel), nao apagar.
5. Texto: carregar a fonte antes de mudar (`getStyledTextSegments(['fontName'])` → `loadFontAsync`).
6. Bloco novo: clonar os elementos de um bloco existente (card, titulo, linha, icone) e reposicionar — mantem o estilo identico.
7. Conferir com screenshot do frame (`await node.screenshot({scale:0.15})`) antes de exportar.

---

## C. Aplicar no Power BI

**Atencao — fundo compartilhado**: paginas diferentes podem apontar para o **mesmo arquivo** de fundo (acontece quando a imagem foi escolhida uma vez e reaproveitada). Trocar o fundo de uma troca o de todas. Rode `--listar` antes; o script avisa. Para separar, defina pela interface uma imagem diferente na pagina que deve mudar (caminho 2) e depois use o caminho 1.

**Pre-requisito**: a pagina ja precisa ter **uma imagem de fundo** definida uma vez (Formatar pagina → Plano de fundo da tela → Imagem). O script **substitui** o arquivo, nao cria a configuracao. O formato exportado segue o do fundo atual (svg/png/jpg). Se a pagina nao tiver fundo, use o caminho 2 uma vez.

### Caminho 1 (padrao) — script, Desktop FECHADO
```
python fundo_pbi.py --pbix "C:\...\Relatorio.pbix" "Visao Geral" --frame 1740:22 --figma-file AbC123
python fundo_pbi.py --pbix "C:\...\Relatorio.pbix" --config config.json          # todas do config
python fundo_pbi.py --pbip "C:\...\Projeto" "Visao Geral" --config config.json    # .pbip
python fundo_pbi.py --pbix "C:\...\Relatorio.pbix" "Visao Geral" --arquivo fundo.svg   # sem Figma
```
Sempre rode antes com `--dry-run`. O script:
- recusa se o arquivo estiver aberto no Desktop (nao cria nada);
- no .pbix, troca so a imagem dentro do zip, preservando ordem e compressao de todas as entradas; valida o zip antes de gravar; gera `<arquivo>.<data-hora>.bak`;
- entende os dois formatos internos do .pbix (PBIR `Report/definition/pages/*/page.json` e o legado `Report/Layout`).

Saidas: **0** ok · **2** estrutura nao reconhecida → caminho 2 · **1** outros erros (token, rede, pagina sem fundo, arquivo aberto).

Depois: reabrir o arquivo e conferir. Abriu com erro? Feche, restaure o `.bak` (renomeie de volta) e use o caminho 2.

### Caminho 2 (fallback) — exportar + aplicar pela tela, Desktop ABERTO
1. `python fundo_pbi.py --exportar C:\fundos "Visao Geral" --frame 1740:22 --figma-file AbC123` (so baixa o SVG).
2. Pela tela (`controle-tela.md`): pagina → Formatar pagina → Plano de fundo da tela → Imagem → Procurar → arquivo → Ajuste "Ajustar", Transparencia 0%.
3. Salvar.

### Rede
O script chama `api.figma.com`. Se o ambiente onde o Claude roda nao alcancar o Figma, o **usuario** roda o script na maquina dele (ou exporta o SVG manualmente no Figma: selecionar frame → Export → SVG) e usa `--arquivo`.

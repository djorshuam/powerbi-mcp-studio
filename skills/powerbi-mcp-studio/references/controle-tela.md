# Controle de tela (Power BI Desktop)

Use **so** para o que MCP e script nao fazem: fechar/reabrir o Desktop, conferir visualmente, Formatar pagina (fundo no caminho 2), mexer em visuais/layout de .pbix. E o caminho mais lento e sujeito a erro — trate cada clique com cuidado. Carregue antes a skill `computer-use`, se existir.

## Setup (uma vez por maquina)
1. **App Claude para desktop** instalado e logado na maquina que tem o Power BI.
2. Settings → **Desktop app** → ligar **Computer use** (vem desligado).
3. Na conversa, o Claude pede acesso por aplicativo; o usuario aprova cada um.

## Acesso na sessao
1. `computer_resolve_access` → `["Power BI Desktop"]` → `computer_request_access` com as entradas **verbatim**.
2. Peca tambem **"File Explorer"** (nivel so-clique). Sem ele, quando a area de trabalho fica em primeiro plano todo clique e recusado ("desktop shell is frontmost"); com ele, um clique na janela do Power BI a traz para frente. Tambem e o que permite navegar no dialogo "Abrir arquivo".
3. "Computer use nao esta ligado" → `computer_request_access` so com `reason` (mostra o botao para ligar).

## Monitor e coordenadas
- Com mais de um monitor, o Power BI pode nao estar no principal. O print informa os monitores disponiveis: `computer_switch_display` para o certo antes de tudo.
- Coordenadas de clique sao **sempre no frame completo** informado no print (ex.: 1456×819), mesmo quando o print vem em escala 0.5/0.6. Para clicar em botoes pequenos (faixa de opcoes), tire o print em **escala 1** ou faca `zoom` e confirme o alvo antes.
- Faixa de opcoes e perigosa: botoes vizinhos criam coisas (um clique errado em "Novo visual" cria um visual vazio que Ctrl+Z pode nao desfazer). Se houver alternativa (ex.: refresh via MCP), use a alternativa.
- Print depois de cada acao importante. Resultado inesperado → **parar e avisar**, sem tentar de novo as cegas.
- Ao terminar: `computer_release_lock`.

## Armadilhas ja vistas
- **Print vazio** ("empty capture 0x0") em todos os monitores = tela **bloqueada** (Win+L) ou protegida. Parar e pedir para desbloquear.
- **Acesso expira** apos ~30 min sem uso: refazer `computer_resolve_access` + `computer_request_access`.
- **`computer_open_application` abre uma NOVA instancia** do Power BI a cada chamada (cada uma com seu motor, pesando a maquina). Para trazer uma janela existente para frente, clique no icone da barra de tarefas e escolha a miniatura. Feche instancias "Sem titulo" que sobrarem (miniatura → X).
- **Varias instancias**: `ListLocalInstances` do MCP mostra todas; conecte pela `parentWindowTitle` certa.
- **Dialogo "Abrir" do Windows**: prefira a lista de Recentes do Power BI; no dialogo, navegue por cliques na pasta e de **duplo clique no arquivo**; digitar o caminho pode nao registrar.
- Maquina lenta: espere mais (abrir relatorio 60–90 s) e confirme pelo MCP (`ListLocalInstances` mostra o titulo quando carregou) em vez de prints repetidos.
- Se o usuario estiver na frente do computador, pedir que ele abra/feche e mande o print costuma ser mais rapido que a tela.

- **Duas instalacoes do Power BI** (Store + MSI antiga): duplo clique abre a antiga (erro de PBIR). Abra o Desktop pelo menu e use Arquivo > Abrir; recomende desinstalar a antiga.

## Receitas
- **Fechar**: dispensar dialogos abertos → X no canto superior direito. Se aparecer "Salvar alteracoes?", **perguntar ao usuario**. Nunca cancelar nem fechar durante **"Publicando no Power BI"** — esperar o "Exito".
- **Reabrir**: `computer_open_application("Power BI Desktop")` → esperar a tela inicial (~30–45 s) → lista **Recentes** → clicar no arquivo → esperar ~60–90 s (passa por "Sem titulo" e "Carregando as consultas"). Depois **reconectar o MCP** (porta nova).
- **Conferir**: `zoom` no canvas; checar fundo, visuais carregados, valores esperados.
- **Fundo pela interface (caminho 2)**: clicar numa area vazia do canvas (nada selecionado) → painel Visualizacoes → Formatar pagina (pincel) → **Plano de fundo da tela** → Imagem → **Procurar** → navegar ate o arquivo (dialogo do Windows: so cliques) → Ajuste de imagem **Ajustar** → Transparencia **0%**.
- **Salvar**: Ctrl+S com o Power BI em primeiro plano.

## Ponte de arquivos (quando o Claude roda na nuvem ligado ao computador)
- Escrever por cima de um arquivo existente pela ponte pode nao refletir no shell do dispositivo: grave com nome novo e copie por cima no shell; confira com `md5sum`/`grep`.
- Nao dispare gravacao e execucao em paralelo; rode em sequencia.
- Apagar arquivos exige permissao; sem ela, mova sobras para `_to_delete/`.
- Pastas `.claude/` costumam ser protegidas: entregue o arquivo para o usuario copiar.

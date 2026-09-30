# Design: DESIGN.md, galeria e tema do Power BI

Um **DESIGN.md** (formato do Google Stitch) descreve a linguagem visual em texto: cores, tipografia, espacamento, bordas, componentes, faca/nao faca. Um arquivo so alimenta tudo: **tema do Power BI**, **fundos no Figma**, **medidas HTML/SVG** e icones.

## 1. Escolher a base
- **Cliente com marca**: criar `clientes/<cliente>/DESIGN.md` a partir do manual da marca/site/logotipo (cores com hex, fontes, tom). Estrutura: copie o cabecalho YAML de qualquer design da galeria e troque os valores.
- **Sem marca / buscando inspiracao**: `designs/INDEX.md` lista 74 linguagens visuais por categoria (IA, dev tools, fintech, e-commerce, automotivo, midia...), com estilo e cores principais. Mostre 3–5 opcoes coerentes com o publico do relatorio e deixe o usuario escolher. Pode-se misturar (ex.: estrutura de um, paleta de outro).
- Os designs da galeria sao **analises inspiradas** em marcas reais (licenca MIT do repositorio de origem). Use como inspiracao; num entregavel de cliente, nao reproduza a identidade de outra marca (logo, nome, assinatura visual reconhecivel).

## 2. Gerar e aplicar o tema
```
python scripts/tema_pbi.py --design designs/stripe/DESIGN.md --saida tema.json               # so gera
python scripts/tema_pbi.py --design clientes/x/DESIGN.md --modo escuro --saida tema-dark.json
python scripts/tema_pbi.py --design clientes/x/DESIGN.md --pbix "C:\...\Relatorio.pbix"      # aplica (Desktop FECHADO)
python scripts/tema_pbi.py --mostrar --pbix "C:\...\Relatorio.pbix"                           # tema atual
```
O que o script faz:
- Le o cabecalho YAML (`colors`, `typography`, `rounded`); sem YAML, le as linhas `**Nome** (\`#hex\`): uso` do texto; sem nada disso → codigo 2 e o Claude escreve um `tokens.json` (formato no `--help` do script).
- Identifica papeis: primaria, fundo, superficie, texto, texto secundario, borda, bom/ruim/neutro; monta paleta de dados com 8+ cores distintas (completa por rotacao de matiz quando a marca e monocromatica).
- Fontes: mapeia familias web para fontes que o Power BI tem (Inter/SF → Segoe UI, Helvetica → Arial, mono → Consolas...) e avisa a substituicao. Peso do titulo vira Segoe UI Light/Semibold.
- **Contraste garantido**: texto ≥ 4,5:1, texto secundario ≥ 3:1, cores de dados ≥ 3:1 contra o fundo (WCAG 2.1); ajusta e avisa.
- `--modo escuro`: usa o tom escuro da propria marca (ink/dark/inverse) ou #121418, recalcula superficie, borda e texto claros, e reajusta a paleta.
- Aplica no .pbix/.pbip (formato PBIR): grava o JSON em `RegisteredResources`, registra em `report.json` (`themeCollection.customTheme` + `resourcePackages`), substitui o tema customizado anterior, gera `.bak`.
- Formato legado (codigo 2): gere com `--saida` e aplique pela interface: **Exibicao → Temas → Procurar temas**.

## 3. Usar o mesmo design no resto
- **Fundos (Figma)**: passe o DESIGN.md para o Claude ao desenhar/editar frames (cores, raio, espacamento, tipografia) — ver `fundo-pagina.md`.
- **Medidas HTML/SVG**: use as mesmas cores/fonte do tema nas medidas que geram HTML (farol, cards, arvores) — defina variaveis no topo da medida (`VAR _cor_ok = "#1A7F37"`).
- **Icones**: `icone_pbi.py --cor <primaria do tema>` (ver `icones.md`).
- Registre o tema escolhido no `clientes/<cliente>/receitas.md`.

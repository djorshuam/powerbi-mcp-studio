# Icones (Phosphor, offline)

`icones/phosphor.json.gz` traz os **1.512 icones do Phosphor em 6 pesos** (regular, thin, light, bold, fill, duotone) — 9.072 SVGs, licenca MIT (`icones/LICENSE-phosphor.txt`), sem internet. Estilo limpo e consistente, bom para dashboards.

## Buscar
```
python scripts/icone_pbi.py --buscar hospital          # nome, tags e categorias (em ingles)
python scripts/icone_pbi.py --buscar "seta cima"        # termos comuns em portugues sao traduzidos
```
Catalogo visual: https://phosphoricons.com

## Usar no Power BI
| Onde | Como |
|---|---|
| Fundo desenhado (Figma) | exportar SVG (`--saida`) e colar no frame; ou usar o plugin do Phosphor no Figma |
| Visual Imagem estatico | `--saida icone.svg` → Inserir → Imagem |
| Tabela/matriz (icone por linha) ou icone dinamico | `--formato dax` gera medida `data:image/svg+xml`; defina **Categoria de dados = URL da imagem** na medida |
| Cor por status | `--formato dax --cor-medida "[Cor Status]"` (medida que devolve `#RRGGBB`) |
| Visual HTML (medidas que geram HTML) | `--formato html` gera `<svg>` com aspas simples, pronto para concatenar |
| Muitos de uma vez | `--lote heart,users,bed --peso fill --cor #0D253D --pasta icones` |

Dicas: use a cor primaria ou o texto secundario do tema; um peso so no relatorio inteiro (regular ou duotone ficam bons); tamanho 16–24 px em rotulos, 32–48 px em cartoes.

## Font Awesome
Alternativa conhecida. **Free**: icones sob CC BY 4.0 (exige atribuicao), ~2.000 icones. **Pro**: licenca paga por usuario — **nao** empacotar em produto para cliente. Se o cliente ja usa FA, baixe os SVGs Free do pacote oficial e trate como arquivo local (`--arquivo` no fundo, ou cole o SVG na medida DAX no mesmo formato gerado pelo `icone_pbi.py`). Padrao da skill: Phosphor (MIT, sem atribuicao obrigatoria no relatorio).

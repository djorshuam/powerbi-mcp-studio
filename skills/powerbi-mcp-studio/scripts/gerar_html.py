"""
gerar_html.py - Gera um DASHBOARD HTML interativo (um arquivo so) a partir do mesmo layout.json usado
no Power BI: mesmos visuais, mesmas posicoes, mesmo estilo (DESIGN.md + fundo SVG), dados embutidos,
filtros por segmentacao e clique nos graficos. Parte da skill powerbi-mcp-studio.

Uso:
    python gerar_html.py --layout layout.json --dados pasta_com_csv/ [--medidas medidas.json] \
        [--design DESIGN.md] [--titulo "..."] [--subtitulo "..."] [--escuro] [--estilo cartoes|minimal|contraste] \
        --saida dashboard.html

- Tabelas: cada CSV vira a tabela <nome do arquivo> (o mesmo nome usado nos campos "Tipo:Tabela[Campo]").
- Coluna derivada "<coluna> Mes" (ano-mes) e criada automaticamente para colunas de data.
- Medidas: "Medida:T[Nome]" usa medidas.json (gerado pelo recomendar_visuais.py; campo "js").
- Graficos: ECharts via CDN (jsdelivr); --offline embute a copia em vendor/ (ou --echarts caminho): funciona sem internet (~1 MB a mais).
  Mapa vira ranking em barras (sem geometria offline).
- Publicar: abrir no navegador, enviar o arquivo, ou publicar como Artifact no Claude.
"""
import csv, json, re, sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))


def a(n, d=None):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


def conv(v):
    s = str(v).strip()
    if s == "":
        return None
    t = s.replace("R$", "").strip()
    if re.fullmatch(r"-?\d+(\.\d+)?([eE]-?\d+)?", t):
        return float(t)
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?|-?\d+,\d+", t):
        return float(t.replace(".", "").replace(",", "."))
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:19], f).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s


def ler_tabela(p):
    txt = Path(p).read_text(encoding="utf-8-sig", errors="replace")
    sep = ";" if txt[:5000].count(";") > txt[:5000].count(",") else ","
    rows = [r for r in csv.reader(txt.splitlines(), delimiter=sep) if any(c.strip() for c in r)]
    cab = rows[0]
    dados = [[conv(x) for x in (r + [""] * (len(cab) - len(r)))[:len(cab)]] for r in rows[1:]]
    # colunas de data -> "<col> Mes"
    for j, c in enumerate(list(cab)):
        vals = [r[j] for r in dados if r[j] is not None][:200]
        if vals and all(isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in vals):
            cab.append(f"{c} Mes")
            for r in dados:
                r.append(r[j][:7] if r[j] else None)
    return re.sub(r"\W+", "_", Path(p).stem).strip("_"), {"colunas": cab, "linhas": dados}


def campo(spec):
    m = re.fullmatch(r"\s*(\w+)\s*:\s*'?([^'\[]+?)'?\s*\[([^\]]+)\]\s*", spec)
    if not m:
        raise SystemExit(f"campo invalido: {spec}")
    tipo, tab, nome = m.groups()
    ag = {"Soma": "sum", "Media": "avg", "Contagem": "count", "ContagemDistinta": "distinct", "Min": "min", "Max": "max"}
    if tipo == "Coluna":
        return {"k": "col", "t": tab, "c": nome}
    if tipo == "Medida":
        return {"k": "med", "t": tab, "c": nome}
    return {"k": "agg", "t": tab, "c": nome, "agg": ag[tipo], "rotulo": f"{tipo} de {nome}"}


HTML = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITULO__</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
<style>
:root{--texto:__TEXTO__;--mudo:__MUDO__;--p:__P__;--borda:__BORDA__;--card:__CARD__;--fundo:__FUNDO__}
*{box-sizing:border-box}html,body{margin:0;background:var(--fundo);font-family:"Segoe UI",system-ui,-apple-system,Arial,sans-serif;color:var(--texto)}
#pal{position:relative;width:__W__px;height:__H__px;transform-origin:0 0;margin:0 auto}
#pal>svg{position:absolute;inset:0}
.v{position:absolute;display:flex;flex-direction:column;overflow:hidden}
.v h3{margin:0 0 4px;font-size:13px;font-weight:600;color:var(--texto);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;height:22px;line-height:22px}
.v .corpo{flex:1;min-height:0;position:relative}
.kpi .valor{font-size:34px;font-weight:300;letter-spacing:-.5px;line-height:1.1;margin-top:6px}
.kpi .rot{font-size:11.5px;color:var(--mudo);margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:12px}th{position:sticky;top:0;background:var(--card);text-align:left;color:var(--mudo);font-weight:600;border-bottom:2px solid var(--p);padding:5px 6px}
td{padding:4px 6px;border-bottom:1px solid var(--borda)}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.rolagem{position:absolute;inset:0;overflow:auto}
.sl label{display:flex;gap:6px;align-items:center;font-size:12.5px;padding:3px 2px;cursor:pointer}
.sl input{accent-color:var(--p)}
#limpar{position:absolute;right:24px;top:24px;font:12px inherit;border:1px solid var(--borda);background:var(--card);color:var(--texto);border-radius:999px;padding:6px 12px;cursor:pointer;display:none}
.nota{font-size:10.5px;color:var(--mudo);position:absolute;bottom:0;right:4px}
</style></head><body>
<div id="pal">__SVG__<button id="limpar" onclick="limpar()">Limpar filtros</button></div>
<script>
const TAB=__DADOS__, VIS=__VISUAIS__, MED=__MEDIDAS__, PAL=__PALETA__, W=__W__, H=__H__;
const filtros={}; // "tabela|coluna" -> Set
const nf=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2});
function fmt(v,tags){ if(v==null||isNaN(v))return '—';
  if(tags&&tags.includes('pct'))return (v*100).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%';
  const a=Math.abs(v), m=tags&&tags.includes('moeda')?'R$ ':'';
  if(a>=1e9)return m+nf.format(v/1e9)+' bi'; if(a>=1e6)return m+nf.format(v/1e6)+' mi'; if(a>=1e4)return m+nf.format(v/1e3)+' mil';
  return m+nf.format(v);}
function idx(t,c){const i=TAB[t].colunas.indexOf(c); if(i<0)throw new Error('coluna '+t+'['+c+'] nao existe'); return i;}
function linhas(t,ignorar){ const T=TAB[t]; const fs=Object.entries(filtros).filter(([k,s])=>k.startsWith(t+'|')&&k!==ignorar&&s.size);
  if(!fs.length)return T.linhas; const ix=fs.map(([k,s])=>[idx(t,k.split('|')[1]),s]);
  return T.linhas.filter(r=>ix.every(([i,s])=>s.has(String(r[i]))));}
function agg(rows,t,op,c){ if(op==='count')return rows.length; const i=idx(t,c);
  if(op==='distinct')return new Set(rows.map(r=>r[i]).filter(x=>x!=null)).size;
  const v=rows.map(r=>r[i]).filter(x=>typeof x==='number'); if(!v.length)return null;
  if(op==='sum')return v.reduce((a,b)=>a+b,0); if(op==='avg')return v.reduce((a,b)=>a+b,0)/v.length;
  if(op==='min')return Math.min(...v); if(op==='max')return Math.max(...v);}
function valor(rows,f){ if(f.k==='agg')return agg(rows,f.t,f.agg,f.c);
  if(f.k==='med'){const m=MED[f.c]; if(!m)return null; const A=agg(rows,f.t,m.js.a[0]==='sum'?'sum':m.js.a[0],m.js.a[1]), B=agg(rows,f.t,m.js.b[0]==='sum'?'sum':m.js.b[0],m.js.b[1]);
    if(!B)return null; return m.js.op==='margem'?(A-B)/A:A/B;} return null;}
function tagsDe(f){ if(f.k==='med'&&MED[f.c])return MED[f.c].tags||[]; if(f.agg==='avg'&&/%|perc|taxa|pct|margem/i.test(f.c))return['pct'];
  if(/valor|receita|custo|preco|faturamento|venda|despesa|lucro|ticket|meta/i.test(f.c)&&f.k!=='agg'||(/valor|receita|custo|preco|faturamento|venda|despesa|lucro|ticket|meta/i.test(f.c)&&['sum','avg','min','max'].includes(f.agg)))return['moeda']; return [];}
function rot(f){return f.rot||(f.k==='med'?f.c:f.rotulo||f.c);}
function grupos(rows,cat,ys){ const i=idx(cat.t,cat.c), m=new Map(); for(const r of rows){const k=r[i]==null?'(vazio)':String(r[i]); if(!m.has(k))m.set(k,[]); m.get(k).push(r);}
  return [...m.entries()].map(([k,rs])=>({k,v:ys.map(y=>valor(rs,y))}));}
const charts={};
function alternar(t,c,k){const key=t+'|'+c; filtros[key]=filtros[key]||new Set(); filtros[key].has(k)?filtros[key].delete(k):filtros[key].add(k); tudo();}
function limpar(){for(const k in filtros)delete filtros[k]; document.querySelectorAll('.sl input').forEach(i=>i.checked=false); tudo();}
const base={textStyle:{fontFamily:'Segoe UI, Arial'},color:PAL,grid:{left:8,right:16,top:28,bottom:8,containLabel:true},tooltip:{trigger:'axis',valueFormatter:null}};
function eixo(){return{axisLine:{lineStyle:{color:getComputedStyle(document.documentElement).getPropertyValue('--borda')}},axisLabel:{color:getComputedStyle(document.documentElement).getPropertyValue('--mudo'),fontSize:11},splitLine:{lineStyle:{color:getComputedStyle(document.documentElement).getPropertyValue('--borda'),type:'dashed'}}};}
function desenhar(v,el){
  const t=(v.cat||v.vals[0]).t, rows=linhas(t, v.cat?t+'|'+v.cat.c:null), corpo=el.querySelector('.corpo');
  if(v.tipo==='card'||v.tipo==='cardVisual'||v.tipo==='kpi'||v.tipo==='gauge'&&!v.cat){const f=v.vals[0]; corpo.innerHTML=`<div class="valor">${fmt(valor(rows,f),tagsDe(f))}</div><div class="rot">${rot(f)}</div>`; return;}
  if(v.tipo==='multiRowCard'){corpo.innerHTML=v.vals.map(f=>`<div style="margin:6px 0"><div class="valor" style="font-size:22px">${fmt(valor(rows,f),tagsDe(f))}</div><div class="rot">${rot(f)}</div></div>`).join(''); return;}
  if(v.tipo==='slicer'){ if(corpo.dataset.ok)return; const i=idx(v.vals[0].t,v.vals[0].c); const vs=[...new Set(TAB[v.vals[0].t].linhas.map(r=>r[i]).filter(x=>x!=null).map(String))].sort();
    corpo.innerHTML='<div class="rolagem sl">'+vs.map(x=>`<label><input type="checkbox" value="${x}">${x}</label>`).join('')+'</div>';
    corpo.querySelectorAll('input').forEach(inp=>inp.onchange=()=>alternar(v.vals[0].t,v.vals[0].c,inp.value)); corpo.dataset.ok=1; return;}
  if(v.tipo==='tableEx'||v.tipo==='pivotTable'){ const cats=v.vals.filter(f=>f.k==='col'), nums=v.vals.filter(f=>f.k!=='col');
    let lin; if(cats.length&&nums.length){const ix=cats.map(c=>idx(c.t,c.c)), m=new Map(); for(const r of rows){const k=ix.map(i=>r[i]).join('\u0001'); if(!m.has(k))m.set(k,[]); m.get(k).push(r);}
      lin=[...m.entries()].map(([k,rs])=>[...k.split('\u0001'),...nums.map(f=>valor(rs,f))]).sort((a,b)=>(b[cats.length]||0)-(a[cats.length]||0)).slice(0,200);}
    else {const ix=v.vals.map(c=>idx(c.t,c.c)); lin=rows.slice(0,200).map(r=>ix.map(i=>r[i]));}
    const tot=nums.map(f=>valor(rows,f));
    corpo.innerHTML='<div class="rolagem"><table><thead><tr>'+v.vals.map((f,j)=>`<th class="${f.k!=='col'?'n':''}">${rot(f)}</th>`).join('')+'</tr></thead><tbody>'+
      lin.map(r=>'<tr>'+r.map((x,j)=>j>=cats.length&&nums.length?`<td class="n">${fmt(x,tagsDe(nums[j-cats.length]))}</td>`:`<td>${x??''}</td>`).join('')+'</tr>').join('')+
      (nums.length&&cats.length?'<tr style="font-weight:600">'+cats.map((c,j)=>`<td>${j?'':'Total'}</td>`).join('')+tot.map((x,j)=>`<td class="n">${fmt(x,tagsDe(nums[j]))}</td>`).join('')+'</tr>':'')+'</tbody></table></div>'; return;}
  // graficos
  const g=grupos(rows,v.cat,v.vals); const ch=charts[v.id]||(charts[v.id]=echarts.init(corpo,null,{renderer:'svg'}));
  const tempo=/Mes$|data|date|mes|ano|periodo/i.test(v.cat.c); if(tempo)g.sort((a,b)=>a.k<b.k?-1:1); else g.sort((a,b)=>(b.v[0]||0)-(a.v[0]||0));
  const tags=tagsDe(v.vals[0]), vf=x=>fmt(x,tags); let op;
  const ks=g.map(x=>x.k), series=(tipo,extra={})=>v.vals.map((f,j)=>Object.assign({name:rot(f),type:tipo,data:g.map(x=>x.v[j]),emphasis:{focus:'series'}},extra));
  if(['lineChart','areaChart'].includes(v.tipo)) op={...base,xAxis:{type:'category',data:ks,...eixo()},yAxis:{type:'value',...eixo(),axisLabel:{...eixo().axisLabel,formatter:vf}},
     series:series('line',{smooth:true,symbolSize:5,areaStyle:v.tipo==='areaChart'||v.vals.length===1?{opacity:.12}:undefined})};
  else if(['clusteredBarChart','stackedBarChart','filledMap','map'].includes(v.tipo)){const top=g.slice(0,15).reverse();
     op={...base,xAxis:{type:'value',...eixo(),axisLabel:{...eixo().axisLabel,formatter:vf}},yAxis:{type:'category',data:top.map(x=>x.k),...eixo()},
     series:v.vals.map((f,j)=>({name:rot(f),type:'bar',data:top.map(x=>x.v[j]),barMaxWidth:18,itemStyle:{borderRadius:[0,4,4,0]},stack:v.tipo==='stackedBarChart'?'s':undefined}))};}
  else if(['pieChart','donutChart'].includes(v.tipo)) op={...base,tooltip:{trigger:'item',valueFormatter:vf},legend:{orient:'vertical',right:0,top:'middle',textStyle:{color:'inherit',fontSize:11}},
     series:[{type:'pie',radius:v.tipo==='donutChart'?['48%','75%']:'75%',center:['38%','52%'],data:g.map(x=>({name:x.k,value:x.v[0]})),label:{formatter:'{d}%',fontSize:11},itemStyle:{borderColor:getComputedStyle(document.documentElement).getPropertyValue('--card'),borderWidth:2}}]};
  else if(v.tipo==='funnel') op={...base,tooltip:{trigger:'item',valueFormatter:vf},series:[{type:'funnel',left:'8%',width:'84%',data:g.map(x=>({name:x.k,value:x.v[0]})),label:{fontSize:11}}]};
  else op={...base,legend:v.vals.length>1?{top:0,right:0,textStyle:{fontSize:11}}:undefined,xAxis:{type:'category',data:ks,...eixo()},yAxis:{type:'value',...eixo(),axisLabel:{...eixo().axisLabel,formatter:vf}},
     series:series('bar',{barMaxWidth:36,itemStyle:{borderRadius:[4,4,0,0]},stack:v.tipo==='stackedColumnChart'?'s':undefined})};
  op.tooltip={...(op.tooltip||base.tooltip),valueFormatter:vf};
  const sel=filtros[v.cat.t+'|'+v.cat.c]; if(sel&&sel.size&&op.series)op.series.forEach(s=>{if(Array.isArray(s.data))s.data=s.data.map((d,j)=>{const k=typeof d==='object'&&d?d.name:ks[j]; const val=typeof d==='object'&&d?d.value:d; return {value:val,name:k,itemStyle:{opacity:sel.has(k)?1:.3}};});});
  ch.setOption(op,true); ch.off('click'); ch.on('click',p=>alternar(v.cat.t,v.cat.c,p.name));
  if(['filledMap','map'].includes(v.tipo))corpo.insertAdjacentHTML('beforeend','<div class="nota">mapa exibido como ranking</div>');}
function tudo(){ document.getElementById('limpar').style.display=Object.values(filtros).some(s=>s.size)?'block':'none';
  for(const v of VIS){try{desenhar(v,document.getElementById(v.id));}catch(e){document.getElementById(v.id).querySelector('.corpo').innerHTML='<div class="rot">'+e.message+'</div>';}}}
const pal=document.getElementById('pal');
for(const v of VIS){const d=document.createElement('div'); d.className='v'+(['card','cardVisual','kpi','multiRowCard'].includes(v.tipo)?' kpi':''); d.id=v.id;
  Object.assign(d.style,{left:v.x+'px',top:v.y+'px',width:v.w+'px',height:v.h+'px',padding:'10px 14px'}); d.innerHTML=`<h3>${v.titulo||''}</h3><div class="corpo"></div>`; pal.appendChild(d);}
function escala(){const s=Math.min(1,(window.innerWidth-16)/W); pal.style.transform=`scale(${s})`; document.body.style.height=(H*s+16)+'px'; Object.values(charts).forEach(c=>c.resize());}
window.addEventListener('resize',escala); escala(); tudo();
</script></body></html>"""


def main():
    if not a("--layout"):
        raise SystemExit(__doc__)
    spec = json.loads(Path(a("--layout")).read_text(encoding="utf-8"))
    pg = spec["paginas"][0]
    W, H = pg.get("largura", 1280), pg.get("altura", 720)
    tabs = {}
    fontes = [Path(p) for p in (sys.argv[sys.argv.index("--csv") + 1:] if "--csv" in sys.argv else [])]
    fontes = [p for p in fontes if not str(p).startswith("--")]
    if a("--dados"):
        d = Path(a("--dados"))
        fontes += sorted((d / "dados").glob("*.csv")) if (d / "dados").exists() else sorted(d.glob("*.csv"))
    for f in fontes:
        n, t = ler_tabela(f)
        tabs[n] = t
    meds = {}
    if a("--medidas"):
        for m in json.loads(Path(a("--medidas")).read_text(encoding="utf-8")):
            meds[m["nome"]] = {"js": m["js"], "tags": m.get("tags", [])}
    usados = set()
    vis = []
    for i, v in enumerate(pg["visuais"]):
        if v["tipo"] == "textbox":
            continue
        cs = [(c.split("=", 1)[0], campo(c.split("=", 1)[1])) for c in v.get("campos", [])]
        cat = next((f for papel, f in cs if papel in ("Category", "Group", "Rows") and f["k"] == "col"), None)
        vals = [f for papel, f in cs if not (cat is not None and f is cat)]
        if not vals and not cat:
            continue
        for f in ([cat] if cat else []) + vals:
            usados.add(f["t"])
        vis.append({"id": f"v{i}", "tipo": v["tipo"], "titulo": v.get("titulo"), "x": v["x"], "y": v["y"], "w": v["w"], "h": v["h"], "cat": cat, "vals": vals})
    faltam = usados - set(tabs)
    if faltam:
        raise SystemExit(f"tabelas sem CSV: {faltam}. CSVs lidos: {list(tabs)}")
    # estilo: mesmas cores do tema e o mesmo fundo SVG do Power BI
    from svg_fundo import paleta, gerar_svg
    escuro = "--escuro" in sys.argv
    c = paleta(a("--design"), escuro)
    from tema_pbi import tokens_de_design, ajustar_modo
    pal = None
    if a("--design"):
        t, _ = tokens_de_design(Path(a("--design")).read_text(encoding="utf-8"), Path(a("--design")).parent.name)
        t, _ = ajustar_modo(t, "escuro" if escuro else "claro")
        pal = t["colors"]["palette"]
    pal = pal or ["#2F6FDE", "#E8833A", "#2A9D8F", "#8E6CDF", "#D14B6B", "#7BA34A", "#C9A227", "#4F7CAC"]
    caixas = [dict(x=v["x"], y=v["y"], w=v["w"], h=v["h"], tipo=v["tipo"], id=v["id"]) for v in vis]  # layout = cartoes; visual fica dentro com respiro
    svg = gerar_svg(W, H, caixas, c, a("--estilo", "cartoes"), a("--titulo", pg.get("titulo") or pg["nome"]), a("--subtitulo"))
    so = {k: v for k, v in tabs.items() if k in usados}
    html = (HTML.replace("__TITULO__", a("--titulo", pg["nome"])).replace("__SVG__", svg).replace("__W__", str(W)).replace("__H__", str(H))
            .replace("__TEXTO__", c["texto"]).replace("__MUDO__", c["mudo"]).replace("__P__", c["p"]).replace("__BORDA__", c["borda"])
            .replace("__CARD__", c["card"]).replace("__FUNDO__", c["fundo"])
            .replace("__DADOS__", json.dumps(so, ensure_ascii=False, separators=(",", ":")))
            .replace("__VISUAIS__", json.dumps(vis, ensure_ascii=False)).replace("__MEDIDAS__", json.dumps(meds, ensure_ascii=False))
            .replace("__PALETA__", json.dumps(pal)))
    local = a("--echarts") or (str(AQUI.parent / "vendor" / "echarts.min.js") if "--offline" in sys.argv else None)
    if local:  # embute a biblioteca: funciona offline
        js = Path(local).read_text(encoding="utf-8")
        html = html.replace('<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>', "<script>" + js + "</script>")
    Path(a("--saida", "dashboard.html")).write_text(html, encoding="utf-8")
    print(f"{len(vis)} visuais, {sum(len(t['linhas']) for t in so.values())} linhas embutidas -> {a('--saida', 'dashboard.html')} ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()

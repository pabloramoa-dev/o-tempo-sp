# -*- coding: utf-8 -*-
"""
compor.py — transforma o pacote.json (roteiro + tempos + boca + palavras) no
index.html do HyperFrames do @otemposp.

Tudo aqui é determinístico: nada de Math.random, Date.now ou rede. As posições
"aleatórias" (nuvens, gotas, janelas dos prédios) saem de um gerador com semente
fixa em Python e entram no HTML já como números.

Camadas (de trás pra frente):
  1. CENAS (.scene)  — abertura -> número(s) -> quadro das cinco regiões ->
                       alerta -> frase -> cta, com glitch / whip-pan / flash
  2. OVERLAY FIXO    — HUD de telejornal, Bira ou Bia (SVG animado) atrás da
                       bancada, ticker, lower third, legenda karaokê e o card
                       "Seguir" (sub-composição compositions/instagram-follow)
  3. TEXTURA         — grão de filme e vinheta
"""
import html
import json
import random
import re

W, H = 1080, 1920
INK = "#122E43"       # azul-marinho do elenco RJ
NAVY2 = "#0b1a28"
TEAL = "#007F87"
RED = "#d63a2f"
YEL = "#FFD166"
OFF = "#f4f1e8"
PT = "#10202e"

TITULOS = {'rio_antes_de_sair': 'SÃO PAULO ANTES DE SAIR', 'chove_onde': 'O TEMPO MUDA ONDE?',
           'vai_dar_praia': 'VAI DAR PRAIA?', 'fim_de_semana': 'SEU FIM DE SEMANA',
           'vai_ao_jogo': 'VAI AO JOGO?', 'amanha_no_rio': 'AMANHÃ EM SÃO PAULO'}

CEUS = {  # topo, meio, morros, mar
    "sol": ("#2f8fd8", "#bfe6f7", "#3f7a5c", "#2f9bc0"),
    "calor": ("#f07a32", "#ffd9a0", "#5f7a4a", "#3a9fb8"),
    "nublado": ("#7f8e9c", "#d3dae0", "#56705f", "#6f98aa"),
    "chuva": ("#4c5a6b", "#8e9aa6", "#46604f", "#5d7d8c"),
    "tempestade": ("#232a38", "#5c6474", "#34463f", "#45606c"),
    "frio": ("#8fb1c9", "#e7eef3", "#5f8270", "#6aa6bd"),
}
MOUTH = {"X": 0.06, "A": 0.1, "B": 0.35, "C": 0.6, "D": 1.0, "E": 0.7,
         "F": 0.3, "G": 0.3, "H": 0.45}
APRESENTADOR = {
    'bira': {'nome': 'BIRA DO TEMPO', 'cargo': 'MANHÃ EM SÃO PAULO', 'pele': '#A96D49',
             'camisa': '#273F60', 'logo': '#ffffff', 'kicker': 'PREVISÃO DAS 6H'},
    'bia': {'nome': 'BIA', 'cargo': 'O TEMPO DE AMANHÃ EM SÃO PAULO', 'pele': '#C78359',
            'camisa': '#893E56', 'logo': '#ffffff', 'kicker': 'PREVISÃO DAS 18H'},
}


def esc(s):
    return html.escape(str(s), quote=True)


# ------------------------------------------------------- Bira / Bia (SVG) ---
def apresentador_svg(nome):
    """Bira do Tempo / Bia redesenhados em SVG a partir do rj_cast.py
    (Manim): 1 unidade = 150 px, cabeça centrada em (260, 230)."""
    c = APRESENTADOR[nome]
    bia = nome == 'bia'
    u, cx, cy = 150, 260, 230
    pele, camisa, cabelo = c['pele'], c['camisa'], '#392D32'
    sw = 8

    def X(x):
        return cx + u * x

    def Y(y):
        return cy - u * (y - 1.5)

    def rect(xc, yc, w, h, r, fill, extra=""):
        return (f'<rect x="{X(xc - w / 2):.1f}" y="{Y(yc + h / 2):.1f}" width="{u * w:.1f}" '
                f'height="{u * h:.1f}" rx="{u * r:.1f}" fill="{fill}" stroke="{INK}" '
                f'stroke-width="{sw}" {extra}/>')

    def circ(x, y, r, fill, extra=""):
        return (f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{u * r:.1f}" fill="{fill}" '
                f'stroke="{INK}" stroke-width="{sw}" {extra}/>')

    cabelo_tras = rect(0, 1.2, 1.95, 2.1, .65, cabelo) if bia else ''
    fios = [(-.57, 2.27, .34), (-.2, 2.42, .4), (.23, 2.41, .37), (.57, 2.22, .3)]
    if bia:
        fios.append((.85, 2.33, .45))
    cab = ''.join(circ(x, y, r, cabelo) for x, y, r in fios)
    if bia:
        cab += (f'<line x1="{X(.61):.1f}" y1="{Y(2.44):.1f}" x2="{X(.88):.1f}" y2="{Y(2.57):.1f}" '
                f'stroke="{TEAL}" stroke-width="14" stroke-linecap="round"/>')
    olhos = ''
    for x in (-.34, .34):
        olhos += (f'<ellipse cx="{X(x):.1f}" cy="{Y(1.55):.1f}" rx="{u * .175:.1f}" ry="{u * .215:.1f}" '
                  f'fill="#ffffff" stroke="{INK}" stroke-width="{sw}"/>')
    pupilas = ''.join(
        f'<g class="pupila"><circle cx="{X(x + .025):.1f}" cy="{Y(1.54):.1f}" r="{u * .085:.1f}" fill="{INK}"/>'
        f'<circle cx="{X(x + .05):.1f}" cy="{Y(1.58):.1f}" r="{u * .025:.1f}" fill="#ffffff"/></g>'
        for x in (-.34, .34))
    palp = ''.join(
        f'<ellipse cx="{X(x):.1f}" cy="{Y(1.55):.1f}" rx="{u * .19:.1f}" ry="{u * .23:.1f}" fill="{pele}"/>'
        f'<line x1="{X(x - .15):.1f}" y1="{Y(1.52):.1f}" x2="{X(x + .15):.1f}" y2="{Y(1.52):.1f}" '
        f'stroke="{INK}" stroke-width="7" stroke-linecap="round"/>' for x in (-.34, .34))
    sob = ''.join(
        f'<line id="ap-sob{lado}" x1="{X(x - .16):.1f}" y1="{Y(1.92):.1f}" x2="{X(x + .16):.1f}" '
        f'y2="{Y(1.95):.1f}" stroke="{INK}" stroke-width="12" stroke-linecap="round"/>'
        for lado, x in (('E', -.34), ('D', .34)))
    # braços: ombro -> mão (o direito da tela é o que aponta pro telão)
    braco = {}
    for lado, s in (('E', -1), ('D', 1)):
        ox, oy, mx, my = X(s * .62), Y(.18), X(s * 1.05), Y(-.73)
        braco[lado] = (f'<g id="ap-braco{lado}"><line x1="{ox:.1f}" y1="{oy:.1f}" x2="{mx:.1f}" y2="{my:.1f}" '
                       f'stroke="{INK}" stroke-width="44" stroke-linecap="round"/>'
                       f'<line x1="{ox:.1f}" y1="{oy:.1f}" x2="{mx:.1f}" y2="{my:.1f}" '
                       f'stroke="{camisa}" stroke-width="30" stroke-linecap="round"/>'
                       f'{circ(s * 1.05, -.73, .22, pele)}</g>')
    ombro_d = f'{X(.62):.1f} {Y(.18):.1f}'
    mx, my = X(0), Y(1.04)
    return f'''
<svg id="ap-svg" viewBox="0 0 520 700" width="520" height="700" style="overflow:visible" xmlns="http://www.w3.org/2000/svg" data-ombro="{ombro_d}" data-ombro-e="{X(-.62):.1f} {Y(.18):.1f}">
 <g id="ap-corpo">
  {cabelo_tras}
  {braco["E"]}
  {rect(0, -.38, 1.55, 1.65, .32, camisa)}
  <path d="M200 400 L260 510 L320 400 L294 394 L260 443 L226 394 Z" fill="#DCE7EF"/>
  <path d="M{X(-.26):.1f} {Y(.42):.1f} L{X(0):.1f} {Y(.12):.1f} L{X(.26):.1f} {Y(.42):.1f}" fill="none" stroke="{INK}" stroke-width="7" stroke-linejoin="round"/>
  <text x="{X(.36):.1f}" y="{Y(-.24):.1f}" text-anchor="middle" font-family="BarlowC" font-size="44" fill="{c["logo"]}">SP</text>
  {braco["D"]}
 </g>
 <g id="ap-cabeca">
  {rect(0, .55, .47, .58, .16, pele)}
  {circ(-.86, 1.45, .18, pele)}{circ(.86, 1.45, .18, pele)}
  {rect(0, 1.5, 1.72, 1.9, .67, pele)}
  {cab}
  {olhos}
  <g id="ap-pupilas">{pupilas}</g>
  <g id="ap-palp" opacity="0">{palp}</g>
  {sob}
  <path d="M{X(.01):.1f} {Y(1.42):.1f} Q{X(.16):.1f} {Y(1.32):.1f} {X(.13):.1f} {Y(1.22):.1f}" fill="none" stroke="#754A38" stroke-width="6" stroke-linecap="round"/>
  <path d="M{mx - 33:.1f} {my - 4:.1f} Q{mx:.1f} {my + 22:.1f} {mx + 33:.1f} {my - 4:.1f}" fill="none" stroke="{INK}" stroke-width="8" stroke-linecap="round"/>
  <g id="ap-boca" transform="translate({mx:.1f},{my + 4:.1f})">
   <g id="ap-boca-abre"><ellipse cx="0" cy="0" rx="32" ry="26" fill="#5b1f1f" stroke="{INK}" stroke-width="7"/>
    <ellipse cx="0" cy="12" rx="17" ry="8" fill="#c0504d"/></g>
  </g>
 </g>
</svg>'''


def nuvem_rj_svg(tam=220):
    """Mascote Nuvem RJ (rj_cast.nuvem) para o telão e o card."""
    return f'''<svg viewBox="-120 -90 240 170" width="{tam}" height="{tam * 170 / 240:.0f}" xmlns="http://www.w3.org/2000/svg">
 <g fill="#F4FAFD" stroke="{INK}" stroke-width="9" stroke-linejoin="round">
  <path d="M-100 20 A42 42 0 0 1 -60 -42 A57 57 0 0 1 48 -50 A43 43 0 0 1 98 6 A28 28 0 0 1 81 47 L-81 47 A28 28 0 0 1 -100 20 Z"/></g>
 <circle cx="-25" cy="-7" r="9" fill="{INK}"/><circle cx="25" cy="-7" r="9" fill="{INK}"/>
 <path d="M-17 14 Q0 30 17 14" fill="none" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>
</svg>'''


# ------------------------------------------------------------- cenário ---
def paisagem(ceu, uid, com_sol=True):
    """Telão com a paisagem do Rio: Corcovado, Pão de Açúcar com o bondinho,
    prédios da orla, o mar e o calçadão de ondas. O céu é o tempo do dia."""
    topo, meio, morro, mar = CEUS.get(ceu, CEUS["sol"])
    rng = random.Random(sum(map(ord, uid)) * 7 + 11)
    ncl = {"sol": 3, "calor": 2, "nublado": 6, "chuva": 7, "tempestade": 7, "frio": 4}.get(ceu, 3)
    cor_n = {"chuva": "#b7c1cb", "tempestade": "#6d7686", "nublado": "#eef1f4"}.get(ceu, "#ffffff")
    nuvens = []
    for _ in range(ncl):
        x, y, s = rng.randint(-80, 900), rng.randint(230, 560), rng.uniform(0.8, 1.5)
        nuvens.append(
            f'<g class="{uid}-nuvem" data-dx="{rng.choice([-1, 1]) * rng.randint(40, 90)}" '
            f'transform="translate({x},{y}) scale({s:.2f})">'
            f'<ellipse cx="60" cy="40" rx="60" ry="34" fill="{cor_n}"/>'
            f'<ellipse cx="120" cy="30" rx="56" ry="42" fill="{cor_n}"/>'
            f'<ellipse cx="170" cy="46" rx="44" ry="28" fill="{cor_n}"/>'
            f'<rect x="20" y="44" width="190" height="30" rx="15" fill="{cor_n}"/></g>')
    sol = ""
    if com_sol and ceu in ("sol", "calor", "frio"):
        raios = "".join(f'<rect x="-8" y="-190" width="16" height="54" rx="8" fill="#ffd34e" '
                        f'transform="rotate({a})"/>' for a in range(0, 360, 30))
        sol = (f'<g transform="translate(850,400)"><g class="{uid}-raios">{raios}</g>'
               f'<circle r="118" fill="#ffd34e" stroke="#e8a93a" stroke-width="8"/></g>')
    chuva = ""
    if ceu in ("chuva", "tempestade"):
        linhas = []
        for _ in range(70):
            x, y = rng.randint(-100, 1100), rng.randint(0, 1500)
            linhas.append(f'<line x1="{x}" y1="{y}" x2="{x - 14}" y2="{y + 52}" stroke="#dbe9f5" '
                          f'stroke-width="4" stroke-linecap="round" opacity="0.75"/>')
        chuva = f'<g class="{uid}-chuva">{"".join(linhas)}</g>'
    predios = []
    x = -10
    while x < 1090:
        w, h = rng.randint(60, 110), rng.randint(90, 230)
        cor = rng.choice(["#e9e2d3", "#d9d3c4", "#f2ede2", "#cfd6d8"])
        jan = "".join(f'<rect x="{x + 12 + j * 22}" y="{1290 - h + 16 + k * 30}" width="12" height="16" fill="#8fa9b8"/>'
                      for k in range(max(1, h // 30 - 1)) for j in range(max(1, (w - 16) // 22)))
        predios.append(f'<rect x="{x}" y="{1290 - h}" width="{w}" height="{h + 30}" fill="{cor}" stroke="{PT}" stroke-width="4"/>{jan}')
        x += w + rng.randint(-4, 6)
    onda = "M0 1395 " + " ".join(f"Q{45 + 90 * k} {1375 if k % 2 == 0 else 1415} {90 + 90 * k} 1395" for k in range(13))
    return f'''
<svg class="paisagem" viewBox="0 0 1080 1920" width="1080" height="1920" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
 <defs><linearGradient id="{uid}-g" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{topo}"/><stop offset="0.6" stop-color="{meio}"/></linearGradient></defs>
 <rect width="1080" height="1920" fill="url(#{uid}-g)"/>
 {sol}
 {"".join(nuvens)}
 {"".join(predios)}
 <rect y="1285" width="1080" height="635" fill="#4b6174"/>
 <g stroke="#122E43" stroke-width="5">
 <path d="M52 1130h335v92H52z" fill="#93adbb"/>
 <path d="M47 1285v-184h16v184 M368 1285v-184h16v184" fill="#dc4546"/>
 <path d="M44 1096h345v16H44z" fill="#d84043"/>
 </g>
 <g stroke="#e2e1cf" fill="none">
 <path d="M660 1300L810 902L875 1300 M855 1300L810 902L675 1300" stroke-width="13"/>
 {"".join(f'<path d="M810 {915+i*10}L{510+i*20} 1240 M810 {915+i*10}L{1060-i*14} 1240" stroke-width="3"/>' for i in range(12))}
 <path d="M490 1240h590" stroke-width="12"/>
 </g>
 {chuva}
</svg>'''


# --------------------------------------------------------------- cenas ---
def _scene(cena, p, bg, miolo):
    return (f'<div id="{cena["id"]}" class="scene clip" data-start="0" data-duration="{p["dur"]}" '
            f'data-track-index="1" style="background-color:{bg}">{miolo}</div>')


def _lugar(b):
    """Carimbo do número: o lugar citado na fala (dado do roteiro, nunca inventado)."""
    leg = b["legenda"]
    m = re.search(r"separam (.+?) de (.+?)[.]", leg)
    if m:
        return f"{m.group(1)} × {m.group(2)}"
    m = re.search(r"\b(?:na|no|em|nos|nas|Na|No|Em|Nos|Nas) ([A-ZÁÉÍÓÚÂÊÔ][\wÀ-ú' ]+?)(?:[,.]|$)", leg)
    return m.group(1) if m else ""


def cena_abertura(p, cena, bat):
    titulo = TITULOS.get(p["formato"], "O TEMPO SP")
    palavras = "".join(f'<span class="ab-w">{esc(w)}</span> ' for w in titulo.split())
    quando = "AMANHÃ" if p["formato"] == "amanha_no_rio" else "HOJE"
    from datetime import date
    d = date.fromisoformat(p["data_previsao"])
    meses = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
    miolo = f'''{paisagem(p["ceu"], "ab")}
 <div class="ab-kicker"><span class="tag tag-red">{esc("PREVISÃO DAS " + str(int(p["hora"].split(":")[0])) + "H")}</span>
  <span class="tag tag-yel">{quando} · {d.day:02d} {meses[d.month - 1]}</span></div>
 <div class="ab-placa"></div>
 <div class="ab-titulo" data-layout-allow-overlap="true">{palavras}</div>
 <div class="ab-mascote">{nuvem_rj_svg(240)}</div>'''
    return _scene(cena, p, CEUS.get(p["ceu"], CEUS["sol"])[0], miolo)


def cena_numero(p, cena, bat):
    b = bat[cena["batidas"][0]]
    d = b["dados"]
    num = str(d.get("numero", ""))
    digitos = "".join(ch for ch in num if ch.isdigit() or ch in ",.")
    sufixo = num[len(digitos):] if num.startswith(digitos) else ""
    chuva = "%" in sufixo or "CHUVA" in d.get("sub", "").upper()
    sid = cena["id"]
    if chuva:
        icone = ('<svg viewBox="-150 -150 300 300" width="250" height="250"><g>'
                 '<ellipse cx="-40" cy="-20" rx="80" ry="56" fill="#dfe6ee" stroke="#10202e" stroke-width="8"/>'
                 '<ellipse cx="40" cy="-34" rx="74" ry="64" fill="#dfe6ee" stroke="#10202e" stroke-width="8"/>'
                 '<rect x="-110" y="-10" width="220" height="56" rx="28" fill="#dfe6ee"/></g>'
                 f'<g class="nu-gotas">' + "".join(
                     f'<line x1="{x}" y1="70" x2="{x - 10}" y2="112" stroke="#8fd0ff" stroke-width="12" stroke-linecap="round"/>'
                     for x in (-70, -25, 20, 65)) + '</g></svg>')
        bg = "#2b3a4f"
    else:
        icone = ('<svg viewBox="-150 -150 300 300" width="250" height="250"><g class="nu-raios">'
                 + "".join(f'<rect x="-9" y="-140" width="18" height="46" rx="9" fill="#ffd34e" transform="rotate({a})"/>'
                           for a in range(0, 360, 30))
                 + '</g><circle r="86" fill="#ffd34e" stroke="#e8a93a" stroke-width="8"/>'
                 '<rect x="-16" y="-60" width="32" height="96" rx="16" fill="#ffffff" stroke="#10202e" stroke-width="7"/>'
                 '<circle cx="0" cy="44" r="28" fill="#d63a2f" stroke="#10202e" stroke-width="7"/>'
                 '<rect x="-7" y="-20" width="14" height="60" fill="#d63a2f"/></svg>')
        bg = "#1f6fb0"
    lugar = d.get("local") or _lugar(b)
    carimbo = (f'<div class="nu-carimbo" data-layout-allow-overlap="true"><span>{esc(lugar.upper())}</span></div>'
               if lugar else "")
    miolo = f'''{paisagem(p["ceu"], "n" + sid, com_sol=False)}
 <div class="nu-veu"></div>
 <div class="nu-icone">{icone}</div>
 <div class="nu-rot" data-layout-allow-overlap="true">{esc(d.get("sub", ""))}</div>
 <div class="nu-val"><span class="nu-dig" data-alvo="{esc(digitos or 0)}">{esc(digitos or num)}</span><span class="nu-suf">{esc(sufixo)}</span></div>
 {carimbo}'''
    return _scene(cena, p, bg, miolo)


def cena_quadro(p, cena, bat):
    res = bat[cena["batidas"][0]]
    cidades = res["dados"]["cidades"]
    import math
    def metric(c, key, unit, decimals=0):
        v = c.get(key)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            return "—"
        return f"{v:.{decimals}f}".replace(".", ",") + unit
    linhas = []
    compacto = len(cidades) > 4
    for c in cidades:
        nome = c["nome"].upper()
        fonte = 35 if compacto else (42 if len(nome) <= 19 else 37)
        linhas.append(f'''
  <div class="qd-linha" data-cidade="{esc(c["nome"])}">
   <div class="qd-barra"></div>
   <div class="qd-main"><div class="qd-cidade" style="font-size:{fonte}px">{esc(nome)}</div>
   <div class="qd-chuva">VOLUME <b>{metric(c, "chuva_mm", " mm", decimals=1)}</b></div>
   <div class="qd-cels"><span class="qd-min">{metric(c, "min", "°")}</span><span class="qd-max">{metric(c, "max", "°")}</span></div></div>
  </div>''')
    miolo = f'''{paisagem(p["ceu"], "qd" + cena["id"])}
 <div class="qd-veu"></div>
 <div class="qd-topo"><span class="qd-check">✓</span><span class="qd-titulo">{esc(res["dados"].get("titulo", "NA REGIÃO"))}</span></div>
 <div class="qd-painel{" qd-compacto" if compacto else ""}">
  <div class="qd-head"><span>POR SETOR</span><span class="qd-chuva-titulo">CHUVA</span><span class="qd-cols"><b>MÍN</b><b>MÁX</b></span></div>
  {"".join(linhas)}
  <div class="qd-dicas" data-qa-bounds="true">{esc(" · ".join(p.get("dicas_praticas", [])))}</div>
 </div>'''
    return _scene(cena, p, NAVY2, miolo)


def cena_alerta(p, cena, bat):
    b = bat[cena["batidas"][0]]
    d = b["dados"]
    miolo = f'''<div class="al-fundo"></div>
 <div class="al-icone"><svg viewBox="-130 -120 260 230" width="240" height="212"><path d="M0 -105 L118 98 L-118 98 Z" fill="{YEL}" stroke="{PT}" stroke-width="12" stroke-linejoin="round"/>
  <rect x="-13" y="-48" width="26" height="92" rx="10" fill="{PT}"/><circle cx="0" cy="70" r="15" fill="{PT}"/></svg></div>
 <div class="al-titulo">{esc(d.get("titulo", "ATENÇÃO").upper())}</div>
 <div class="al-det"><span>{esc(d.get("detalhe", ""))}</span></div>
 <div class="al-carimbo" data-layout-allow-overlap="true"><span>ATENÇÃO</span></div>'''
    return _scene(cena, p, RED, miolo)


def _tam_frase(txt):
    n = len(txt)
    return 104 if n <= 40 else 86 if n <= 70 else 70 if n <= 110 else 58


def cena_frase(p, cena, bat):
    blocos = "".join(
        f'<div class="fr-texto" data-b="{i}" style="font-size:{_tam_frase(bat[i]["legenda"])}px">'
        f'{esc(bat[i]["legenda"].upper())}</div>' for i in cena["batidas"])
    miolo = f'''{paisagem(p["ceu"], "f" + cena["id"])}
 <div class="qd-veu"></div>
 {blocos}'''
    return _scene(cena, p, INK, miolo)


def cena_cta(p, cena, bat):
    b = bat[cena["batidas"][0]]
    d = b["dados"]
    chamada = d.get("chamada") or b["legenda"].split(".")[0].strip().upper()
    miolo = f'''<div class="cta-fundo"></div>
 <div class="cta-bloco" id="cta-b1">
  <div class="cta-mascote">{nuvem_rj_svg(230)}</div>
  <div class="cta-chamada" style="font-size:{100 if len(chamada) <= 26 else 82}px">{esc(chamada)}</div>
  <div class="cta-sub">{esc(d.get("sub", "Previsão todo dia às 6h e às 18h"))}</div>
 </div>'''
    return _scene(cena, p, TEAL, miolo)


FAB = {"abertura": cena_abertura, "numero": cena_numero, "quadro": cena_quadro,
       "alerta": cena_alerta, "frase": cena_frase, "cta": cena_cta}


# ------------------------------------------------------------ overlay ---
def ticker(p):
    itens = " &#9679; ".join(
        f'{esc(c["nome"].upper())} <b>{round(c["min"])}°/{round(c["max"])}°</b>' for c in p["cidades"])
    itens += " &#9679; SIGA @OTEMPOSP"
    return (f'<div class="tk-faixa"><div class="tk-rot">SP</div><div class="tk-janela">'
            f'<div id="tk-trilho">{itens} &#9679; {itens}</div></div></div>')


def legenda_html(p):
    """Páginas de até 4 palavras por batida. O quadro das cinco regiões já
    mostra tudo que é falado nele, então ali a legenda sai de cena."""
    paginas = []
    for bi, b in enumerate(p["batidas"]):
        if b["tipo"] == "resumo":
            continue
        pag = []
        for w in (w for w in p["palavras"] if w["b"] == bi):
            pag.append(w)
            if len(pag) == 4 or w["w"][-1] in ".!?":
                paginas.append(pag)
                pag = []
        if pag:
            paginas.append(pag)
    out = []
    for k, pg in enumerate(paginas):
        palavras = "".join(
            f'<span class="lg-w" data-s="{w["s"]}" data-e="{w["e"]}"><span class="lg-bg"></span>'
            f'<span class="lg-t">{esc(w["w"].upper())}</span></span>' for w in pg)
        out.append(f'<div class="lg-pag" id="lg-p{k}" data-s="{pg[0]["s"]}" data-e="{pg[-1]["e"]}">{palavras}</div>')
    return "".join(out)


# ------------------------------------------------------------- página ---
def compor(p):
    dur = p["dur"]
    bat = p["batidas"]
    cenas = p["cenas"]
    ap = APRESENTADOR[p["personagem"]]
    y, m, d = p["data"].split("-")
    dia_capa = "HOJE" if p["personagem"] == "bira" else "AMANHÃ"
    minima_capa = round(min(c["min"] for c in p["cidades"]))
    maxima_capa = round(max(c["max"] for c in p["cidades"]))
    data_curta = f'{p["data_ext"].split(",")[0][:3]} {d}/{m}'
    cenas_html = "".join(FAB[c["tipo"]](p, c, bat) for c in cenas)
    # O botão de seguir deve aparecer no CTA, mesmo quando uma cena
    # meteorológica (chuva) encerrar o vídeo depois dele.
    cta_index = next((i for i, c in enumerate(cenas) if c["tipo"] == "cta"), None)
    if cta_index is not None:
        cta = cenas[cta_index]
        cta_fim = cenas[cta_index + 1]["ini"] if cta_index + 1 < len(cenas) else dur
        t_siga = min(cta["ini"] + 0.9, cta_fim - 0.4)
        t_siga = round(max(0, t_siga), 2)
        dur_follow = round(max(0.3, cta_fim - t_siga - (0.08 if cta_index + 1 < len(cenas) else 0)), 2)
    else:
        t_siga = round(max(0.5, dur - 2.6), 2)
        dur_follow = round(dur - t_siga, 2)

    dados_js = json.dumps({
        "dur": dur,
        "cenas": [{"id": c["id"], "tipo": c["tipo"], "ini": c["ini"],
                   "fim": (cenas[k + 1]["ini"] if k + 1 < len(cenas) else dur),
                   "batidas": [{"i": i, "ini": bat[i]["ini"], "fim": bat[i]["fim"]} for i in c["batidas"]]}
                  for k, c in enumerate(cenas)],
        "batidas": [{"tipo": b["tipo"], "ini": b["ini"], "fim": b["fim"]} for b in bat],
        "direcao": p.get("direcao", []),
        "boca": [[t, MOUTH.get(v, 0.3)] for t, v in p["boca"]],
        "palavras": [[w["s"], w["e"], w["w"]] for w in p["palavras"]],
        "tSiga": t_siga,
    }, ensure_ascii=False)
    transicoes = [{"time": c, "shader": s, "duration": 0.45}
                  for c, s in zip(p["cortes"], p["transicoes"])]

    return f'''<!doctype html>
<html lang="pt-BR" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>{esc(ap["nome"].title())} — O TEMPO SP — HyperFrames</title>
<script src="assets/vendor/gsap.min.js"></script>
<style>
@font-face {{ font-family: "BarlowC"; src: url("assets/fonts/BarlowCondensed-ExtraBold.woff2") format("woff2"); font-weight: 800; }}
@font-face {{ font-family: "BarlowCB"; src: url("assets/fonts/BarlowCondensed-Bold.woff2") format("woff2"); font-weight: 700; }}
@font-face {{ font-family: "Poppins"; src: url("assets/fonts/Poppins-Regular.ttf") format("truetype"); font-weight: 400; }}
@font-face {{ font-family: "Poppins"; src: url("assets/fonts/Poppins-Bold.ttf") format("truetype"); font-weight: 700; }}
@font-face {{ font-family: "Poppins"; src: url("assets/fonts/Poppins-ExtraBold.ttf") format("truetype"); font-weight: 800; }}
@font-face {{ font-family: "Poppins"; src: url("assets/fonts/Poppins-Black.ttf") format("truetype"); font-weight: 900; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: {NAVY2}; }}
#root {{ position: relative; width: 100%; height: 100%; overflow: hidden; font-family: "Poppins", sans-serif; color: #ffffff; }}
#palco {{ position: absolute; inset: 0; overflow: hidden; }}
.scene {{ position: absolute; inset: 0; overflow: hidden; }}
.paisagem {{ position: absolute; inset: 0; }}
/* ---------- abertura ---------- */
.ab-kicker {{ position: absolute; top: 262px; left: 0; right: 0; display: flex; justify-content: center; gap: 18px; }}
.tag {{ display: block; font-family: "BarlowC", sans-serif; font-size: 50px; letter-spacing: 2px; padding: 6px 22px 4px; border: 5px solid {PT}; }}
.tag-red {{ background-color: {RED}; color: #ffffff; }}
.tag-yel {{ background-color: {YEL}; color: {PT}; }}
.ab-placa {{ position: absolute; top: 360px; left: 70px; right: 70px; height: 470px; background-color: rgba(18,46,67,0.86); border: 6px solid {PT}; border-radius: 36px; box-shadow: 0 14px 0 {PT}; }}
.ab-titulo {{ position: absolute; top: 400px; left: 100px; right: 100px; height: 300px; display: flex; flex-wrap: wrap; justify-content: center; align-content: center; gap: 0 26px; font-family: "BarlowC", sans-serif; font-size: 156px; line-height: 0.98; color: #ffffff; text-shadow: 0 10px 0 {PT}; }}
.ab-w {{ display: block; }}
.ab-w:last-child {{ color: {YEL}; }}
.ab-mascote {{ position: absolute; top: 690px; left: 0; right: 0; display: flex; justify-content: center; }}
/* ---------- capa para a grade: visível no primeiro frame ---------- */
#cover-card {{ position:absolute;inset:0;z-index:348;pointer-events:none;
  background:linear-gradient(180deg,rgba(9,27,47,.91) 0%,rgba(18,49,76,.9) 53%,rgba(10,30,48,.30) 100%); }}
.cover-kicker {{ position:absolute;top:275px;left:72px;right:72px;display:flex;align-items:center;justify-content:center;
  font-family:"BarlowC",sans-serif;font-size:58px;letter-spacing:3px;color:{YEL}; }}
.cover-title {{ position:absolute;top:390px;left:58px;right:58px;text-align:center;
  font-family:"BarlowC",sans-serif;font-size:156px;line-height:.94;color:#fff;text-shadow:0 9px 0 {PT}; }}
.cover-day {{ position:absolute;top:858px;left:124px;right:124px;background:{YEL};color:{PT};
  border:6px solid {PT};border-radius:22px;text-align:center;font-family:"BarlowC",sans-serif;font-size:86px; }}
.cover-temps {{ position:absolute;top:1038px;left:85px;right:85px;display:flex;justify-content:center;
  gap:28px;font-family:"BarlowCB",sans-serif;font-size:62px;text-shadow:0 5px 0 {PT}; }}
.cover-temps span {{ background:rgba(9,27,47,.85);border:4px solid #a9dfff;border-radius:20px;padding:16px 23px; }}
.cover-temps strong {{ color:{YEL}; }}
.cover-footer {{ position:absolute;top:1250px;right:70px;background:{INK};padding:8px 24px;border-radius:16px;
  font-family:"BarlowCB",sans-serif;font-size:46px;color:#fff; }}
/* ---------- número ---------- */
.nu-veu {{ position: absolute; inset: 0; background-color: rgba(11,26,40,0.55); }}
.nu-icone {{ position: absolute; top: 255px; left: 0; right: 0; display: flex; justify-content: center; }}
.nu-rot {{ position: absolute; top: 505px; left: 40px; right: 40px; text-align: center; font-family: "BarlowCB", sans-serif; font-size: 54px; letter-spacing: 4px; color: {YEL}; text-shadow: 0 4px 0 {PT}; }}
.nu-val {{ position: absolute; top: 545px; left: 0; right: 0; text-align: center; font-family: "BarlowC", sans-serif; font-size: 230px; line-height: 1; color: #ffffff; text-shadow: 0 12px 0 {PT}, 8px 8px 0 {PT}; }}
.nu-suf {{ font-size: 150px; margin-left: 6px; }}
.nu-carimbo {{ position: absolute; top: 790px; left: 40px; right: 40px; display: flex; justify-content: center; }}
.nu-carimbo span {{ display: block; font-family: "BarlowC", sans-serif; font-size: 62px; color: #ffffff; background-color: {TEAL}; padding: 6px 30px 2px; border: 7px solid {PT}; border-radius: 14px; box-shadow: 0 10px 0 {PT}; white-space: nowrap; }}
/* ---------- quadro (split-flap) ---------- */
.qd-veu {{ position: absolute; inset: 0; background-color: rgba(11,26,40,0.72); }}
.qd-topo {{ position: absolute; top: 255px; left: 60px; right: 60px; display: flex; align-items: center; justify-content: center; gap: 18px; }}
.qd-check {{ display: flex; align-items: center; justify-content: center; width: 70px; height: 70px; border-radius: 35px; background-color: {TEAL}; border: 5px solid {PT}; font-size: 44px; font-weight: 900; color: #ffffff; }}
.qd-titulo {{ font-family: "BarlowC", sans-serif; font-size: 66px; color: #ffffff; text-shadow: 0 5px 0 {PT}; }}
.qd-painel {{ position: absolute; top: 350px; left: 44px; right: 44px; padding: 20px 28px 22px; background-color: #0e1d2c; border: 6px solid {PT}; border-radius: 26px; box-shadow: 0 16px 0 {PT}; }}
.qd-head {{ position:relative; display:flex;align-items:center; padding-left:22px; font-family:"BarlowCB",sans-serif; font-size:36px;color:{YEL};letter-spacing:3px;margin-bottom:8px;min-height:45px; }}
.qd-chuva-titulo {{ position:absolute;left:50%;transform:translateX(-50%);white-space:nowrap;text-align:center; }}
.qd-cols {{ margin-left:auto;display:grid;grid-template-columns:1fr 1fr;gap:8px;width:190px;letter-spacing:0;text-align:center; }}
.qd-cols b {{ font-weight: 700; }}
.qd-linha {{ position: relative; min-height: 92px; height: auto; padding: 8px 0 8px 22px; border-top: 3px solid #22364a; }}
.qd-barra {{ position:absolute;left:0;top:14px;width:8px;height:76px;background:{YEL};border-radius:5px; }}
.qd-main {{ position:relative;display:flex;align-items:center;min-height:68px;height:auto;gap:8px; }}
.qd-cidade {{ font-family:"BarlowC",sans-serif;font-size:42px;line-height:1.03;color:white;white-space:normal;overflow-wrap:break-word;flex:0 1 30%;min-width:0; }}
/* O volume ocupa posição fixa no centro; nunca acompanha a animação de destaque. */
.qd-chuva {{ position:absolute;left:50%;transform:translateX(-50%);width:300px;text-align:center;white-space:nowrap;font-family:"BarlowC",sans-serif;font-size:42px;color:#ffffff;line-height:1.1; }}
.qd-chuva b {{ font-size:42px;color:#ffffff;font-weight:800; }}
.qd-cels {{ display:grid;grid-template-columns:1fr 1fr;flex-shrink:0;gap:8px;width:190px;margin-left:auto;font-family:"BarlowC",sans-serif;font-size:44px; }}
.qd-cels span {{ width:auto;text-align:center; }}
.qd-min {{ color:#9fd8ff; }}
.qd-max {{ color:{YEL}; }}
/* Painel compacto quando um mesmo agrupamento contém 5 a 8 cidades. */
.qd-compacto {{ padding:12px 24px 16px; }}
.qd-compacto .qd-head {{ font-size:30px; margin-bottom:4px; }}
.qd-compacto .qd-linha {{ min-height:62px; padding:2px 0 2px 16px; border-top-width:2px; }}
.qd-compacto .qd-main {{ min-height:54px; }}
.qd-compacto .qd-cols,.qd-compacto .qd-cels {{ width:160px; }}
.qd-compacto .qd-chuva {{ font-size:34px;width:270px; }}
.qd-compacto .qd-chuva b {{ font-size:34px; }}
.qd-compacto .qd-cidade {{ font-size:35px !important; }}
.qd-compacto .qd-cels {{ font-size:37px; }}
.qd-compacto .qd-cels span {{ width:72px; }}
.qd-compacto .qd-barra {{ top:5px; height:49px; }}
.qd-compacto .qd-dicas {{ font-size:22px; margin-top:4px; }}
.qd-metrics {{ display:flex;justify-content:space-between;gap:10px;font-family:"BarlowCB",sans-serif;font-size:30px;color:#b9ccdd;line-height:30px; }}
.qd-metrics b {{ color:white;font-weight:700; }}
.qd-dicas {{ font-family:"BarlowCB",sans-serif;font-size:26px;color:{YEL};margin-top:12px;text-align:center;line-height:1.25; }}
/* ---------- alerta ---------- */
.al-fundo {{ position: absolute; inset: 0; background-color: {RED}; background-image: repeating-linear-gradient(135deg, rgba(0,0,0,0.18) 0 44px, rgba(0,0,0,0) 44px 88px); }}
.al-icone {{ position: absolute; top: 250px; left: 0; right: 0; display: flex; justify-content: center; }}
.al-titulo {{ position: absolute; top: 470px; left: 50px; right: 50px; text-align: center; font-family: "BarlowC", sans-serif; font-size: 136px; line-height: 1; color: #ffffff; text-shadow: 0 10px 0 {PT}; }}
.al-det {{ position: absolute; top: 625px; left: 40px; right: 40px; display: flex; justify-content: center; }}
.al-det span {{ display: block; font-family: "BarlowCB", sans-serif; font-size: 56px; color: {PT}; background-color: #ffffff; border: 6px solid {PT}; border-radius: 16px; padding: 4px 26px 0; text-align: center; }}
.al-carimbo {{ position: absolute; top: 770px; left: 0; right: 0; display: flex; justify-content: center; }}
.al-carimbo span {{ display: block; font-family: "BarlowC", sans-serif; font-size: 70px; color: {PT}; background-color: {YEL}; padding: 4px 34px 0; border: 7px solid {PT}; border-radius: 14px; box-shadow: 0 10px 0 {PT}; }}
/* ---------- frase ---------- */
.fr-texto {{ position: absolute; top: 300px; left: 70px; right: 70px; height: 560px; display: flex; align-items: center; justify-content: center; text-align: center; font-family: "BarlowC", sans-serif; line-height: 1.05; color: #ffffff; text-shadow: 0 8px 0 {PT}; opacity: 0; }}
/* ---------- cta ---------- */
.cta-fundo {{ position: absolute; inset: 0; background-color: {TEAL}; background-image: repeating-linear-gradient(135deg, rgba(0,0,0,0.14) 0 40px, rgba(0,0,0,0) 40px 80px); }}
.cta-bloco {{ position: absolute; top: 250px; left: 60px; right: 60px; display: flex; flex-direction: column; align-items: center; }}
.cta-chamada {{ margin-top: 6px; font-family: "BarlowC", sans-serif; line-height: 1; text-align: center; color: #ffffff; text-shadow: 0 8px 0 {PT}; }}
.cta-sub {{ margin-top: 18px; font-size: 40px; font-weight: 800; text-align: center; color: {YEL}; text-shadow: 0 3px 0 {PT}; }}
/* ---------- overlay fixo ---------- */
#hud {{ position: absolute; top: 150px; left: 36px; right: 36px; height: 84px; display: flex; align-items: center; gap: 16px; z-index: 300; }}
.hud-vivo {{ display: flex; align-items: center; gap: 12px; background-color: {RED}; border: 5px solid {PT}; border-radius: 12px; padding: 4px 18px 2px; font-family: "BarlowC", sans-serif; font-size: 44px; color: #ffffff; }}
.hud-ponto {{ width: 20px; height: 20px; border-radius: 10px; background-color: #ffffff; }}
.hud-nome {{ flex: 1; font-family: "BarlowC", sans-serif; font-size: 42px; color: #ffffff; background-color: {INK}; border: 5px solid {PT}; border-radius: 12px; padding: 4px 18px 2px; white-space: nowrap; }}
.hud-rel {{ font-family: "BarlowC", sans-serif; font-size: 44px; color: {PT}; background-color: {YEL}; border: 5px solid {PT}; border-radius: 12px; padding: 4px 16px 2px; }}
#ap-wrap {{ position: absolute; left: -10px; top: 1010px; width: 520px; height: 700px; z-index: 310; }}
#bancada {{ position: absolute; left: 0; right: 0; top: 1520px; bottom: 0; z-index: 320; background-color: {INK}; border-top: 8px solid {PT}; }}
.bc-faixa {{ position: absolute; top: 0; left: 0; right: 0; height: 18px; background-color: {TEAL}; }}
.tk-faixa {{ position: absolute; top: 36px; left: 0; right: 0; height: 78px; display: flex; background-color: #ffffff; border-top: 5px solid {PT}; border-bottom: 5px solid {PT}; }}
.tk-rot {{ flex: 0 0 auto; display: flex; align-items: center; padding: 0 22px; background-color: {RED}; color: #ffffff; font-family: "BarlowC", sans-serif; font-size: 42px; border-right: 5px solid {PT}; }}
.tk-janela {{ position: relative; flex: 1; overflow: hidden; }}
#tk-trilho {{ position: absolute; left: 0; top: 0; height: 68px; line-height: 70px; white-space: nowrap; font-family: "BarlowCB", sans-serif; font-size: 42px; color: {PT}; }}
#tk-trilho b {{ color: {TEAL}; }}
#lt {{ position: absolute; left: 480px; top: 1330px; z-index: 330; }}
.lt-nome {{ display: block; background-color: #ffffff; color: {PT}; font-family: "BarlowC", sans-serif; font-size: 64px; padding: 4px 20px 0; box-shadow: 10px 10px 0 {TEAL}; white-space: nowrap; }}
.lt-cargo {{ display: block; margin-top: 16px; background-color: {PT}; color: {YEL}; font-family: "BarlowCB", sans-serif; font-size: 32px; padding: 4px 18px 2px; width: fit-content; white-space: nowrap; }}
#legenda {{ position: absolute; left: 40px; right: 40px; top: 890px; height: 150px; z-index: 340; }}
.lg-pag {{ position: absolute; inset: 0; display: flex; flex-wrap: wrap; justify-content: center; align-content: center; gap: 6px 14px; opacity: 0; }}
.lg-w {{ position: relative; display: block; padding: 2px 14px 0; background-color: rgba(11,26,40,0.82); border-radius: 12px; }}
.lg-bg {{ position: absolute; inset: 0; border-radius: 10px; background-color: {TEAL}; border: 4px solid {PT}; transform: scaleX(0); transform-origin: 0% 50%; }}
.lg-t {{ position: relative; display: block; font-family: "Poppins", sans-serif; font-weight: 900; font-size: 58px; line-height: 1.15; color: #ffffff; -webkit-text-stroke: 5px {PT}; paint-order: stroke fill; text-shadow: 0 5px 0 {PT}; }}
#follow-slot {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; z-index: 350; }}
#grao {{ position: absolute; inset: -40px; z-index: 900; pointer-events: none; opacity: 0.07;
  background-image: repeating-radial-gradient(circle at 17% 32%, rgba(255,255,255,0.9) 0 1px, rgba(255,255,255,0) 1px 3px), repeating-radial-gradient(circle at 73% 61%, rgba(0,0,0,0.9) 0 1px, rgba(0,0,0,0) 1px 4px); }}
#vinheta {{ position: absolute; inset: 0; z-index: 910; pointer-events: none; background: radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.42) 100%); }}
#glitch {{ position: absolute; inset: 0; z-index: 915; opacity: 0; pointer-events: none; mix-blend-mode: screen; background-image: repeating-linear-gradient(0deg, rgba(255,0,60,0.55) 0 14px, rgba(0,0,0,0) 14px 46px, rgba(0,220,255,0.5) 46px 58px, rgba(0,0,0,0) 58px 120px); }}
#flash {{ position: absolute; inset: 0; z-index: 920; background-color: #ffffff; opacity: 0; pointer-events: none; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{dur}" data-width="{W}" data-height="{H}">

 <div id="palco">{cenas_html}</div>
 <div id="cover-card" class="clip" data-start="0" data-duration="1.5" data-track-index="12">
  <div class="cover-kicker">O TEMPO SP</div>
  <div class="cover-title">PREVISÃO<br>DO TEMPO<br>SÃO PAULO</div>
  <div class="cover-day">{esc(dia_capa)} · {d}/{m}</div>
  <div class="cover-temps"><span>MÍN <strong>{minima_capa}°</strong></span><span>MÁX <strong>{maxima_capa}°</strong></span></div>
  <div class="cover-footer">8 REGIÕES · @OTEMPOSP</div>
 </div>

 <div id="hud" class="clip" data-start="0" data-duration="{dur}" data-track-index="2">
  <div class="hud-vivo"><span class="hud-ponto" id="hud-ponto"></span>{("PILOTO" if p["demo"] else "PREVISÃO")}</div>
  <div class="hud-nome">O TEMPO SP · {("SIMULAÇÃO" if p["demo"] else esc(data_curta))}</div>
  <div class="hud-rel">{esc(p["hora"])}</div>
 </div>

 <div id="ap-wrap" class="clip" data-start="0" data-duration="{dur}" data-track-index="3"><div id="ap-mov">{apresentador_svg(p["personagem"])}</div></div>

 <div id="bancada" class="clip" data-start="0" data-duration="{dur}" data-track-index="4">
  <div class="bc-faixa"></div>
  {ticker(p)}
 </div>

 <div id="lt" class="clip" data-start="0.5" data-duration="4.2" data-track-index="5">
  <span class="lt-nome" id="lt-nome">{esc(ap["nome"])}</span>
  <span class="lt-cargo" id="lt-cargo">{esc(ap["cargo"])}</span>
 </div>

 <div id="legenda" class="clip" data-start="0" data-duration="{dur}" data-track-index="6">{legenda_html(p)}</div>

 <div id="follow-slot" data-composition-id="instagram-follow" data-composition-src="compositions/instagram-follow.html"
      data-start="{t_siga}" data-duration="{dur_follow}" data-width="1080" data-height="1920" data-track-index="7"></div>

 <div id="grao" class="clip" data-start="0" data-duration="{dur}" data-track-index="8"></div>
 <div id="vinheta" class="clip" data-start="0" data-duration="{dur}" data-track-index="9"></div>
 <div id="flash" class="clip" data-start="0" data-duration="{dur}" data-track-index="10"></div>
 <div id="glitch" class="clip" data-start="0" data-duration="{dur}" data-track-index="11"></div>

 <audio id="aud-voz" src="assets/audio/narracao.wav" data-start="0" data-duration="{dur}" data-track-index="20" data-volume="1"></audio>
 <audio id="aud-trilha" src="assets/audio/trilha.wav" data-start="0" data-duration="{dur}" data-track-index="21" data-volume="0.14"></audio>
 <audio id="aud-whoosh" src="assets/audio/whoosh.wav" data-start="0" data-duration="{dur}" data-track-index="22" data-volume="0.32"></audio>
</div>

<script>
(function () {{
  var D = {dados_js};
  window.__qaScenes = D.cenas;
  var cenaIds = D.cenas.map(function (c) {{ return c.id; }});
  function q(id, sel) {{ return document.querySelector("#" + id + " " + sel); }}
  function qa(id, sel) {{ return document.querySelectorAll("#" + id + " " + sel); }}

  var tl = gsap.timeline({{ paused: true }});
  // A capa existe desde o primeiro frame e sai após 1,5s.
   tl.set("#cover-card", {{ opacity: 1 }}, 0);
   tl.set("#cover-card", {{ opacity: 0 }}, 1.5);
   // 1) TRANSIÇÕES entre cenas — receitas CSS do catálogo de transições do
  //    HyperFrames (glitch · whip pan · flash). CSS em vez de WebGL porque
  //    renderiza igual em qualquer máquina, inclusive no runner sem GPU.
  var TR = {json.dumps(transicoes)};
  cenaIds.forEach(function (id, k) {{ tl.set("#" + id, {{ opacity: k === 0 ? 1 : 0, x: 0 }}, 0); }});
  TR.forEach(function (t, k) {{
    var A = "#" + cenaIds[k], B = "#" + cenaIds[k + 1], T = t.time, d = t.duration;
    if (t.shader === "glitch") {{
      var passos = [[-40, 6, 0.9], [55, -8, 0.4], [-25, 12, 1], [70, -4, 0.6], [-15, 3, 0.8], [30, -10, 0.5], [0, 0, 0]];
      passos.forEach(function (p, j) {{
        var tt = T + j * d / passos.length;
        tl.set("#palco", {{ x: p[0], skewX: p[1] }}, tt);
        tl.set("#glitch", {{ opacity: p[2], backgroundPositionY: (j * 97 % 300) + "px" }}, tt);
      }});
      tl.set(B, {{ opacity: 1 }}, T + d * 0.45);
      tl.set(A, {{ opacity: 0 }}, T + d * 0.5);
    }} else if (t.shader === "whip-pan") {{
      tl.set(B, {{ opacity: 1 }}, T);
      tl.fromTo(A, {{ x: 0, filter: "blur(0px)" }}, {{ x: -1080, filter: "blur(24px)", duration: d, ease: "power3.in" }}, T);
      tl.fromTo(B, {{ x: 1080, filter: "blur(24px)" }}, {{ x: 0, filter: "blur(0px)", duration: d, ease: "power3.out" }}, T + d * 0.35);
      tl.set(A, {{ opacity: 0 }}, T + d);
    }} else {{
      tl.fromTo("#flash", {{ opacity: 0 }}, {{ opacity: 1, duration: d * 0.45, ease: "power2.in" }}, T);
      tl.set(B, {{ opacity: 1 }}, T + d * 0.45);
      tl.set(A, {{ opacity: 0 }}, T + d * 0.45);
      tl.to("#flash", {{ opacity: 0, duration: d * 0.55, ease: "power2.out" }}, T + d * 0.45);
    }}
  }});

  function shake(alvo, t0, f) {{
    [[6, -5], [-5, 4], [3, -2], [0, 0]].forEach(function (s, k) {{
      tl.set(alvo, {{ x: s[0] * f, y: s[1] * f }}, t0 + k / 30);
    }});
  }}

  D.cenas.forEach(function (c) {{
    var id = c.id;
    // 2) ABERTURA — headline-slam do título, palavra por palavra
    if (c.tipo === "abertura") {{
      tl.fromTo(qa(id, ".tag"), {{ yPercent: -140, opacity: 0 }}, {{ yPercent: 0, opacity: 1, duration: 0.35, stagger: 0.08, ease: "back.out(2)" }}, c.ini + 0.02);
      tl.fromTo(q(id, ".ab-placa"), {{ scaleY: 0, transformOrigin: "50% 50%" }}, {{ scaleY: 1, duration: 0.3, ease: "power3.out" }}, c.ini);
      tl.fromTo(qa(id, ".ab-w"), {{ scale: 2.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.28, stagger: 0.1, ease: "power4.in" }}, c.ini + 0.02);
      var nW = qa(id, ".ab-w").length;
      var tImp = c.ini + 0.02 + 0.28 + 0.1 * (nW - 1);
      shake(q(id, ".ab-titulo"), tImp, 3);
      tl.to("#flash", {{ opacity: 0.45, duration: 0.04 }}, tImp);
      tl.to("#flash", {{ opacity: 0, duration: 0.25 }}, tImp + 0.04);
      tl.fromTo(q(id, ".ab-mascote"), {{ y: 160, opacity: 0, rotation: -12 }}, {{ y: 0, opacity: 1, rotation: 0, duration: 0.5, ease: "back.out(2)" }}, tImp + 0.1);
      tl.fromTo(q(id, ".ab-mascote"), {{ y: 0 }}, {{ y: -16, duration: 0.6, repeat: Math.max(1, Math.floor((c.fim - tImp) / 0.6)), yoyo: true, ease: "sine.inOut", immediateRender: false }}, tImp + 0.6);
    }}
    // 3) NÚMERO — count-up + headline-slam + camera-shake + carimbo do lugar
    if (c.tipo === "numero") {{
      var dig = q(id, ".nu-dig");
      var alvo = parseInt(dig.getAttribute("data-alvo"), 10) || 0;
      tl.fromTo(q(id, ".nu-icone"), {{ scale: 0.3, rotation: -40, opacity: 0 }}, {{ scale: 1, rotation: 0, opacity: 1, duration: 0.5, ease: "back.out(1.8)" }}, c.ini + 0.02);
      tl.fromTo(q(id, ".nu-rot"), {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.3 }}, c.ini + 0.12);
      tl.fromTo(q(id, ".nu-val"), {{ scale: 2.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.4, ease: "power4.in" }}, c.ini + 0.15);
      for (var n = 0; n <= 16; n++) tl.set(dig, {{ textContent: String(Math.round(alvo * n / 16)) }}, c.ini + 0.15 + 0.6 * n / 16);
      shake(q(id, ".nu-val"), c.ini + 0.55, 3);
      tl.to("#flash", {{ opacity: 0.4, duration: 0.04 }}, c.ini + 0.55);
      tl.to("#flash", {{ opacity: 0, duration: 0.25 }}, c.ini + 0.59);
      var raios = q(id, ".nu-raios");
      if (raios) tl.fromTo(raios, {{ rotation: 0, svgOrigin: "0 0" }}, {{ rotation: 60, duration: c.fim - c.ini, ease: "none" }}, c.ini);
      var gotas = q(id, ".nu-gotas");
      if (gotas) tl.fromTo(gotas, {{ y: -10 }}, {{ y: 14, duration: 0.25, repeat: Math.max(1, Math.floor((c.fim - c.ini) / 0.25)), yoyo: true, ease: "sine.inOut" }}, c.ini);
      var car = q(id, ".nu-carimbo");
      if (car) {{
        var tCar = c.ini + Math.min(1.4, (c.fim - c.ini) * 0.45);
        tl.fromTo(car.querySelector("span"), {{ scale: 3, rotation: -18, opacity: 0 }}, {{ scale: 1, rotation: -5, opacity: 1, duration: 0.28, ease: "power4.in" }}, tCar);
        shake(car, tCar + 0.28, 3);
      }}
    }}
    // 4) QUADRO — split-flap (Solari) das cinco regiões + destaque da falada
    if (c.tipo === "quadro") {{
      tl.fromTo(q(id, ".qd-topo"), {{ scale: 0.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.4, ease: "back.out(2.2)" }}, c.ini + 0.05);
      // Fade sem deslocamento: CHUVA, cidades e temperaturas ficam imóveis na tabela.
      tl.fromTo(q(id, ".qd-painel"), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.25, ease: "none" }}, c.ini + 0.15);
      tl.fromTo(qa(id, ".qd-linha"), {{ opacity: 0 }}, {{ opacity: 1, duration: 0.2, stagger: 0.08, ease: "none" }}, c.ini + 0.2);
      var seq = "0123456789";
      qa(id, ".flap").forEach(function (f, k) {{
        var alvoF = f.getAttribute("data-alvo"), fim = seq.indexOf(alvoF), t0 = c.ini + 0.45 + k * 0.04;
        if (fim >= 0) for (var j = 0; j < 7; j++) tl.set(f, {{ textContent: seq[(fim + 3 + j) % 10] }}, t0 + j * 0.045);
        tl.set(f, {{ textContent: alvoF }}, t0 + 7 * 0.045);
        tl.fromTo(f, {{ scaleY: 0.2 }}, {{ scaleY: 1, duration: 0.32, ease: "bounce.out" }}, t0);
      }});
       // Sincronizar o destaque com a palavra falada, por LOCALIDADE.
       // São preservadas as cidades individuais, mesmo com fala agrupada.
       var linhas = qa(id, ".qd-linha");
       var norm = function (s) {{ return s.toUpperCase().replace(/[^A-ZÁÉÍÓÚÂÊÔÃÕÇ]/g, ""); }};
       var marcas = [];
       linhas.forEach(function (linha, k) {{
         var tokens = (linha.getAttribute("data-cidade") || "").split(/\s+/).map(norm).filter(Boolean);
         for (var i = 0; i < D.palavras.length; i++) {{
           var w = D.palavras[i];
           if (w[0] < c.ini || w[0] >= c.fim || norm(w[2]) !== tokens[0]) continue;
           var coincide = true;
           for (var j = 1; j < tokens.length; j++) {{
             var prox = D.palavras[i + j];
             if (!prox || prox[0] >= c.fim || norm(prox[2]) !== tokens[j]) {{
               coincide = false;
               break;
             }}
           }}
           if (coincide) {{ marcas.push({{ index: k, t: w[0] }}); break; }}
         }}
       }});
       marcas.sort(function (a, b) {{ return a.t - b.t; }});
       marcas.forEach(function (marca, index) {{
         var linha = linhas[marca.index];
         var comeco = Math.max(c.ini + 0.10, marca.t);
         var proxima = index + 1 < marcas.length ? marcas[index + 1].t : c.fim - 0.12;
         var fim = Math.max(comeco + 0.22, Math.min(c.fim - 0.05, proxima));
         var saida = Math.max(comeco + 0.08, fim - 0.18);
         tl.set(linha, {{ backgroundColor: "rgba(255,209,102,0.46)", boxShadow: "inset 0 0 0 3px #ffd166" }}, comeco);
         tl.set(linha.querySelector(".qd-cidade"), {{ color: "#ffe18b" }}, comeco);
         tl.fromTo(linha.querySelector(".qd-barra"), {{ scaleY: 0.65 }}, {{ scaleY: 1.13, duration: 0.18, ease: "power2.out" }}, comeco);
         tl.to(linha, {{ backgroundColor: "rgba(255,209,102,0)", boxShadow: "none", duration: 0.18 }}, saida);
         tl.to(linha.querySelector(".qd-cidade"), {{ color: "#ffffff", duration: 0.18 }}, saida);
       }});
    }}
    // 5) ALERTA — triângulo pulsando, título batendo, carimbo ATENÇÃO
    if (c.tipo === "alerta") {{
      tl.fromTo(q(id, ".al-icone"), {{ scale: 0.2, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.4, ease: "back.out(2.5)" }}, c.ini + 0.02);
      tl.fromTo(q(id, ".al-icone"), {{ scale: 1 }}, {{ scale: 1.08, duration: 0.3, repeat: Math.max(1, Math.floor((c.fim - c.ini) / 0.3)), yoyo: true, ease: "sine.inOut", immediateRender: false }}, c.ini + 0.45);
      tl.fromTo(q(id, ".al-titulo"), {{ scale: 2.2, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.35, ease: "power4.in" }}, c.ini + 0.12);
      shake(q(id, ".al-titulo"), c.ini + 0.47, 4);
      tl.fromTo(q(id, ".al-det"), {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.3, ease: "power3.out" }}, c.ini + 0.5);
      var tA = c.ini + Math.min(1.2, (c.fim - c.ini) * 0.4);
      tl.fromTo(q(id, ".al-carimbo span"), {{ scale: 3, rotation: 16, opacity: 0 }}, {{ scale: 1, rotation: -6, opacity: 1, duration: 0.28, ease: "power4.in" }}, tA);
      shake(q(id, ".al-carimbo"), tA + 0.28, 3);
    }}
    // 6) FRASE — cada fala entra e sai no tempo dela
    if (c.tipo === "frase") {{
      c.batidas.forEach(function (b, k) {{
        var el = q(id, '.fr-texto[data-b="' + b.i + '"]');
        var sai = k + 1 < c.batidas.length ? c.batidas[k + 1].ini : c.fim;
        tl.fromTo(el, {{ opacity: 0, y: 60, scale: 0.9 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.35, ease: "back.out(1.8)" }}, b.ini + 0.02);
        if (k + 1 < c.batidas.length) tl.to(el, {{ opacity: 0, y: -40, duration: 0.2 }}, sai - 0.15);
      }});
    }}
    // 7) CTA — mascote, chamada e o card "Seguir" (sub-composição)
    if (c.tipo === "cta") {{
      tl.fromTo(q(id, ".cta-mascote"), {{ y: -300, rotation: 20 }}, {{ y: 0, rotation: 0, duration: 0.55, ease: "bounce.out" }}, c.ini + 0.02);
      tl.fromTo(q(id, ".cta-chamada"), {{ scale: 0.5, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.35, ease: "back.out(2.4)" }}, c.ini + 0.12);
      tl.fromTo(q(id, ".cta-sub"), {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.3 }}, c.ini + 0.35);
      tl.to("#cta-b1", {{ y: -30, scale: 0.9, duration: 0.4, ease: "power2.inOut" }}, D.tSiga - 0.1);
    }}
  }});
  tl.to("#vinheta", {{ opacity: 1.0, duration: 0.3 }}, D.dur - 0.35);

  // 8) HUD: ponto do AO VIVO piscando (repeat finito), ticker correndo
  var nPisca = Math.floor(D.dur / 0.9);
  tl.fromTo("#hud-ponto", {{ opacity: 1 }}, {{ opacity: 0.15, duration: 0.45, repeat: nPisca * 2 - 1, yoyo: true, ease: "steps(1)" }}, 0);
  tl.fromTo("#hud", {{ y: -140 }}, {{ y: 0, duration: 0.4, ease: "back.out(1.6)" }}, 0);
  var trilho = document.getElementById("tk-trilho");
  tl.fromTo(trilho, {{ x: 0 }}, {{ x: -trilho.scrollWidth / 2, duration: D.dur, ease: "none" }}, 0);

  // 9) LOWER THIRD — entra e sai
  tl.fromTo("#lt-nome", {{ xPercent: -120, opacity: 0 }}, {{ xPercent: 0, opacity: 1, duration: 0.35, ease: "power3.out" }}, 0.5);
  tl.fromTo("#lt-cargo", {{ xPercent: -120, opacity: 0 }}, {{ xPercent: 0, opacity: 1, duration: 0.35, ease: "power3.out" }}, 0.62);
  tl.to(["#lt-nome", "#lt-cargo"], {{ xPercent: 130, opacity: 0, duration: 0.3, ease: "power2.in", stagger: 0.06 }}, 4.3);

  // 10) APRESENTADOR — respiração, piscadas, sobrancelhas, aponta pro telão
  var svg = document.getElementById("ap-svg");
  var ombro = svg.getAttribute("data-ombro");
  var ombroE = svg.getAttribute("data-ombro-e");
  tl.fromTo("#ap-wrap", {{ y: 700 }}, {{ y: 0, duration: 0.5, ease: "back.out(1.4)" }}, 0);
  var nResp = Math.max(1, Math.floor(D.dur / 1.6));
  tl.fromTo("#ap-corpo", {{ scaleY: 1, svgOrigin: "260 640" }}, {{ scaleY: 1.018, duration: 0.8, repeat: nResp * 2 - 1, yoyo: true, ease: "sine.inOut" }}, 0);
  tl.fromTo("#ap-cabeca", {{ y: 0 }}, {{ y: -5, duration: 0.8, repeat: nResp * 2 - 1, yoyo: true, ease: "sine.inOut" }}, 0);
  for (var tp = 1.3; tp < D.dur - 0.3; tp += 2.9) {{
    tl.set("#ap-palp", {{ opacity: 1 }}, tp);
    tl.set("#ap-palp", {{ opacity: 0 }}, tp + 0.1);
  }}
  D.batidas.forEach(function (b, k) {{
    tl.fromTo(["#ap-sobE", "#ap-sobD"], {{ y: 0 }}, {{ y: -14, duration: 0.12, yoyo: true, repeat: 1, ease: "power2.out" }}, b.ini);
    tl.fromTo("#ap-mov", {{ rotation: 0, svgOrigin: "260 640" }}, {{ rotation: (k % 2 ? 2.5 : -2.5), duration: 0.18, yoyo: true, repeat: 1, ease: "power1.inOut" }}, b.ini);
    var d = D.direcao[k];
    if (d) {{
      // O braço E está livre; o braço D continua apontando para o telão.
      var graus = {{ repouso:0, explicar:-7, apontar:-12, enfatizar:-10, alertar:-16, acolher:-5, perguntar:-10 }};
      var angulo = (graus[d.gesto] || 0) * d.energia;
      var trecho = Math.min(.58, Math.max(.2, (b.fim-b.ini)*.28));
      tl.fromTo("#ap-bracoE", {{rotation:0, svgOrigin:ombroE}},
        {{rotation:angulo, duration:trecho, yoyo:true, repeat:1, ease:"sine.inOut", immediateRender:false}}, b.ini+.04);
      var zoom = {{aproximar:1.06,aproximar_suave:1.035,abrir:1,estabilizar:1,manter:1.015}};
      // Só o avatar é aproximado: números e cartões nunca sofrem zoom.
      tl.to("#ap-wrap", {{scale:zoom[d.camera]||1, duration:.42, ease:"power2.inOut"}}, b.ini);
    }}
  }});
  if (D.direcao.length) tl.to("#ap-wrap", {{scale:1,duration:.22,ease:"power2.out"}},Math.max(0,D.dur-.27));
  D.cenas.forEach(function (c) {{
    var dado = (c.tipo === "numero" || c.tipo === "quadro" || c.tipo === "alerta");
    tl.to("#ap-pupilas", {{ x: dado ? 8 : 0, y: dado ? -7 : 0, duration: 0.2 }}, c.ini + 0.1);
    if (dado) {{
      // braço direito sobe e aponta pro telão durante a cena de dado
      tl.to("#ap-bracoD", {{ rotation: -128, svgOrigin: ombro, duration: 0.3, ease: "back.out(1.6)" }}, c.ini + 0.15);
      tl.to("#ap-bracoD", {{ rotation: 0, svgOrigin: ombro, duration: 0.3, ease: "power2.inOut" }}, Math.max(c.ini + 0.6, c.fim - 0.3));
    }}
  }});

  // 11) LIP SYNC — a boca segue a energia do áudio (amplitude.py)
  D.boca.forEach(function (c) {{
    tl.set("#ap-boca-abre", {{ scaleY: c[1], scaleX: 0.75 + 0.25 * c[1], svgOrigin: "0 0" }}, c[0]);
  }});

  // 12) LEGENDA KARAOKÊ (caption-highlight): página por página, palavra por palavra
  var pags = document.querySelectorAll(".lg-pag");
  pags.forEach(function (pg, k) {{
    var s = parseFloat(pg.getAttribute("data-s")), e = parseFloat(pg.getAttribute("data-e"));
    var prox = k + 1 < pags.length ? parseFloat(pags[k + 1].getAttribute("data-s")) : D.dur;
    var sai = Math.min(prox, e + 0.35);
    tl.fromTo(pg, {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.12, ease: "power2.out" }}, Math.max(0, s - 0.05));
    tl.to(pg, {{ opacity: 0, duration: 0.06 }}, sai - 0.06);
    pg.querySelectorAll(".lg-w").forEach(function (w) {{
      var ws = parseFloat(w.getAttribute("data-s")), we = parseFloat(w.getAttribute("data-e"));
      var bg = w.querySelector(".lg-bg");
      tl.fromTo(bg, {{ scaleX: 0 }}, {{ scaleX: 1, duration: Math.min(0.12, we - ws), ease: "power2.out" }}, ws);
      tl.fromTo(w, {{ scale: 1 }}, {{ scale: 1.08, duration: 0.08, yoyo: true, repeat: 1, ease: "power1.out" }}, ws);
      tl.to(bg, {{ scaleX: 0, transformOrigin: "100% 50%", duration: 0.08 }}, we);
    }});
  }});

  // 13) nuvens, mar, bondinho e chuva do telão (movimento contínuo, finito)
  document.querySelectorAll("[class$='-nuvem']").forEach(function (n) {{
    tl.to(n, {{ x: "+=" + n.getAttribute("data-dx"), duration: D.dur, ease: "none" }}, 0);
  }});
  document.querySelectorAll("[class$='-mar']").forEach(function (m) {{
    tl.fromTo(m, {{ x: 0 }}, {{ x: 60, duration: 1.4, repeat: Math.floor(D.dur / 1.4), ease: "none" }}, 0);
  }});
  document.querySelectorAll("[class$='-bonde']").forEach(function (b) {{
    tl.fromTo(b, {{ x: 0, y: 0 }}, {{ x: -60, y: 57, duration: D.dur, ease: "none" }}, 0);
  }});
  document.querySelectorAll("[class$='-raios']").forEach(function (r) {{
    tl.fromTo(r, {{ rotation: 0, svgOrigin: "0 0" }}, {{ rotation: 40, duration: D.dur, ease: "none" }}, 0);
  }});
  document.querySelectorAll("[class$='-chuva']").forEach(function (c) {{
    tl.fromTo(c, {{ y: -120 }}, {{ y: 0, duration: 0.35, repeat: Math.floor(D.dur / 0.35), ease: "none" }}, 0);
  }});

  // 14) grão de filme com deslocamento em degraus
  for (var gk = 0; gk < D.dur * 12; gk++) {{
    tl.set("#grao", {{ x: ((gk * 37) % 40) - 20, y: ((gk * 53) % 40) - 20 }}, gk / 12);
  }}

  window.__timelines["main"] = tl;
}})();
</script>
</body>
</html>
'''

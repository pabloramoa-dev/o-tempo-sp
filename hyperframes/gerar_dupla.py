# -*- coding: utf-8 -*-
"""
gerar_dupla.py — boletim do @otemposp em DUPLA: Bira e Bia conversando.

Formato padrão desde 18/11/2026 (manhã e tarde). Quem apresenta continua o
mesmo de antes; o outro personagem entra na conversa:
  - 06h (hoje):    Bira apresenta, Bia acompanha
  - 18h (amanhã):  Bia apresenta, Bira acompanha

Roteiro: a mesma pauta de produção (scripts/produce.pauta) com as falas
alternadas entre os dois — uma localidade falada por região, todas as 11 no
quadro. Abre com uma saudação curta, o CTA fica com quem apresenta e quem
acompanha se despede no fim.

Recursos (todos gratuitos, em hyperframes/assets/dupla/):
  - SFX Kit (github.com/wyzowl/sfx-kit, CC0) no ponto de sincronia do guia
  - trilha "Sunset on the Beach" (Komiku, CC0) com DUCKING (sidechaincompress)
  - normalização EBU R128 a -14 LUFS (ffmpeg-normalize)
  - figurantes Open Peeps (CC0, via DiceBear) e fundo geopattern (MIT) no CTA

Reversão sem editar código: variável SP_FORMATO=solo volta ao boletim de um
personagem só (hyperframes/gerar_hf.py).

Teste local com dados ilustrativos (nunca publicar):
    python hyperframes/gerar_dupla.py --ilustrativo tarde --out output/teste.mp4
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(AQUI))

import gerar_hf as HF  # noqa: E402
import compor as C  # noqa: E402
from src.otemposp.characters.amplitude import gerar_cues  # noqa: E402
from src.otemposp.characters import kokoro as KK  # noqa: E402
from src.otemposp.characters import director as DIRECAO  # noqa: E402

PRESETS = HF.PRESETS
SR = 44100
DUPLA = AQUI / 'assets' / 'dupla'
MUSICA = DUPLA / 'trilha_komiku_sunset_on_the_beach.ogg'
GAP_MESMO, GAP_TROCA = 0.24, 0.34
NOME = {'bira': 'Bira', 'bia': 'Bia'}


def run(cmd, **kw):
    subprocess.run([str(x) for x in cmd], check=True, **kw)


# ------------------------------------------------------------ roteiro ---
def papeis(when):
    lider = 'bira' if when == 'hoje' else 'bia'
    return lider, ('bia' if lider == 'bira' else 'bira')


def roteiro_dupla(brief):
    """Batidas da pauta de produção + falante de cada uma."""
    from scripts.produce import pauta
    batidas, cidades = pauta(brief)
    when = brief['when']
    lider, outro = papeis(when)
    saud = 'Bom dia' if when == 'hoje' else 'Boa noite'
    periodo = 'de hoje' if when == 'hoje' else 'de amanhã'

    def beat(tipo, fala, **dados):
        return dict(tipo=tipo, fala=fala, legenda=fala, dados=dados)

    bat = [beat('nenhum', f'{saud}, São Paulo! Bora ver o tempo {periodo}, {NOME[outro]}?')]
    falante = [lider]
    for k, b in enumerate(batidas):
        b = dict(b)
        if k == 0:
            b['fala'] = f'Bora, {NOME[lider]}! ' + b['fala']
            b['legenda'] = f'Bora, {NOME[lider]}! ' + b['legenda']
        bat.append(b)
        falante.append(outro if k % 2 == 0 else lider)
    falante[-1] = lider                    # o CTA fica com quem apresenta
    ate = 'a tarde' if when == 'hoje' else 'amanhã'
    bat.append(beat('cta', f'{saud}, e até {ate}!'))
    falante.append(outro)
    return bat, falante, cidades, lider, outro


# --------------------------------------------------- dados ilustrativos ---
ILUSTRATIVO = {
    'norte_1': (17, 27, 1.2), 'norte_2': (16, 26, 2.4), 'centro': (18, 27, 0.8),
    'oeste': (17, 26, 1.0), 'leste_1': (18, 28, 0.6), 'leste_2': (17, 28, 1.6),
    'sul_1': (17, 26, 1.4), 'sul_2': (16, 25, 3.2), 'litoral_norte': (20, 28, 4.0),
    'litoral_baixada': (20, 27, 5.5), 'litoral_sul': (19, 26, 7.8),
}


def brief_ilustrativo(when, data_pub):
    """Só para teste visual (is_fixture=True mostra PILOTO/SIMULAÇÃO no vídeo)."""
    from src.otemposp.geo import daily_locations, sectors
    pub = dt.date.fromisoformat(data_pub)
    alvo = pub + dt.timedelta(days=0 if when == 'hoje' else 1)
    cards = []
    for k, pt in enumerate(daily_locations(pub, when)):
        mn, mx, mm = ILUSTRATIVO[pt['sector']]
        ajuste = (k % 3) - 1 if when == 'hoje' else 0
        cards.append(dict(point=pt['name'], sector=pt['sector'], short=sectors()[pt['sector']]['short'],
                          min_c=float(mn), max_c=float(mx + ajuste), rain_mm=mm, rain_pct=None))
    return dict(when=when, date=alvo.isoformat(), is_fixture=True, hora_inicio=0, cards=cards,
                caption='TESTE COM DADOS ILUSTRATIVOS — NÃO PUBLICAR',
                hottest=max(cards, key=lambda c: c['max_c']), wettest=max(cards, key=lambda c: c['rain_mm']))


# ------------------------------------------------------------- vozes ---
def narrar_dupla(bat, falante, work):
    from kokoro_onnx import Kokoro
    k = Kokoro(*KK.garantir_modelo())
    blocos, segs, t = [], [], 0.0
    for i, (b, quem) in enumerate(zip(bat, falante)):
        pr = PRESETS[quem]
        s, sr = k.create(b['fala'], voice=KK.estilo(k, pr['voice']), speed=pr['speed'], lang='pt-br')
        s = KK.resample_44100(np.asarray(s, dtype=np.float32), sr)
        prox = falante[i + 1] if i + 1 < len(bat) else quem
        gap = GAP_TROCA if prox != quem else GAP_MESMO
        n_gap = int(gap * SR)
        segs.append({'i': i, 'quem': quem, 'ini': round(t, 3), 'fim_fala': round(t + len(s) / SR, 3),
                     'fim': round(t + (len(s) + n_gap) / SR, 3), 'texto': b['fala']})
        blocos.append((s, quem))
        blocos.append((np.zeros(n_gap, np.float32), None))
        t += (len(s) + n_gap) / SR
        print(f'  [{quem:4s}] {segs[-1]["ini"]:5.2f}s  {b["fala"]}')
    voz = np.concatenate([b for b, _ in blocos])
    pk = float(np.abs(voz).max()) or 1.0
    pistas = {q: np.concatenate([b if w == q else np.zeros_like(b) for b, w in blocos]) / pk * 0.97
              for q in ('bia', 'bira')}
    raw = work / 'raw.wav'
    HF.gravar_wav(raw, voz / pk * 0.97, SR)
    return segs, pistas, raw


# --------------------------------------------------------------- SFX ---
class Sfx:
    def __init__(self, dur):
        self.S = json.loads((DUPLA / 'sfx.json').read_text(encoding='utf-8'))['sons']
        self.n = int(dur * SR)
        self.bus = np.zeros(self.n, np.float32)
        self.cache, self.usados = {}, []

    def _carregar(self, sid):
        if sid not in self.cache:
            pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(DUPLA / self.S[sid]['arquivo']),
                                           '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'])
            self.cache[sid] = np.frombuffer(pcm, np.float32).copy()
        return self.cache[sid]

    def por(self, sid, momento, ganho=0.5):
        """Guia do SFX Kit: início = momento − sync_at."""
        x = self._carregar(sid)
        ini = int(round((momento - self.S[sid]['sync_at']) * SR))
        if ini < 0:
            x, ini = x[-ini:], 0
        m = min(len(x), self.n - ini)
        if m > 0:
            self.bus[ini:ini + m] += x[:m] * ganho
            self.usados.append((round(momento, 2), sid))


def planejar_sfx(pacote, n_titulo):
    sx = Sfx(pacote['dur'])
    cenas, bat = pacote['cenas'], pacote['batidas']
    fins = [cenas[k + 1]['ini'] if k + 1 < len(cenas) else pacote['dur'] for k in range(len(cenas))]
    for T, tipo in zip(pacote['cortes'], pacote['transicoes']):
        if tipo == 'whip-pan':
            sx.por('whoosh-medium-soft', T + 0.30, 0.55)
        elif tipo == 'glitch':
            sx.por('digital-glitch-clear', T + 0.02, 0.40)
            sx.por('whoosh-fast-soft', T + 0.20, 0.30)
        else:
            sx.por('shimmer-short-soft', T + 0.20, 0.45)
    for c, fim in zip(cenas, fins):
        ini = c['ini']
        if c['tipo'] == 'abertura':
            sx.por('pop-medium-in', ini + 0.05, 0.45)
            sx.por('pop-medium-in', ini + 0.13, 0.45)
            t_imp = ini + 0.02 + 0.28 + 0.1 * (n_titulo - 1)
            sx.por('cinematic-drum-big', t_imp, 0.55)
            sx.por('move-bounce', t_imp + 0.12, 0.30)
        elif c['tipo'] == 'numero':
            sx.por('data-countup-short', ini + 0.15, 0.35)
            sx.por('data-number-land', ini + 0.75, 0.45)
            sx.por('impact-medium-soft', ini + 0.55, 0.40)
            t_car = ini + min(1.4, (fim - ini) * 0.45)
            sx.por('impact-light-firm', t_car + 0.28, 0.50)
        elif c['tipo'] == 'quadro':
            n = len(bat[c['batidas'][0]]['dados'].get('cidades') or []) or 3
            for k in range(n):
                sx.por(f'tone-step-{min(5, k + 1)}', ini + 0.30 + 0.1 * k, 0.22)
        elif c['tipo'] == 'alerta':
            sx.por('notification-alert-clear', ini + 0.05, 0.40)
            sx.por('boom-hit-medium', ini + 0.47, 0.45)
            t_a = ini + min(1.2, (fim - ini) * 0.4)
            sx.por('impact-light-firm', t_a + 0.28, 0.50)
        elif c['tipo'] == 'cta':
            sx.por('move-bounce', ini + 0.10, 0.35)
            for k in range(7):
                sx.por('pop-small-in', ini + 0.55 + 0.09 * k, 0.40)
    sx.por('notification-message-in-soft', pacote['tSiga'] + 0.15, 0.40)
    sx.por('sting-warm-short', pacote['dur'] - 1.75, 0.50)
    return sx


# ------------------------------------------------------------- mixagem ---
def mixar(work, narr, sfx_bus, dur):
    HF.gravar_wav(work / 'sfx.wav', sfx_bus, SR)
    mix = work / 'mix_bruto.wav'
    fade_out = max(0, dur - 1.6)
    grafo = (
        f'[1:a]atrim=0:{dur + 0.5},asetpts=PTS-STARTPTS,volume=0.32,'
        f'afade=t=in:d=0.6,afade=t=out:st={fade_out:.2f}:d=1.5,aformat=channel_layouts=stereo[mus];'
        '[0:a]aformat=channel_layouts=stereo,asplit=2[voz][side];'
        # DUCKING: a voz comprime a música enquanto alguém fala
        '[mus][side]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350:makeup=1[duck];'
        '[2:a]aformat=channel_layouts=stereo[fx];'
        '[voz][duck][fx]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.95[out]')
    run(['ffmpeg', '-y', '-v', 'error', '-i', narr, '-stream_loop', '-1', '-i', MUSICA, '-i', work / 'sfx.wav',
         '-filter_complex', grafo, '-map', '[out]', '-ar', SR, '-t', f'{dur:.3f}', mix])
    final = work / 'mix.wav'
    run([sys.executable, '-m', 'ffmpeg_normalize', mix, '-nt', 'ebu', '-t', '-14', '-tp', '-1.5',
         '-ar', str(SR), '-c:a', 'pcm_s16le', '-f', '-o', final])
    return final


# ------------------------------------------------------- HTML da dupla ---
def html_dupla(pacote, falante, boca_outro, extras, outro):
    h = C.compor(pacote)
    dur = pacote['dur']
    svg = C.apresentador_svg(outro).replace('ap-', 'bp-')
    h = h.replace(' <div id="bancada"',
                  f' <div id="bp-wrap" class="clip" data-start="0" data-duration="{dur}" data-track-index="12">'
                  f'<div id="bp-mov">{svg}</div></div>\n\n <div id="bancada"', 1)
    ap2 = C.APRESENTADOR[outro]
    h = h.replace(' <div id="legenda"',
                  f' <div id="lt2" class="clip" data-start="0.7" data-duration="4.2" data-track-index="13">'
                  f'<span class="lt-nome" id="lt2-nome">{C.esc(ap2["nome"])}</span>'
                  f'<span class="lt-cargo" id="lt2-cargo">{C.esc(ap2["cargo"])}</span></div>\n\n'
                  ' <div id="legenda"', 1)
    cor_outro = ap2['camisa']
    cor_bia = C.APRESENTADOR['bia']['camisa']
    geo = extras['geo']
    css = (
        '\n#ap-wrap { left: -30px !important; }\n'
        '#bp-wrap { position: absolute; left: 590px; top: 1010px; width: 520px; height: 700px; z-index: 311; }\n'
        '#lt { left: 22px !important; top: 1392px !important; }\n'
        '#lt2 { position: absolute; right: 22px; top: 1392px; z-index: 330; display: flex; flex-direction: column; align-items: flex-end; }\n'
        '#lt .lt-nome, #lt2 .lt-nome { font-size: 52px; }\n'
        '#lt .lt-cargo, #lt2 .lt-cargo { font-size: 26px; margin-top: 10px; }\n'
        f'#lt2 .lt-nome {{ box-shadow: -10px 10px 0 {cor_outro}; }}\n'
        f'.cta-geo {{ position: absolute; inset: 0; background-image: url("{geo}"); background-size: 420px; opacity: 0.30; mix-blend-mode: multiply; }}\n'
        '.cta-peeps { position: absolute; top: 650px; left: 0; right: 0; height: 200px; display: flex; justify-content: center; }\n'
        '.cta-peeps img { display: block; width: 170px; height: 170px; margin: 0 -14px; }\n'
        f'.lg-bia .lg-bg {{ background-color: {cor_bia} !important; }}\n')
    h = h.replace('</style>', css + '</style>', 1)
    imgs = ''.join(f'<img class="peep" src="{u}" alt=""/>' for u in extras['peeps'])
    h = h.replace('<div class="cta-fundo"></div>',
                  f'<div class="cta-fundo"></div><div class="cta-geo"></div><div class="cta-peeps">{imgs}</div>')
    trocas = [
        ('    if (dado) {\n      // braço direito',
         '    if (dado && window.__DUPLA.falante[c.batidas[0].i] === window.__DUPLA.principal) {\n      // braço direito'),
        ('  D.batidas.forEach(function (b, k) {\n    tl.fromTo(["#ap-sobE"',
         '  D.batidas.forEach(function (b, k) {\n    if (window.__DUPLA.falante[k] !== window.__DUPLA.principal) return;\n'
         '    tl.fromTo(["#ap-sobE"'),
        ('<script>\n(function () {', None),
        ('  window.__timelines["main"] = tl;', '__JS__'),
    ]
    dupla = {'principal': pacote['personagem'], 'falante': falante,
             'boca2': [[t, C.MOUTH.get(v, 0.3)] for t, v in boca_outro]}
    for antes, depois in trocas:
        if antes not in h:
            raise RuntimeError(f'compor.py mudou: ponto de injeção não encontrado ({antes[:40]!r})')
        if depois is None:
            depois = f'<script>window.__DUPLA = {json.dumps(dupla)};</script>\n<script>\n(function () {{'
        elif depois == '__JS__':
            depois = JS_DUPLA + '\n  window.__timelines["main"] = tl;'
        h = h.replace(antes, depois, 1)
    return h


JS_DUPLA = r'''
  // ===== DUPLA: segundo personagem à direita; quem fala é destaque, o outro olha =====
  var F = window.__DUPLA.falante, P = window.__DUPLA.principal;
  var svgB = document.getElementById("bp-svg");
  var ombroBE = svgB.getAttribute("data-ombro-e");
  tl.fromTo("#bp-wrap", { y: 700 }, { y: 0, duration: 0.5, ease: "back.out(1.4)" }, 0.15);
  var nRespB = Math.max(1, Math.floor(D.dur / 1.7));
  tl.fromTo("#bp-corpo", { scaleY: 1, svgOrigin: "260 640" }, { scaleY: 1.018, duration: 0.85, repeat: nRespB * 2 - 1, yoyo: true, ease: "sine.inOut" }, 0.3);
  tl.fromTo("#bp-cabeca", { y: 0 }, { y: -5, duration: 0.85, repeat: nRespB * 2 - 1, yoyo: true, ease: "sine.inOut" }, 0.3);
  for (var tb = 2.2; tb < D.dur - 0.3; tb += 3.3) {
    tl.set("#bp-palp", { opacity: 1 }, tb);
    tl.set("#bp-palp", { opacity: 0 }, tb + 0.1);
  }
  tl.set("#bp-boca-abre", { scaleY: 0.06, svgOrigin: "0 0" }, 0);
  window.__DUPLA.boca2.forEach(function (c) {
    tl.set("#bp-boca-abre", { scaleY: c[1], scaleX: 0.75 + 0.25 * c[1], svgOrigin: "0 0" }, c[0]);
  });
  tl.fromTo("#lt2-nome", { xPercent: 120, opacity: 0 }, { xPercent: 0, opacity: 1, duration: 0.35, ease: "power3.out" }, 0.7);
  tl.fromTo("#lt2-cargo", { xPercent: 120, opacity: 0 }, { xPercent: 0, opacity: 1, duration: 0.35, ease: "power3.out" }, 0.82);
  tl.to(["#lt2-nome", "#lt2-cargo"], { xPercent: 130, opacity: 0, duration: 0.3, ease: "power2.in", stagger: 0.06 }, 4.4);
  function cenaDe(t) { var r = D.cenas[0]; D.cenas.forEach(function (c) { if (t >= c.ini - 0.01) r = c; }); return r; }
  D.batidas.forEach(function (b, k) {
    var quem = F[k], c = cenaDe(b.ini);
    var dado = (c.tipo === "numero" || c.tipo === "quadro" || c.tipo === "alerta");
    var fala = quem === P ? "#ap-wrap" : "#bp-wrap", ouve = quem === P ? "#bp-wrap" : "#ap-wrap";
    tl.to(fala, { scale: 1.03, filter: "brightness(1)", transformOrigin: "50% 100%", duration: 0.25, ease: "power2.out" }, b.ini - 0.05);
    tl.to(ouve, { scale: 0.95, filter: "brightness(0.86)", transformOrigin: "50% 100%", duration: 0.25, ease: "power2.out" }, b.ini - 0.05);
    if (quem !== P) {
      tl.to("#ap-pupilas", { x: 12, y: 2, duration: 0.18 }, b.ini + 0.25);
      tl.to("#bp-pupilas", { x: dado ? -8 : -4, y: dado ? -7 : 0, duration: 0.18 }, b.ini + 0.1);
      tl.fromTo(["#bp-sobE", "#bp-sobD"], { y: 0 }, { y: -14, duration: 0.12, yoyo: true, repeat: 1, ease: "power2.out" }, b.ini);
      tl.fromTo("#bp-mov", { rotation: 0, svgOrigin: "260 640" }, { rotation: (k % 2 ? -2.5 : 2.5), duration: 0.18, yoyo: true, repeat: 1, ease: "power1.inOut" }, b.ini);
      if (dado) {
        tl.to("#bp-bracoE", { rotation: 128, svgOrigin: ombroBE, duration: 0.3, ease: "back.out(1.6)" }, b.ini + 0.15);
        tl.to("#bp-bracoE", { rotation: 0, svgOrigin: ombroBE, duration: 0.3, ease: "power2.inOut" }, Math.max(b.ini + 0.6, b.fim - 0.15));
      } else {
        tl.fromTo("#bp-bracoD", { rotation: 0, svgOrigin: svgB.getAttribute("data-ombro") }, { rotation: 10, duration: 0.35, yoyo: true, repeat: 1, ease: "sine.inOut", immediateRender: false }, b.ini + 0.05);
      }
    } else {
      tl.to("#bp-pupilas", { x: -12, y: 2, duration: 0.18 }, b.ini + 0.25);
    }
  });
  tl.to(["#ap-wrap", "#bp-wrap"], { scale: 1, filter: "brightness(1)", duration: 0.3 }, D.dur - 0.6);
  // legenda: palavras da Bia na cor dela, as do Bira na cor padrão
  document.querySelectorAll(".lg-w").forEach(function (w) {
    var s = parseFloat(w.getAttribute("data-s"));
    for (var k = D.batidas.length - 1; k >= 0; k--) {
      if (s >= D.batidas[k].ini - 0.01) { if (F[k] === "bia") w.classList.add("lg-bia"); break; }
    }
  });
  // CTA: figurantes Open Peeps entram, balançam e saem antes do card "Seguir"
  D.cenas.forEach(function (c) {
    if (c.tipo !== "cta") return;
    var ps = document.querySelectorAll("#" + c.id + " .peep");
    if (!ps.length) return;
    tl.fromTo(ps, { y: 140, opacity: 0, scale: 0.5 }, { y: 0, opacity: 1, scale: 1, duration: 0.35, stagger: 0.09, ease: "back.out(2.2)" }, c.ini + 0.5);
    var tSai = Math.max(c.ini + 1.4, D.tSiga - 0.15);
    ps.forEach(function (p, k) {
      tl.fromTo(p, { y: 0 }, { y: -12, duration: 0.42, repeat: Math.max(1, Math.floor((tSai - c.ini - 1.2) / 0.42)), yoyo: true, ease: "sine.inOut", immediateRender: false }, c.ini + 1.2 + k * 0.06);
    });
    tl.to(ps, { opacity: 0, y: 60, scale: 0.7, duration: 0.25, stagger: 0.03, ease: "power2.in" }, tSai);
  });
'''


# ------------------------------------------------------------- render ---
def preparar_dupla(brief, out):
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / ('work_dupla_' + ('bira' if brief['when'] == 'hoje' else 'bia'))
    work.mkdir(parents=True, exist_ok=True)
    if HF.BUILD.exists():
        shutil.rmtree(HF.BUILD)
    HF.BUILD.mkdir(parents=True)
    HF.AUDIO.mkdir(parents=True, exist_ok=True)
    vendor = AQUI / 'assets' / 'vendor'
    vendor.mkdir(parents=True, exist_ok=True)
    shutil.copy(RAIZ / 'video/node_modules/gsap/dist/gsap.min.js', vendor)

    bat, falante, cidades, lider, outro = roteiro_dupla(brief)
    formato = ('eventos_fim_de_semana' if brief.get('especial_eventos') else
               'amanha_no_rio' if lider == 'bia' else 'rio_antes_de_sair')
    segs, pistas, raw = narrar_dupla(bat, falante, work)
    tempos = [(s['ini'], max(s['ini'] + 0.2, s['fim_fala'])) for s in segs]
    dur = round(segs[-1]['fim'] + HF.CAUDA, 2)

    narr = work / 'narracao.wav'
    run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-af', HF.FILTRO_VOZ, '-ar', SR, '-ac', 1, narr])
    x, _ = HF.ler_wav(narr)
    x = np.concatenate([x, np.zeros(max(0, int(dur * SR) - len(x)), np.float32)])[:int(dur * SR)]
    HF.gravar_wav(narr, x, SR)

    cues = {}
    for quem, p in pistas.items():
        p = np.concatenate([p, np.zeros(max(0, int(dur * SR) - len(p)), np.float32)])[:int(dur * SR)]
        cues[quem] = gerar_cues(p / (np.abs(p).max() or 1), SR, fps=30)

    cenas = HF.agrupar_cenas(bat)
    for c in cenas:
        c['ini'] = tempos[c['batidas'][0]][0]
    cortes = [round(max(0.05, c['ini'] - HF.TRANS_DUR * 0.55), 3) for c in cenas[1:]]
    trans = [{'quadro': 'glitch', 'alerta': 'glitch', 'cta': 'flash-through-white'}.get(c['tipo'], 'whip-pan')
             for c in cenas[1:]]
    palavras = []
    for i, b in enumerate(bat):
        for p in HF.tempos_das_palavras(b['legenda'], *tempos[i]):
            p['b'] = i
            palavras.append(p)

    data_iso = brief['date']
    plano = DIRECAO.planejar(bat, [dict(ini=s, fim=e) for s, e in tempos], lider)
    pacote = {
        'dicas_praticas': [], 'direcao': plano if DIRECAO.ativo() else [],
        'especial_eventos': bool(brief.get('especial_eventos')),
        'dur': dur, 'personagem': lider, 'formato': formato, 'demo': bool(brief.get('is_fixture')),
        'data': data_iso, 'data_ext': HF.data_extenso(data_iso), 'data_previsao': data_iso,
        'hora': '14:00' if brief.get('especial_eventos') else ('06:00' if lider == 'bira' else '18:00'),
        'ceu': 'chuva' if ((brief['wettest'].get('rain_pct') or 0) >= 70
                         or (brief['wettest'].get('rain_mm') or 0) >= 10) else 'sol',
        'cidades': cidades,
        'batidas': [dict(b, ini=tempos[i][0], fim=tempos[i][1]) for i, b in enumerate(bat)],
        'cenas': cenas, 'cortes': cortes, 'transicoes': trans, 'palavras': palavras,
        'capa_s': HF.momento_da_capa(cenas, cortes, dur),
        'boca': [[c['start'], c['value']] for c in cues[lider]],
        'dupla': {'apresenta': lider, 'acompanha': outro, 'falantes': falante},
    }
    ult = cenas[-1]
    pacote['tSiga'] = round(max(0.5, min(ult['ini'] + 0.9, dur - 2.2) if ult['tipo'] == 'cta' else dur - 2.6), 2)
    n_titulo = len(C.TITULOS.get(formato, 'O TEMPO SP').split())

    sx = planejar_sfx(pacote, n_titulo)
    mix = mixar(work, narr, sx.bus, dur)
    # faixa única: voz + trilha com ducking + SFX (as outras duas ficam mudas)
    shutil.copy(mix, HF.AUDIO / 'narracao.wav')
    HF.gravar_wav(HF.AUDIO / 'trilha.wav', np.zeros(int(dur * SR), np.float32), SR, estereo=True)
    HF.gravar_wav(HF.AUDIO / 'whoosh.wav', np.zeros(int(dur * SR), np.float32), SR, estereo=True)

    extras = json.loads((DUPLA / 'figurantes.json').read_text(encoding='utf-8'))
    html = html_dupla(pacote, falante, [[c['start'], c['value']] for c in cues[outro]], extras, outro)
    (AQUI / 'index.html').write_text(html, encoding='utf-8')
    (HF.BUILD / 'pacote.json').write_text(json.dumps(pacote, ensure_ascii=False, indent=1), encoding='utf-8')
    (work / 'sfx_usados.json').write_text(json.dumps(sx.usados, indent=1))
    print(f'index.html da dupla — {dur:.1f}s | {lider} apresenta, {outro} acompanha | '
          f'cenas: {" > ".join(c["tipo"] for c in cenas)} | {len(sx.usados)} efeitos sonoros')
    return pacote, bat


def render_brief_dupla(brief, destino, qualidade='standard'):
    """Mesma interface do scripts.produce.render_brief (formato solo)."""
    out = Path(destino)
    pacote, bat = preparar_dupla(brief, out)
    out.with_suffix('.json').write_text(json.dumps(bat, ensure_ascii=False, indent=2))
    out.with_suffix('.txt').write_text(brief['caption'])
    return HF.renderizar(out, pacote, qualidade)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--ilustrativo', choices=('hoje', 'amanhã'), required=True,
                    help='teste visual com dados ilustrativos (nunca publicar)')
    ap.add_argument('--data-pub', default=dt.date.today().isoformat())
    ap.add_argument('--qualidade', default='standard', choices=['draft', 'standard', 'high'])
    a = ap.parse_args()
    render_brief_dupla(brief_ilustrativo(a.ilustrativo, a.data_pub), a.out, a.qualidade)
    print(f'ok: {a.out}')


if __name__ == '__main__':
    main()

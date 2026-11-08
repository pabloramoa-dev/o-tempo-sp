"""Lip sync DVH: boca por visema (Rhubarb) + updater que segue o personagem."""
import json
from manim import *

import os
LIP_JSON = os.environ.get('OTEMPOSP_LIP_JSON', 'lip_full.json')
CUES = json.load(open(LIP_JSON))['mouthCues'] if os.path.exists(LIP_JSON) else []
PT2 = "#1a1a1a"
VINHO = "#7a1f2a"
LINGUA = "#d96a6a"


def boca_visema(v):
    if v in ('X', 'A'):
        m = Line(LEFT*0.16, RIGHT*0.16, stroke_color=PT2, stroke_width=8)
    elif v == 'B':
        m = VGroup(
            Ellipse(width=0.34, height=0.14, stroke_color=PT2, stroke_width=7,
                    fill_color=WHITE, fill_opacity=1),
            Line(LEFT*0.15, RIGHT*0.15, stroke_color="#bbb", stroke_width=3))
    elif v == 'C':
        m = Ellipse(width=0.34, height=0.26, stroke_color=PT2, stroke_width=7,
                    fill_color=VINHO, fill_opacity=1)
    elif v == 'D':
        m = VGroup(
            Ellipse(width=0.42, height=0.4, stroke_color=PT2, stroke_width=7,
                    fill_color=VINHO, fill_opacity=1),
            Arc(radius=0.13, start_angle=PI, angle=PI, stroke_width=0,
                fill_color=LINGUA, fill_opacity=1).shift(DOWN*0.11))
    elif v == 'E':
        m = Ellipse(width=0.26, height=0.3, stroke_color=PT2, stroke_width=7,
                    fill_color=VINHO, fill_opacity=1)
    elif v == 'F':
        m = Circle(radius=0.11, stroke_color=PT2, stroke_width=7,
                   fill_color=VINHO, fill_opacity=1)
    elif v == 'G':
        m = VGroup(
            Ellipse(width=0.3, height=0.16, stroke_color=PT2, stroke_width=7,
                    fill_color=VINHO, fill_opacity=1),
            Rectangle(width=0.2, height=0.06, stroke_width=0,
                      fill_color=WHITE, fill_opacity=1).shift(UP*0.03))
    else:  # H
        m = VGroup(
            Ellipse(width=0.34, height=0.3, stroke_color=PT2, stroke_width=7,
                    fill_color=VINHO, fill_opacity=1),
            Ellipse(width=0.15, height=0.11, stroke_width=0,
                    fill_color=LINGUA, fill_opacity=1).shift(DOWN*0.05))
    return VGroup(m)


def anexar_lipsync(scene, ref, t0, escala=1.0, deslocamento=None):
    """Boca sincronizada: `ref` é o mobject da boca original (fica invisível),
    t0 é o tempo do início do trecho na narração completa."""
    if deslocamento is None:
        deslocamento = ORIGIN
    cues = [c for c in CUES if c['end'] > t0 - 0.05]
    relogio = {'t': t0}
    estado = {'v': 'X'}
    boca = boca_visema('X')
    boca.scale(escala).move_to(ref.get_center() + deslocamento)

    def upd(mo, dt):
        relogio['t'] += dt
        t = relogio['t']
        v = 'X'
        for c in cues:
            if c['start'] <= t < c['end']:
                v = c['value']; break
            if c['start'] > t:
                break
        if v != estado['v']:
            mo.become(boca_visema(v).scale(escala))
            estado['v'] = v
        mo.move_to(ref.get_center() + deslocamento)

    boca.add_updater(upd)
    scene.add(boca)
    return boca



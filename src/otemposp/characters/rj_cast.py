"""Elenco original RJ em geometria vetorial; interface compatível com o motor."""
from manim import *
import numpy as np

config.frame_width = 8.0
config.frame_height = 14.222

INK = '#122E43'
TEAL = '#007F87'
YELLOW = '#FFD166'


def shape(cls, color, **kw):
    return cls(fill_color=color, fill_opacity=1, stroke_color=INK, stroke_width=5, **kw)


def presenter(name='bira'):
    bia = name == 'bia'
    skin = '#C78359' if bia else '#A96D49'
    shirt = '#843952' if bia else '#213956'
    hair_color = '#392D32'
    back_hair = shape(RoundedRectangle, hair_color, width=1.95, height=2.1, corner_radius=.65).move_to([0, 1.2, 0]) if bia else VGroup()
    shoes = VGroup(*[shape(RoundedRectangle, '#F6F2E8', width=.68, height=.3, corner_radius=.12).move_to([x, -2.12, 0]) for x in [-.43, .43]])
    legs = VGroup(*[shape(RoundedRectangle, '#234B67', width=.48, height=1.15, corner_radius=.12).move_to([x, -1.5, 0]) for x in [-.4, .4]])
    body = shape(RoundedRectangle, shirt, width=1.55, height=1.65, corner_radius=.32).move_to([0, -.38, 0])
    neck = shape(RoundedRectangle, skin, width=.47, height=.58, corner_radius=.16).move_to([0, .55, 0])
    head = shape(RoundedRectangle, skin, width=1.72, height=1.9, corner_radius=.67).move_to([0, 1.5, 0])
    ears = VGroup(*[shape(Circle, skin, radius=.18).move_to([x, 1.45, 0]) for x in [-.86, .86]])
    hair = VGroup(*[shape(Circle, hair_color, radius=r).move_to([x, y, 0]) for x, y, r in [(-.57, 2.27, .34), (-.2, 2.42, .4), (.23, 2.41, .37), (.57, 2.22, .3)]])
    if bia:
        hair.add(shape(Circle, hair_color, radius=.45).move_to([.85, 2.33, 0]))
        hair.add(Line([.61,2.44,0],[.88,2.57,0],stroke_color=TEAL,stroke_width=10))
    eyes = []
    brows = []
    for x in [-.34, .34]:
        eye = VGroup(shape(Ellipse, WHITE, width=.35, height=.43).move_to([x,1.55,0]),
                     Dot([x+.025,1.54,0],radius=.085,color=INK), Dot([x+.05,1.58,0],radius=.023,color=WHITE))
        eyes.append(eye)
        brows.append(Line([x-.16,1.92,0],[x+.16,1.95,0],stroke_color=INK,stroke_width=7))
    nose = ArcBetweenPoints([.01,1.42,0],[.13,1.22,0],angle=-.8,stroke_color='#754A38',stroke_width=4)
    mouth = ArcBetweenPoints([-.22,1.04,0],[.22,1.04,0],angle=1,stroke_color=INK,stroke_width=5)
    hands = [shape(Circle, skin, radius=.22).move_to([x,-.73,0]) for x in [-1.05,1.05]]
    arms = [Line([x*.7,.14,0],h.get_center(),stroke_color=skin,stroke_width=24) for x,h in zip([-1,1],hands)]
    logo = Text('SP', font_size=22, weight=BOLD, color=INK if bia else WHITE).move_to([.28,-.12,0])
    collar = VGroup(Line([-.26,.4,0],[0,.15,0],stroke_color=INK,stroke_width=4),Line([0,.15,0],[.26,.4,0],stroke_color=INK,stroke_width=4))
    lapels = VGroup(*[Polygon([side*.58,.32,0],[side*.22,.36,0],[0,-.42,0],fill_color="#DADCE1",fill_opacity=1,stroke_width=0) for side in (-1,1)])
    group = VGroup(*([back_hair] if bia else []), legs, shoes, *arms, body, neck, ears, head, hair, *eyes, *brows, nose, mouth, collar, lapels, logo, *hands)
    result = dict(grupo=group,cab=head,oe=eyes[0],od=eyes[1],boca=mouth,maoE=hands[0],maoD=hands[1],bracoE=arms[0],bracoD=arms[1],sobE=brows[0],sobD=brows[1])
    result.update(cabeca=head,olho_e=eyes[0],olho_d=eyes[1],mao_e=hands[0],mao_d=hands[1])
    return result


EXPRESSIONS = ('neutra', 'atenta', 'desconfiada', 'animada', 'preocupada')


def expression(character, mood='neutra'):
    """Expressão baseada na geometria atual; não acumula rotações."""
    if mood not in EXPRESSIONS: raise ValueError('Expressão desconhecida')
    center = character['cab'].get_center()
    scale = character['cab'].width / 1.72
    slopes = {'neutra':(.03,.03), 'atenta':(.03,-.03), 'desconfiada':(-.15,-.04),
              'animada':(.12,-.12), 'preocupada':(.14,-.14)}[mood]
    for side,x,slope in zip(('E','D'),(-.34,.34),slopes):
        y = .56 if mood in {'atenta','animada'} else .42
        character['sob'+side].become(Line(center+np.array([x-.16,y-slope/2,0])*scale,
            center+np.array([x+.16,y+slope/2,0])*scale,stroke_color=INK,stroke_width=7))
    angle = -.9 if mood=='preocupada' else 1.5 if mood=='animada' else .6
    character['boca'].become(ArcBetweenPoints(center+np.array([-.22,-.46,0])*scale,
        center+np.array([.22,-.46,0])*scale,angle=angle,stroke_color=INK,stroke_width=5))
    return character


def blink(character, period=4.2):
    """Piscar determinístico; fator absoluto evita deformação acumulada."""
    for key in ('oe','od'):
        state={'t':0., 'factor':1.}
        def update(eye,dt,state=state):
            state['t']+=dt
            phase=state['t']%period
            f=max(.08,abs(phase-.12)/.12) if phase<.24 else 1.
            eye.stretch(f/state['factor'],1,about_point=eye.get_center())
            state['factor']=f
        character[key].add_updater(update)



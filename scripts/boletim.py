"""Cena vertical com o elenco vetorial original."""
import json
import wave
import numpy as np
from manim import *
from src.otemposp.characters.rj_cast import presenter, blink, expression
from src.otemposp.characters.director import planejar
from src.otemposp.characters.acting_manim import anexar_mao_livre

class Boletim(Scene):
    def construct(self):
        brief = json.load(open("output/brief.json"))
        morning = brief["when"] == "hoje"
        name = "bira" if morning else "bia"
        self.camera.background_color = "#294961" if morning else "#1D2740"
        for i,h in enumerate([2,3,2.6,3.8,2.2,3.2,2,2.9,3.6,2.5]):
            x = -3.65+i*.81
            self.add(Rectangle(width=.75,height=h,color="#537389",fill_opacity=1,stroke_width=0).move_to([x,1+h/2,0]))
        if morning:  # Vão livre e pórticos vermelhos do MASP na Paulista
            self.add(Rectangle(width=3.3,height=.8,color="#9DB9C3",fill_opacity=1).move_to([-1.7,2.3,0]))
            for x in (-3.2,-.2):
                self.add(Line([x,1,0],[x,3.1,0],color="#E44845",stroke_width=12))
        else:
            for x in (-.9,.9):
                self.add(Line([x,1,0],[-x,3.9,0],color="#DBD2B7",stroke_width=9))
            for x in np.linspace(-3.6,3.6,16):
                self.add(Line([0,3.6,0],[x,1.25,0],color="#C0CCD0",stroke_width=2))
        def label(value,y,size,color=WHITE):
            obj=Text(value,font_size=size,color=color)
            if obj.width>7: obj.scale_to_fit_width(7)
            self.add(obj.move_to([0,y,0]))
        label("O TEMPO SP",5.85,50)
        label(("MANHÃ  /  BIRA" if morning else "AMANHÃ  /  BIA")+"   •   "+brief["date"],5.05,26)
        v=expression(presenter(name),"atenta")
        v["grupo"].scale(.88).move_to([0,1.8,0])
        blink(v)
        times=json.load(open("output/segments.json"))
        plan=planejar([{"fala":t["texto"]} for t in times],times,name)
        anexar_mao_livre(v,plan,.88)
        for side in ("E","D"):
            arm=v["braco"+side]; start=arm.get_start().copy()
            arm.add_updater(lambda m,dt,side=side,start=start:m.put_start_and_end_on(start,v["mao"+side].get_center()))
        with wave.open("output/voice.wav") as w:
            rate=w.getframerate()
            samples=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").astype(float)
        mouth=v["boca"]; center=mouth.get_center(); clock=[0.]
        def speak(m,dt):
            clock[0]+=dt
            chunk=samples[int(clock[0]*rate):int((clock[0]+.05)*rate)]
            height=.035+min(.22,np.mean(abs(chunk))/14000) if len(chunk) else .035
            m.become(Ellipse(width=.36,height=height,fill_color="#52323C",fill_opacity=1,stroke_width=2).move_to(center))
        mouth.add_updater(speak)
        self.add(v["grupo"])
        label("AVENIDA PAULISTA" if morning else "PONTE ESTAIADA",-.65,20,"#FFD166")
        for i,card in enumerate(brief["cards"]):
            label(f"{card['short']}    {card['min_c']:g}° / {card['max_c']:g}°    •    chuva {card['rain_pct']:g}%",-1.35-i*.43,20)
        label("@otemposp", -5.25,25)
        if brief["is_fixture"]: label("PILOTO  •  DADOS SIMULADOS",-5.85,18,"#FFD166")
        self.add_sound("output/voice.wav")
        self.wait(len(samples)/rate)

"""Gesto do braço esquerdo para o motor Manim de reserva.

O braço já segue a mão via visual.conectar_bracos(); esta rotina desloca só a
mão livre com deltas reversíveis. Não interfere nos painéis, na boca ou no
braço direito (que aponta para dados).
"""
from __future__ import annotations

from . import director


def anexar_mao_livre(personagem, plano, escala=1.0):
    if not plano or "maoE" not in personagem:
        return
    mao = personagem["maoE"]
    estado = {"tempo": 0., "dx": 0., "dy": 0.}

    def animar(mob, dt):
        estado["tempo"] += dt
        t = estado["tempo"]
        item = next((p for p in plano if p["inicio"] <= t < p["fim"]), None)
        dx, dy = (director.deslocamento(
            item["gesto"], t, item["inicio"], item["fim"], item["energia"])
            if item else (0., 0.))
        # Uso de delta evita saltos e sobreposição com o updater de respiração.
        mob.shift([(dx - estado["dx"])*escala, (dy - estado["dy"])*escala, 0])
        estado["dx"], estado["dy"] = dx, dy

    mao.add_updater(animar)


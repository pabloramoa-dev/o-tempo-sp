"""Direção por fala de Bira/Bia, gratuita e determinística.

Não altera texto, número meteorológico, voz ou horário.
Controla somente a postura e a câmera do apresentador, nunca os painéis.
"""
from __future__ import annotations

import math
import os
import re

GESTOS = ("repouso", "explicar", "apontar", "enfatizar", "alertar", "acolher", "perguntar")
ANGULOS = {
    "repouso": 0, "explicar": -7, "apontar": -12,
    "enfatizar": -10, "alertar": -16, "acolher": -5, "perguntar": -10,
}
CAMERAS = {
    "aproximar": 1.060,
    "aproximar_suave": 1.035,
    "abrir": 1.0,
    "estabilizar": 1.0,
    "manter": 1.015,
}


def ativo() -> bool:
    return os.environ.get("OTEMPOSP_DIRECAO", "1").strip().lower() not in {"0", "false", "nao", "não"}


def gesto_da_batida(b: dict, indice: int, personagem: str) -> str:
    """Escolha interpretável que respeita a função informativa do boletim."""
    explicito = str(b.get("gesto") or "").strip().lower()
    if explicito in GESTOS:
        return explicito
    tipo = str(b.get("tipo", "nenhum"))
    fala = str(b.get("fala", ""))
    dados = b.get("dados") if isinstance(b.get("dados"), dict) else {}
    if tipo == "alerta" or re.search(r"\b(atenção|alerta|temporal|tempestade)\b", fala, re.I):
        return "alertar"
    if tipo in ("numero", "gancho", "abertura"):
        return "enfatizar"
    if tipo in ("quadro", "resumo", "cidade", "duas_cidades"):
        return "apontar"
    if tipo in ("cta", "fecho"):
        return "perguntar" if "?" in fala else "acolher"
    if "?" in fala:
        return "perguntar"
    if dados.get("cor") == "alerta":
        return "alertar"
    return ("explicar", "repouso", "acolher")[indice % 3]


def planejar(batidas: list[dict], tempos: list[dict], personagem: str) -> list[dict]:
    if personagem not in {"bira", "bia", "ranzinza", "maria"}:
        raise ValueError("Personagem não reconhecido na direção RJ")
    if not batidas or len(batidas) != len(tempos):
        raise ValueError("Número de batidas/segmentos divergente")
    plano = []
    anterior = -1.0
    for i, (batida, tempo) in enumerate(zip(batidas, tempos)):
        ini, fim = float(tempo["ini"]), float(tempo["fim"])
        if not all(math.isfinite(z) for z in (ini, fim)) or ini < 0 or fim <= ini or ini < anterior - .002:
            raise ValueError(f"Timeline inválida na batida {i}")
        tipo = str(batida.get("tipo", "nenhum"))
        gesto = gesto_da_batida(batida, i, personagem)
        camera = ("aproximar" if tipo in {"numero", "gancho", "alerta", "abertura"} else
                  "abrir" if tipo in {"resumo", "quadro"} else
                  "estabilizar" if tipo in {"cta", "fecho"} else
                  "aproximar_suave" if gesto in {"alertar", "enfatizar"} else "manter")
        plano.append(dict(i=i, inicio=round(ini, 3), fim=round(fim, 3),
                          gesto=gesto, camera=camera, tipo=tipo,
                          energia=.83 if personagem in {"bia", "maria"} else 1.0))
        anterior = fim
    return plano


def deslocamento(gesto: str, t: float, inicio: float, fim: float, energia=1.0):
    """Movimento suave de mão livre para o motor Manim de reserva."""
    if gesto not in ANGULOS or not inicio <= t < fim:
        return (0., 0.)
    rampa = min(.32, (fim-inicio)/3)
    if rampa <= 0:
        return (0., 0.)
    q = min(1., max(0., (t-inicio)/rampa), max(0., (fim-t)/rampa))
    q = q*q*(3-2*q)
    amp = ANGULOS[gesto] / -16
    return (-.22*q*amp*energia, .22*q*amp*energia)


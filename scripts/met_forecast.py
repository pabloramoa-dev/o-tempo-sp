"""Previsão da MET Norway para o boletim paulista — atalho para o motor único.

Toda a lógica (horas, chuva, céu, umidade, altitude, validade da rodada) fica em
src/otemposp/weather.py, que é o código coberto pelos testes. Este módulo só
mantém a interface usada por scripts/live.py e scripts/distribute.py.
"""
from src.otemposp.weather import MET_ENDPOINT, MET_SOURCE, collect as _collect

ENDPOINT = MET_ENDPOINT
SOURCE = MET_SOURCE


def collect(offset, session=None):
    """offset 0 = hoje (da hora atual às 24h); 1 = amanhã (24 horas completas).

    Coleta os 18 pontos (8 âncoras do quadro + 10 de contraste, como
    Parelheiros, Marsilac e Cidade Tiradentes).
    """
    return _collect(tier=2, day_offset=int(offset), session=session, source="met_no")

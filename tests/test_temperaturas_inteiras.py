"""Regressão: nunca narrar décimos; vídeo, quadro e legenda com o MESMO número."""
import re

from scripts.produce import pauta as pauta_producao
from scripts.live import pauta as pauta_live
from src.otemposp.editorial import summarise
from src.otemposp.geo import locations
from src.otemposp.temperatura import graus_inteiros


def snapshot():
    points = []
    for i, local in enumerate(locations(1)):
        points.append(dict(
            id=local["id"], name=local["name"], sector=local["sector"],
            min_c=12.9 if i == 0 else 11.4,
            max_c=17.6 if i == 0 else 15.4,
            rain_probability_pct=None, rain_mm=0.0,
        ))
    return dict(is_fixture=True, forecast_date="2026-11-09",
                source="MET Norway", points=points)


def test_arredondamento_convencional():
    assert graus_inteiros(17.4) == 17
    assert graus_inteiros(17.5) == 18
    assert graus_inteiros(17.6) == 18
    assert graus_inteiros(33.9) == 34
    assert graus_inteiros(-0.4) == 0


def test_mesmo_numero_na_voz_no_quadro_e_na_legenda():
    brief = summarise(snapshot(), alertas=[])
    assert "18 graus" in brief["script"]
    assert "17.6" not in brief["script"] and "17,6" not in brief["script"]
    assert "Santana: 13° / 18°" in brief["caption"]
    assert re.search(r"Maior máxima: Santana, 18°", brief["caption"])
    for roteiro in (pauta_producao, pauta_live):
        beats, cidades = roteiro(brief)
        falas = " ".join(b["fala"] for b in beats)
        assert "18 graus" in falas
        assert "17.6" not in falas and "17,6" not in falas
        assert "17 graus" not in falas
        assert len(cidades) == 8
        assert all(isinstance(c["min"], int) and isinstance(c["max"], int) for c in cidades)
        santana = next(c for c in cidades if c["nome"] == "Santana")
        assert (santana["min"], santana["max"]) == (13, 18)

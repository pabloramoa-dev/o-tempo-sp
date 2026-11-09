"""Regressão: jamais narrar décimos de temperatura, nem arredondar 17,6 para 18."""
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


def test_decimais_sao_descartados_na_voz():
    assert graus_inteiros(17.6) == 17
    assert graus_inteiros(17.9) == 17
    assert graus_inteiros(17.0) == 17
    brief = summarise(snapshot())
    assert "17 graus" in brief["script"]
    assert "17.6" not in brief["script"] and "17,6" not in brief["script"]
    for roteiro in (pauta_producao, pauta_live):
        beats, cidades = roteiro(brief)
        falas = " ".join(b["fala"] for b in beats)
        assert "17 graus" in falas
        assert "17.6" not in falas and "17,6" not in falas
        assert "18 graus" not in falas
        assert len(cidades) == 11
        assert all(isinstance(c["min"], int) and isinstance(c["max"], int) for c in cidades)

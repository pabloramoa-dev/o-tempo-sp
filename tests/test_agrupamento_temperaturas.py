"""Temperaturas repetidas são narradas uma só vez, em qualquer região."""
from copy import deepcopy

import pytest

from scripts.produce import pauta as pauta_producao
from scripts.live import pauta as pauta_live
from src.otemposp.temperatura import (agrupar_cidades_por_faixa, frase_faixa,
                                     graus_inteiros, juntar_nomes)


def brief_com_faixas(pares):
    nomes = ["Santana", "Pirituba", "Sé", "Pinheiros",
             "Tatuapé", "Itaquera", "Vila Mariana", "Santo Amaro"]
    assert len(pares) == len(nomes)
    cards = [
        dict(point=nome, short=nome.upper(), min_c=float(minima),
             max_c=float(maxima), rain_pct=None, rain_mm=0.0)
        for nome, (minima, maxima) in zip(nomes, pares)
    ]
    return dict(cards=cards, when="hoje",
                hottest=max(cards, key=lambda c: c["max_c"]),
                wettest=cards[0], is_fixture=True)


@pytest.mark.parametrize("pauta", [pauta_producao, pauta_live])
def test_group_cities_from_different_visual_pages(pauta):
    # Pirituba e Sé ficam no primeiro bloco original; Santo Amaro, no segundo.
    pares = [(16, 25), (17.6, 28.9), (17.1, 28.2), (18, 29),
             (19, 30), (20, 31), (21, 32), (17.9, 28.1)]
    brief = brief_com_faixas(pares)
    original = deepcopy(brief["cards"])
    beats, cities = pauta(brief)
    textos = [b["fala"] for b in beats if b["tipo"] == "resumo"]
    juntos = " ".join(textos)
    assert "Pirituba, Sé e Santo Amaro, de 17 a 28 graus." in juntos
    assert juntos.count("de 17 a 28 graus") == 1
    assert len(cities) == 8
    assert brief["cards"] == original
    assert "17.6" not in juntos and "17,6" not in juntos
    quadros = [g for b in beats if b["tipo"] == "resumo" for g in b["dados"]["cidades"]]
    assert len(quadros) == 6  # 8 cidades, 6 faixas, sem repetir a temperatura
    assert any(g["nome"] == "Pirituba, Sé e Santo Amaro" and g["min"] == 17
               and g["max"] == 28 for g in quadros)
    assert len({nome for g in quadros for nome in g["nomes"]}) == 8


@pytest.mark.parametrize("pauta", [pauta_producao, pauta_live])
def test_group_only_if_both_min_and_max_match(pauta):
    pares = [(17, 28), (17, 29), (18, 28), (17, 28),
             (17, 29), (18, 28), (17, 27), (17, 27)]
    beats, cities = pauta(brief_com_faixas(pares))
    groups = [g for b in beats if b["tipo"] == "resumo" for g in b["dados"]["cidades"]]
    assert len(groups) == 4
    assert any(g["nome"] == "Santana e Pinheiros" and g["min"] == 17 and g["max"] == 28
               for g in groups)
    assert any(g["nome"] == "Pirituba e Tatuapé" and g["min"] == 17 and g["max"] == 29
               for g in groups)
    assert len(cities) == 8


@pytest.mark.parametrize("pauta", [pauta_producao, pauta_live])
def test_if_all_eight_same_interval_only_one_summary(pauta):
    beats, _ = pauta(brief_com_faixas([(17.8, 28.9)] * 8))
    summaries = [b for b in beats if b["tipo"] == "resumo"]
    assert len(summaries) == 1
    assert summaries[0]["fala"].count("de 17 a 28 graus") == 1
    assert len(summaries[0]["dados"]["cidades"]) == 1
    assert len(summaries[0]["dados"]["cidades"][0]["nomes"]) == 8


def test_helpers_for_single_and_multiple_localities():
    assert juntar_nomes(["Sé"]) == "Sé"
    assert juntar_nomes(["Sé", "Pirituba"]) == "Sé e Pirituba"
    with pytest.raises(ValueError):
        juntar_nomes([])
    cidades = [dict(nome="Sé", min=17.6, max=28.9),
               dict(nome="Pirituba", min=17.1, max=28.3)]
    groups = agrupar_cidades_por_faixa(cidades)
    assert frase_faixa(groups[0]) == "Sé e Pirituba, de 17 a 28 graus."
    assert graus_inteiros(17.9) == 17

"""Chuva: só vira destaque quando é chuva de verdade; relevante abre o vídeo."""
import copy

import pytest

from scripts.live import pauta as pauta_live
from scripts.produce import pauta as pauta_producao
from src.otemposp.chuva import maior_chuva, classificar, janela_de_chuva, texto_janela


def brief(volumes, quando="amanhã", janela=None):
    nomes = ["Santana", "Pirituba", "Sé", "Pinheiros",
             "Tatuapé", "Itaquera", "Vila Mariana", "Santo Amaro"]
    assert len(volumes) == len(nomes)
    cards = [dict(point=nome, short=nome.upper(),
                  min_c=17.5, max_c=28.8, rain_pct=None, rain_mm=valor, rain_window=janela)
             for nome, valor in zip(nomes, volumes)]
    return dict(cards=cards, when=quando, hottest=cards[0], wettest=cards[0],
                is_fixture=True)


def test_faixas():
    assert classificar(0) == "seco" and classificar(0.4) == "seco"
    assert classificar(0.5) == "fraca" and classificar(1.9) == "fraca"
    assert classificar(2) == "moderada" and classificar(9.9) == "moderada"
    assert classificar(10) == "forte"


@pytest.mark.parametrize("pauta", [pauta_producao, pauta_live])
def test_chuva_moderada_abre_o_video_e_cta_fecha(pauta):
    data = brief([1, 3, 2, 4, 5.7, 4.1, 0, 1], janela=(15, 18))
    prev = copy.deepcopy(data)
    beats, cities = pauta(data)
    assert beats[1]["tipo"] == "gancho"
    assert beats[1]["fala"] == "Tatuapé pode ter até 6 milímetros de chuva amanhã entre 15 e 18 horas."
    assert beats[1]["dados"]["numero"] == "6 mm"
    assert beats[1]["dados"]["local"] == "Tatuapé"
    assert beats[-1]["tipo"] == "cta"
    assert len([b for b in beats if "milímetros" in b["fala"]]) == 1
    assert data == prev
    assert len(cities) == 8


@pytest.mark.parametrize("pauta", [pauta_producao, pauta_live])
def test_chuvisco_nao_vira_manchete(pauta):
    beats, _ = pauta(brief([0, 0.2, 0, 0, 0, 0, 0.3, 0]))
    assert beats[1]["dados"]["sub"] == "MAIOR MÁXIMA"
    assert not any("milímetro" in b["fala"] for b in beats)
    assert any(b["fala"] == "Sem chuva significativa prevista amanhã nos pontos acompanhados." for b in beats)
    assert beats[-1]["tipo"] == "cta"


@pytest.mark.parametrize("pauta", [pauta_producao, pauta_live])
def test_chuva_fraca_e_informada_sem_numero(pauta):
    beats, _ = pauta(brief([0, 1.2, 0, 0, 0, 0, 0, 0], "hoje"))
    assert beats[1]["dados"]["sub"] == "MAIOR MÁXIMA"
    assert any(b["fala"] == "Pirituba pode ter garoa ou chuva fraca hoje." for b in beats)


@pytest.mark.parametrize("pauta", [pauta_producao, pauta_live])
def test_no_mm_data_never_claims_dry_forecast(pauta):
    data = brief([0] * 8)
    for card in data["cards"]:
        card["rain_mm"] = None
    beats, _ = pauta(data)
    assert not any("chuva" in b["fala"].lower() for b in beats)
    assert beats[-1]["tipo"] == "cta"


def test_chuva_forte_usa_atencao():
    sel = maior_chuva(brief([0, 0, 12.2, 0, 0, 0, 0, 0])["cards"], "hoje")
    assert sel["classe"] == "forte" and sel["mm_fala"] == 13
    assert sel["fala"].startswith("Atenção: Sé pode ter chuva forte hoje")


def test_max_uses_raw_values_not_rounded_and_tie_is_stable():
    data = brief([0, 0, 0, 0, 6.01, 6.02, 0, 0])
    selected = maior_chuva(data["cards"], "amanhã")
    assert selected["point"] == "Itaquera"
    assert selected["mm_fala"] == 7  # não subestimar o volume ao falar "até"
    data["cards"][4]["rain_mm"] = 6.02
    assert maior_chuva(data["cards"], "amanhã")["point"] == "Tatuapé"
    assert selected["locais_com_chuva"] == 2


def test_janela_de_chuva():
    assert janela_de_chuva([(14, 0.1), (15, 1.0), (16, 2.0), (18, 0.5), (22, 0.3)]) == (15, 19)
    assert janela_de_chuva([(3, 0.0)]) is None
    assert texto_janela((15, 18)) == "entre 15 e 18 horas"
    assert texto_janela((20, 24)) == "a partir das 20 horas"
    assert texto_janela((15, 18), falado=False) == "15h–18h"
    assert texto_janela((6, 22)) == "ao longo do dia"


def test_reject_invalid_weather_values_and_unknown_period():
    data = brief([0] * 8)
    data["cards"][0]["rain_mm"] = -1
    with pytest.raises(ValueError):
        maior_chuva(data["cards"], "amanhã")
    with pytest.raises(ValueError):
        maior_chuva(brief([0] * 8)["cards"], "semana passada")

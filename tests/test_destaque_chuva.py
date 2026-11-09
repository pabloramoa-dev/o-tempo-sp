"""Somente o maior acumulado no fechamento, em todas as 11 áreas."""
import copy
import pytest
from scripts.live import pauta as pauta_live
from scripts.produce import pauta as pauta_producao
from src.otemposp.chuva import maior_chuva
from src.otemposp.geo import locations, sectors

def brief(volumes, quando="amanhã"):
    pontos = locations(1)
    assert len(volumes) == len(pontos) == 11
    cards = [dict(point=p["name"], sector=p["sector"], short=sectors()[p["sector"]]["short"],
                  min_c=17.5, max_c=28.8, rain_pct=None, rain_mm=valor)
             for p,valor in zip(pontos,volumes)]
    return dict(cards=cards, when=quando, hottest=cards[0], wettest=cards[0],
                is_fixture=True)

@pytest.mark.parametrize("pauta",[pauta_producao,pauta_live])
def test_only_highest_rain_closes_video(pauta):
    data = brief([1,3,2,4,5.7,4.1,0,1,0,0,0])
    prev = copy.deepcopy(data)
    beats, cities = pauta(data)
    assert beats[-1]["tipo"] == "gancho"
    assert beats[-1]["fala"] == "Tatuapé poderá ter até 6 milímetros de chuva amanhã."
    assert beats[-1]["dados"]["numero"] == "6 mm"
    assert beats[-1]["dados"]["local"] == "Tatuapé"
    assert beats[-2]["tipo"] == "cta"
    assert len([b for b in beats if "chuva" in b["fala"].lower()]) == 1
    assert data == prev
    assert len(cities) == 11

@pytest.mark.parametrize("pauta", [pauta_producao,pauta_live])
@pytest.mark.parametrize("quando",["hoje","amanhã"])
def test_dry_forecast_closes_with_zero_mm_in_voice_and_screen(pauta, quando):
    beats, _ = pauta(brief([0]*11,quando))
    assert beats[-2]["tipo"] == "cta"
    assert beats[-1]["tipo"] == "gancho"
    assert beats[-1]["fala"] == f"Nos onze locais acompanhados, não há chuva prevista {quando}."
    assert beats[-1]["dados"] == {"numero":"0 mm","sub":"SEM CHUVA PREVISTA","local":"11 LOCAIS MONITORADOS"}
    assert not any("milímetros" in b["fala"] for b in beats)

@pytest.mark.parametrize("pauta", [pauta_producao,pauta_live])
def test_no_mm_data_never_claims_dry_forecast(pauta):
    data=brief([0]*11)
    for card in data["cards"]:
        card["rain_mm"]=None
    beats,_=pauta(data)
    assert beats[-1]["tipo"]=="cta"

def test_max_uses_raw_values_not_rounded_and_tie_is_stable():
    data=brief([0,0,0,0,6.01,6.02,0,0,0,0,0])
    selected=maior_chuva(data["cards"],"amanhã")
    assert selected["point"]=="Itaquera"
    assert selected["mm_fala"]==7
    data["cards"][4]["rain_mm"]=6.02
    assert maior_chuva(data["cards"],"amanhã")["point"]=="Tatuapé"

def test_today_and_singular_mm():
    data=brief([0,0.2,0,0,0,0,0,0,0,0,0],"hoje")
    assert maior_chuva(data["cards"],"hoje")["fala"]=="Pirituba poderá ter até 1 milímetro de chuva hoje."

def test_reject_invalid_weather_values_and_unknown_period():
    data=brief([0]*11)
    data["cards"][0]["rain_mm"]=-1
    with pytest.raises(ValueError):
        maior_chuva(data["cards"],"amanhã")
    with pytest.raises(ValueError):
        maior_chuva(brief([0]*11)["cards"],"semana passada")

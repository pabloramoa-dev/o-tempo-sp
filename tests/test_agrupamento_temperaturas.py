"""Narrar intervalos comuns sem fundir localidades na imagem."""
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
    cards = [dict(point=nome, short=nome.upper(), min_c=float(minima),
                  max_c=float(maxima), rain_pct=None, rain_mm=0)
             for nome, (minima, maxima) in zip(nomes, pares)]
    return dict(cards=cards, when="hoje", hottest=max(cards, key=lambda c:c["max_c"]),
                wettest=cards[0], is_fixture=True)


def linhas(beats):
    return [cidade for b in beats if b["tipo"]=="resumo"
            for cidade in b["dados"]["cidades"]]


@pytest.mark.parametrize("pauta", [pauta_producao,pauta_live])
def test_grouped_speech_and_separate_rows_even_across_old_page_split(pauta):
    pares = [(16,25),(16.6,28.4),(17.1,27.6),(18,29),
             (19,30),(20,31),(21,32),(17.4,28.1)]
    brief=brief_com_faixas(pares)
    old=deepcopy(brief["cards"])
    beats,cities=pauta(brief)
    summaries=[b for b in beats if b["tipo"]=="resumo"]
    joined=" ".join(b["fala"] for b in summaries)
    assert "Pirituba, Sé e Santo Amaro, de 17 a 28 graus." in joined
    assert joined.count("de 17 a 28 graus") == 1
    rows=linhas(beats)
    assert len(rows)==8 and len(cities)==8
    assert len({x["nome"] for x in rows})==8
    assert {x["nome"] for x in rows}=={x["nome"] for x in cities}
    assert all(x["nome"] in [c["point"] for c in old] for x in rows)
    matching=next(b for b in summaries if "Pirituba, Sé e Santo Amaro" in b["fala"])
    assert {"Pirituba","Sé","Santo Amaro"}.issubset({x["nome"] for x in matching["dados"]["cidades"]})
    assert len([x for x in rows if x["min"]==17 and x["max"]==28])==3
    assert brief["cards"]==old


@pytest.mark.parametrize("pauta",[pauta_producao,pauta_live])
def test_only_group_same_min_and_max(pauta):
    pares=[(17,28),(17,29),(18,28),(17,28),(17,29),(18,28),(17,27),(17,27)]
    beats,cities=pauta(brief_com_faixas(pares))
    spoken=" ".join(b["fala"] for b in beats if b["tipo"]=="resumo")
    assert "Santana e Pinheiros, de 17 a 28 graus" in spoken
    assert "Pirituba e Tatuapé, de 17 a 29 graus" in spoken
    assert "Sé e Itaquera, de 18 a 28 graus" in spoken
    assert len(linhas(beats))==8 and len(cities)==8


@pytest.mark.parametrize("pauta",[pauta_producao,pauta_live])
def test_all_eight_identical_are_still_eight_visible_lines(pauta):
    beats,_=pauta(brief_com_faixas([(17.8,28.9)]*8))
    summaries=[b for b in beats if b["tipo"]=="resumo"]
    assert len(summaries)==1
    assert summaries[0]["fala"].count("de 18 a 29 graus")==1
    assert len(summaries[0]["dados"]["cidades"])==8


@pytest.mark.parametrize("pauta",[pauta_producao,pauta_live])
def test_individual_temperature_pages_have_four_lines(pauta):
    pairs=[(10+i,20+i) for i in range(8)]
    beats,_=pauta(brief_com_faixas(pairs))
    summaries=[b for b in beats if b["tipo"]=="resumo"]
    assert [len(b["dados"]["cidades"]) for b in summaries]==[4,4]


def test_visual_separate_city_rows_and_attribute_for_highlights():
    compor = pytest.importorskip("hyperframes.compor")
    p={"ceu":"sol","dur":30}
    scene={"id":"s2-quadro","batidas":[0]}
    beats=[{"dados":{"cidades":[{"nome":"Pirituba","min":17,"max":28},
                               {"nome":"Santo Amaro","min":17,"max":28}],
                     "titulo":"TEMPERATURAS POR REGIÃO"}}]
    html=compor.cena_quadro(p,scene,beats)
    assert 'data-cidade="Pirituba"' in html
    assert 'data-cidade="Santo Amaro"' in html
    assert 'class="qd-linha"' in html and html.count('class="qd-linha"')==2
    assert html.count("17°")==2 and html.count("28°")==2


def test_helpers():
    assert juntar_nomes(["Sé"])=="Sé"
    assert juntar_nomes(["Sé","Pirituba"])=="Sé e Pirituba"
    with pytest.raises(ValueError): juntar_nomes([])
    g=agrupar_cidades_por_faixa([dict(nome="Sé",min=17.4,max=28.3),
                                 dict(nome="Pirituba",min=16.6,max=27.5)])
    assert frase_faixa(g[0])=="Sé e Pirituba, de 17 a 28 graus."
    assert graus_inteiros(17.9)==18

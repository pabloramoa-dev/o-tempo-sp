"""Uma fala por região, temperatura agrupada apenas DENTRO da região."""
from copy import deepcopy
import pytest
from scripts.produce import pauta as pauta_producao
from scripts.live import pauta as pauta_live
from src.otemposp.geo import locations, sectors
from src.otemposp.temperatura import (
    agrupar_cidades_por_faixa, frase_faixa, graus_inteiros, juntar_nomes)

def brief_com_faixas(pares):
    pontos=locations(1)
    assert len(pares)==len(pontos)==11
    cards=[dict(point=p["name"],sector=p["sector"],short=sectors()[p["sector"]]["short"],
                min_c=float(a),max_c=float(b),rain_pct=None,rain_mm=0)
           for p,(a,b) in zip(pontos,pares)]
    return dict(cards=cards,when="hoje",hottest=max(cards,key=lambda c:c["max_c"]),
                wettest=cards[0],is_fixture=True)

def resumos(beats):
    return [b for b in beats if b["tipo"]=="resumo"]

def linhas(beats):
    return [cidade for b in resumos(beats) for cidade in b["dados"]["cidades"]]

@pytest.mark.parametrize("pauta",[pauta_producao,pauta_live])
def test_six_regions_spoken_separately_with_all_eleven_visible(pauta):
    pares=[(17,28),(17.6,28.9),(17.1,28.2),(17.9,28.1),
           (19,30),(19.5,30.8),(21,32),(21,32),
           (23,29),(24,30),(25,31)]
    data=brief_com_faixas(pares)
    old=deepcopy(data["cards"])
    beats,cities=pauta(data)
    chunks=resumos(beats)
    assert len(chunks)==6
    titles=[b["dados"]["titulo"] for b in chunks]
    assert titles==["ZONA NORTE","CENTRO","ZONA OESTE","ZONA LESTE","ZONA SUL","LITORAL PAULISTA"]
    assert [len(b["dados"]["cidades"]) for b in chunks]==[2,1,1,2,2,3]
    assert chunks[0]["fala"]=="Na Zona Norte, Santana e Pirituba, de 17 a 28 graus."
    assert chunks[1]["fala"].startswith("No Centro, Sé, de ")
    assert chunks[-1]["fala"].startswith("No Litoral Paulista, ")
    assert len(linhas(beats))==len(cities)==11
    assert {x["nome"] for x in linhas(beats)}=={x["point"] for x in old}
    assert data["cards"]==old

@pytest.mark.parametrize("pauta",[pauta_producao,pauta_live])
def test_even_same_temperatures_never_merge_different_regions(pauta):
    beats,cities=pauta(brief_com_faixas([(17,28)]*11))
    chunks=resumos(beats)
    assert len(chunks)==6 and len(cities)==11
    assert sum(len(x["dados"]["cidades"]) for x in chunks)==11
    assert sum("de 17 a 28 graus" in x["fala"] for x in chunks)==6
    assert "Santana e Pirituba" in chunks[0]["fala"]
    assert "Tatuapé e Itaquera" in chunks[3]["fala"]
    assert "Caraguatatuba, Santos e Ilha Comprida" in chunks[5]["fala"]

@pytest.mark.parametrize("pauta",[pauta_producao,pauta_live])
def test_different_temperatures_remain_individual_in_each_region(pauta):
    pares=[(10+i,20+i) for i in range(11)]
    beats,_=pauta(brief_com_faixas(pares))
    chunks=resumos(beats)
    assert [len(b["dados"]["cidades"]) for b in chunks]==[2,1,1,2,2,3]
    assert chunks[0]["fala"].count("graus")==2
    assert chunks[-1]["fala"].count("graus")==3

@pytest.mark.parametrize("pauta",[pauta_producao,pauta_live])
def test_missing_coast_blocks_video_instead_of_publishing_partial(pauta):
    data=brief_com_faixas([(17,28)]*11)
    data["cards"]=[c for c in data["cards"] if c["sector"]!="litoral_sul"]
    with pytest.raises(ValueError,match="Boletim incompleto"):
        pauta(data)

def test_visual_separate_city_rows_and_attribute_for_highlights():
    from hyperframes.compor import cena_quadro
    p={"ceu":"sol","dur":30}
    scene={"id":"s2-quadro","batidas":[0]}
    beats=[{"dados":{"cidades":[{"nome":"Pirituba","min":17,"max":28,"chuva_mm":0.0},
                                  {"nome":"Santo Amaro","min":17,"max":28,"chuva_mm":6.3}],
                     "titulo":"TEMPERATURAS POR REGIÃO"}}]
    html=cena_quadro(p,scene,beats)
    assert 'data-cidade="Pirituba"' in html
    assert 'data-cidade="Santo Amaro"' in html
    assert 'class="qd-linha"' in html and html.count('class="qd-linha"')==2
    assert html.count("17°")==2 and html.count("28°")==2
    assert html.count('class="qd-chuva"')==2
    assert "VOLUME <b>0,0 mm</b>" in html
    assert "VOLUME <b>6,3 mm</b>" in html

def test_volume_chuva_ausente_nao_e_convertido_em_zero_e_painel_compacto():
    from hyperframes.compor import cena_quadro
    p={"ceu":"sol","dur":30}
    scene={"id":"s3-quadro","batidas":[0]}
    cidades=[{"nome":f"Bairro {i}","min":15,"max":22,"chuva_mm":None if i==0 else 1.4}
             for i in range(5)]
    beats=[{"dados":{"cidades":cidades,"titulo":"ZONA NORTE"}}]
    html=cena_quadro(p,scene,beats)
    assert 'class="qd-painel qd-compacto"' in html
    assert html.count('class="qd-chuva"')==5
    assert "VOLUME <b>—</b>" in html
    assert html.count("VOLUME <b>1,4 mm</b>")==4


def test_helpers():
    assert juntar_nomes(["Sé"])=="Sé"
    assert juntar_nomes(["Sé","Pirituba"])=="Sé e Pirituba"
    with pytest.raises(ValueError): juntar_nomes([])
    g=agrupar_cidades_por_faixa([dict(nome="Sé",min=17.6,max=28.9),
                                  dict(nome="Pirituba",min=17.1,max=28.3)])
    assert frase_faixa(g[0])=="Sé e Pirituba, de 17 a 28 graus."
    assert graus_inteiros(17.9)==17

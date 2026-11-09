"""Cada boletim deve ter todas as regiões da capital e do litoral."""
from src.otemposp.geo import validate, locations, sectors, GRUPOS

def test_capital_mais_tres_areas_litoraneas():
    validate()
    assert len(sectors()) == 11
    assert sum(len(s['subprefeituras']) for s in sectors().values()) == 32
    assert sum(s['group'] != 'litoral' for s in sectors().values()) == 8
    assert sum(s['group'] == 'litoral' for s in sectors().values()) == 3
    assert len(locations(1)) == 11
    assert len(locations(2)) == 21
    assert set(p['sector'] for p in locations(1)) == set(sectors())
    assert {s['group'] for s in sectors().values()} == set(GRUPOS)

def test_cidades_costeiras_presentes_diariamente():
    cidades = {p['name']: p for p in locations(1)}
    assert {'Caraguatatuba', 'Santos', 'Ilha Comprida'} <= set(cidades)
    for cidade in ('Caraguatatuba', 'Santos', 'Ilha Comprida'):
        assert sectors()[cidades[cidade]['sector']]['group'] == 'litoral'

def test_parelheiros_e_cantareira_tier2():
    ids = {x['id'] for x in locations(2)}
    assert {'parelheiros','tremembe','marsilac','perus'} <= ids

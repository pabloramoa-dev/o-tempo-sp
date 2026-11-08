from src.otemposp.geo import validate, locations, sectors

def test_32_subprefeituras_em_8_setores():
    validate()
    assert len(sectors()) == 8
    assert sum(len(s['subprefeituras']) for s in sectors().values()) == 32
    assert len(locations(1)) == 8
    assert len(locations(2)) == 18
    assert set(s['sector'] for s in locations(1)) == set(sectors())

def test_parelheiros_e_cantareira_tier2():
    ids = {x['id'] for x in locations(2)}
    assert {'parelheiros','tremembe','marsilac','perus'} <= ids

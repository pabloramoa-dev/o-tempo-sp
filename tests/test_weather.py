import pytest
from src.otemposp.geo import locations
from src.otemposp.weather import parse, collect, DAILY


def raw():
    return {
        'daily': {k: ([24,25,26] if k!='time' else ['2026-11-08','2026-11-09','2026-11-10']) for k in DAILY+('time',)},
        'hourly': {'time':['2026-11-08T14:00','2026-11-09T16:00'], 'precipitation_probability':[20,40]}
    }

def test_parse_hoje_amanha():
    pts=locations(1)
    rows=[raw() for _ in pts]
    a=parse(rows,pts,day_offset=0)
    b=parse(rows,pts,day_offset=1)
    assert a['forecast_date']=='2026-11-08'
    assert b['forecast_date']=='2026-11-09'
    assert b['points'][0]['rain_peak_hour']=='16:00'
    assert len(b['points'])==8

def test_nao_aceitar_ponto_faltando():
    with pytest.raises(ValueError, match='parcial'):
        parse([raw()],locations(1))

def test_coletor_requisicao_em_lote():
    class Reply:
        def raise_for_status(self): pass
        def json(self): return [raw() for _ in locations(1)]
    class Session:
        def get(self, url, params, timeout):
            assert len(params['latitude'].split(','))==8
            assert 'precipitation_sum' in params['daily']
            return Reply()
    assert len(collect(session=Session())['points'])==8

from datetime import datetime, timezone, timedelta
import pytest
from src.otemposp.geo import locations
from src.otemposp.weather import parse, parse_met, collect, DAILY


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
    assert len(b['points'])==11

def test_nao_aceitar_ponto_faltando():
    with pytest.raises(ValueError, match='parcial'):
        parse([raw()],locations(1))

def test_coletor_open_meteo_em_lote():
    class Reply:
        def raise_for_status(self): pass
        def json(self): return [raw() for _ in locations(1)]
    class Session:
        def get(self, url, params, timeout):
            assert len(params['latitude'].split(','))==11
            assert 'precipitation_sum' in params['daily']
            return Reply()
    assert len(collect(session=Session(), source='open_meteo')['points'])==11


# ----------------------------------------------------------------- MET Norway
NOW = datetime(2026, 11, 8, 9, 0, tzinfo=timezone.utc)  # 06:00 em São Paulo

def met_payload(rain_at_hour=None):
    """48 h horárias a partir das 06:00 locais + blocos de 6 h depois."""
    steps = []
    for h in range(48):
        t = NOW + timedelta(hours=h)
        local_h = (t - timedelta(hours=3)).hour
        rain = 2.5 if rain_at_hour is not None and h == rain_at_hour else 0.0
        steps.append({'time': t.strftime('%Y-%m-%dT%H:%M:%SZ'), 'data': {
            'instant': {'details': {'air_temperature': 18 + local_h * 0.5}},
            'next_1_hours': {'summary': {'symbol_code': 'rain' if rain else 'partlycloudy_day'},
                             'details': {'precipitation_amount': rain}},
            'next_6_hours': {'summary': {'symbol_code': 'cloudy'}, 'details': {'precipitation_amount': 9.9}},
        }})
    for h in range(48, 72, 6):
        t = NOW + timedelta(hours=h)
        steps.append({'time': t.strftime('%Y-%m-%dT%H:%M:%SZ'), 'data': {
            'instant': {'details': {'air_temperature': 20}},
            'next_6_hours': {'summary': {'symbol_code': 'cloudy'}, 'details': {'precipitation_amount': 1.0}},
        }})
    return {'properties': {'timeseries': steps}}

def test_met_hoje_e_amanha_sem_probabilidade():
    pts = locations(1)
    # chuva às 14:00 locais de amanhã = hora 32 a partir das 06:00 de hoje
    payloads = [met_payload(rain_at_hour=32) for _ in pts]
    a = parse_met(payloads, pts, day_offset=0, now=NOW)
    b = parse_met(payloads, pts, day_offset=1, now=NOW)
    assert a['forecast_date'] == '2026-11-08' and b['forecast_date'] == '2026-11-09'
    p = b['points'][0]
    assert p['rain_probability_pct'] is None          # ausente, nunca zero
    assert p['rain_mm'] == 2.5                         # não soma o bloco de 6 h por cima
    assert p['rain_peak_hour'] == '14:00'
    assert p['min_c'] == 18.0 and p['max_c'] == 29.5
    assert a['points'][0]['rain_mm'] == 0.0 and 'rain_peak_hour' not in a['points'][0]
    assert b['license'] == 'CC BY 4.0' and 'MET Norway' in b['source']

def test_met_recusa_dia_incompleto():
    pts = locations(1)
    with pytest.raises(ValueError, match='incompleta'):
        parse_met([met_payload() for _ in pts], pts, day_offset=3, now=NOW)

def test_met_coleta_um_ponto_por_vez_com_user_agent():
    calls = []
    class Reply:
        def raise_for_status(self): pass
        def json(self): return met_payload()
    class Session:
        def get(self, url, params, headers, timeout):
            assert 'api.met.no' in url and 'otemposp' in headers['User-Agent']
            calls.append(params)
            return Reply()
    import src.otemposp.weather as w
    original = w.parse_met
    w.parse_met = lambda payloads, points, day_offset=0: original(payloads, points, day_offset, now=NOW)
    try:
        r = collect(session=Session(), source='met_no')
    finally:
        w.parse_met = original
    assert len(calls) == 11 and len(r['points']) == 11

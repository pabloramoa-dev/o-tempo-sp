from datetime import datetime, timezone, timedelta
import pytest
from src.otemposp.geo import locations
from src.otemposp.weather import parse, parse_met, collect, DAILY, MET_ENDPOINT


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

def test_coletor_open_meteo_em_lote():
    class Reply:
        def raise_for_status(self): pass
        def json(self): return [raw() for _ in locations(1)]
    class Session:
        def get(self, url, params, timeout):
            assert len(params['latitude'].split(','))==8
            assert 'precipitation_sum' in params['daily']
            return Reply()
    assert len(collect(tier=1, session=Session(), source='open_meteo')['points'])==8


# ----------------------------------------------------------------- MET Norway
NOW = datetime(2026, 11, 8, 9, 0, tzinfo=timezone.utc)  # 06:00 em São Paulo
UPDATED = '2026-11-08T07:30:00Z'


def met_payload(rain=None, symbol_rain='rainshowers_day', updated=UPDATED, rh=60, uv=5, gust=8,
                six_max=None):
    """66 h horárias a partir das 06:00 locais (até 23h de amanhã) + blocos de 6 h.

    rain = {hora_a_partir_de_agora: mm}.
    """
    rain = rain or {}
    steps = []
    for h in range(66):
        t = NOW + timedelta(hours=h)
        local_h = (t - timedelta(hours=3)).hour
        mm = rain.get(h, 0.0)
        data = {
            'instant': {'details': {'air_temperature': 18 + local_h * 0.5,
                                    'relative_humidity': rh, 'ultraviolet_index_clear_sky': uv,
                                    'wind_speed_of_gust': gust}},
            'next_1_hours': {'summary': {'symbol_code': symbol_rain if mm else 'partlycloudy_day'},
                             'details': {'precipitation_amount': mm}},
            'next_6_hours': {'summary': {'symbol_code': 'cloudy'},
                             'details': {'precipitation_amount': 9.9,
                                         **({'air_temperature_max': six_max} if six_max else {})}},
        }
        steps.append({'time': t.strftime('%Y-%m-%dT%H:%M:%SZ'), 'data': data})
    return {'properties': {'meta': {'updated_at': updated}, 'timeseries': steps}}


def test_met_hoje_e_amanha_sem_probabilidade():
    pts = locations(1)
    # chuva às 14:00 locais de amanhã = hora 32 a partir das 06:00 de hoje
    payloads = [met_payload(rain={32: 2.5}) for _ in pts]
    a = parse_met(payloads, pts, day_offset=0, now=NOW)
    b = parse_met(payloads, pts, day_offset=1, now=NOW)
    assert a['forecast_date'] == '2026-11-08' and b['forecast_date'] == '2026-11-09'
    assert a['start_hour'] == 6 and b['start_hour'] == 0
    p = b['points'][0]
    assert p['rain_probability_pct'] is None  # ausente, nunca zero
    assert p['rain_mm'] == 2.5  # não soma o bloco de 6 h por cima
    assert p['rain_peak_hour'] == '14:00'
    assert p['rain_window'] == (14, 15)
    assert p['min_c'] == 18.0 and p['max_c'] == 29.5
    assert a['points'][0]['rain_mm'] == 0.0 and 'rain_peak_hour' not in a['points'][0]
    assert b['license'] == 'CC BY 4.0' and 'MET Norway' in b['source']
    assert b['source_url'] == MET_ENDPOINT


def test_met_le_umidade_uv_rajada_e_ceu_por_periodo():
    pts = locations(1)
    # chuva das 15h às 17h de amanhã (horas 33, 34, 35)
    payloads = [met_payload(rain={33: 1.0, 34: 3.0, 35: 0.5}, rh=28, uv=11, gust=20) for _ in pts]
    p = parse_met(payloads, pts, day_offset=1, now=NOW)['points'][0]
    assert p['rh_min'] == 28 and p['uv_max'] == 11 and p['gust_kmh'] == 72
    assert p['rain_window'] == (15, 18)
    assert p['periods'] == {'manha': 'poucas nuvens', 'tarde': 'chuva', 'noite': 'poucas nuvens'}


def test_met_usa_maxima_de_6h_quando_maior_que_a_horaria():
    pts = locations(1)
    p = parse_met([met_payload(six_max=31.2) for _ in pts], pts, day_offset=1, now=NOW)['points'][0]
    assert p['max_c'] == 31.2


def test_met_recusa_dia_incompleto():
    pts = locations(1)
    with pytest.raises(ValueError, match='incompleta'):
        parse_met([met_payload() for _ in pts], pts, day_offset=3, now=NOW)


def test_met_recusa_rodada_vencida_ou_sem_data():
    pts = locations(1)
    with pytest.raises(ValueError, match='desatualizada'):
        parse_met([met_payload(updated='2026-11-07T12:00:00Z') for _ in pts], pts, now=NOW)
    sem = met_payload()
    del sem['properties']['meta']
    with pytest.raises(ValueError, match='atualização'):
        parse_met([sem for _ in pts], pts, now=NOW)


def test_met_coleta_18_pontos_com_altitude_e_user_agent():
    calls = []
    class Reply:
        def raise_for_status(self): pass
        def json(self): return met_payload()
    class Session:
        def get(self, url, params, headers, timeout):
            assert 'api.met.no' in url and 'otemposp' in headers['User-Agent']
            assert 400 < params['altitude'] < 1000
            calls.append(params)
            return Reply()
    import src.otemposp.weather as w
    original = w.parse_met
    w.parse_met = lambda payloads, points, day_offset=0: original(payloads, points, day_offset, now=NOW)
    try:
        r = collect(session=Session(), source='met_no')
    finally:
        w.parse_met = original
    assert len(calls) == 18 and len(r['points']) == 18
    assert {p['tier'] for p in r['points']} == {1, 2}

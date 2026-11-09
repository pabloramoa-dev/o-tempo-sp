import json
from datetime import datetime, timezone

from src.otemposp.geo import locations
from src.otemposp.editorial import summarise
from src.otemposp.publish import guard
from src.otemposp import alertas as ALERTAS
from src.otemposp import ceu as CEU
from scripts.produce import pauta
import pytest

def fixture():
    return {'is_fixture':True, 'forecast_date':'2026-11-08',
        'source':'SIMULADO', 'points': [
        {'id':p['id'],'name':p['name'],'sector':p['sector'],
        'min_c':18+i%3,'max_c':25+i,'rain_probability_pct':10+i*7}
        for i,p in enumerate(locations(1))]}

def met_fixture(tier=1):
    snap = fixture() if tier == 1 else {
        'is_fixture': True, 'forecast_date': '2026-11-08', 'source': 'x',
        'points': [{'id': p['id'], 'name': p['name'], 'sector': p['sector'], 'tier': p['tier'],
                    'min_c': 18 + i % 3, 'max_c': 25 + (i % 8)} for i, p in enumerate(locations(2))]}
    snap.update(source='MET Norway (met.no), licença CC BY 4.0', source_url='https://api.met.no/',
                license='CC BY 4.0', start_hour=0)
    for i, p in enumerate(snap['points']):
        p['rain_probability_pct'] = None
        p['rain_mm'] = float(i % 8) / 2
        p['periods'] = {'manha': 'sol', 'tarde': 'chuva' if i % 2 else 'nublado', 'noite': 'nublado'}
        p['rain_window'] = (15, 18) if p['rain_mm'] >= 0.5 else None
        p['rh_min'], p['uv_max'], p['gust_kmh'] = 55, 6, 30
    return snap

def test_8_cartoes_e_fonte():
    b=summarise(fixture(), alertas=[])
    assert len(b['cards'])==8
    assert 'SIMULADO' in b['caption']
    assert '@otemposp' not in b['script']

def test_met_usa_milimetros_e_credita_fonte():
    b = summarise(met_fixture(), alertas=[])
    assert b['rain_metric'] == 'mm'
    assert 'Dados: MET Norway' in b['caption']
    assert ' mm' in b['caption'] and '%' not in b['caption']
    assert 'graus' in b['script']
    assert b['wettest']['rain_mm'] == 3.5
    assert b['chuva']['classe'] == 'moderada' and b['chuva']['point'] == 'Santo Amaro'
    assert '· 3,5 mm (15h–18h)' in b['caption']
    assert len(b['caption']) < 2200

def test_ceu_dicas_e_cenario():
    b = summarise(met_fixture(), alertas=[])
    assert b['ceu_periodos'] == {'manha': 'sol', 'tarde': 'chuva', 'noite': 'nublado'}
    assert b['frase_ceu'] == 'De manhã, sol; à tarde, chuva; à noite, céu nublado.'
    assert b['ceu'] == 'chuva'
    assert b['dicas'][0]['fala'] == 'Leve o guarda-chuva, principalmente entre 15 e 18 horas.'
    assert b['dicas'][0]['tela'] == 'LEVE GUARDA-CHUVA · 15H–18H'

def test_dica_de_ar_seco_e_amplitude():
    snap = met_fixture()
    for p in snap['points']:
        p['rain_mm'], p['rain_window'], p['rh_min'] = 0.0, None, 24
        p['min_c'], p['max_c'] = 13.2, 27.8
        p['periods'] = {'manha': 'sol', 'tarde': 'sol', 'noite': 'sol'}
    b = summarise(snap, alertas=[])
    falas = [d['fala'] for d in b['dicas']]
    assert falas[0].startswith('Começo do dia fresco e tarde mais quente, de 13 a 28 graus')
    assert 'umidade perto de 24 por cento' in falas[1]
    assert b['chuva'] is None and 'Sem chuva significativa' in b['caption']

def test_extremos_usam_os_18_pontos_mas_quadro_so_as_ancoras():
    snap = met_fixture(tier=2)
    for p in snap['points']:
        if p['id'] == 'marsilac':
            p['min_c'] = 11.0
    b = summarise(snap, alertas=[])
    assert len(b['cards']) == 8 and all(c['tier'] == 1 for c in b['cards'])
    assert b['coldest']['point'] == 'Marsilac'
    beats, _ = pauta(b)
    assert any(x['fala'] == 'A menor mínima fica em Marsilac, com 11 graus.' for x in beats)

def test_ordem_do_video_com_alerta_oficial():
    alerta = {'orgao': 'Defesa Civil de SP', 'titulo': 'Temporal com raios', 'detalhe': 'Zonas Sul e Leste',
              'url': 'https://www.defesacivil.sp.gov.br/', 'issued_at': 'x', 'expires_at': 'y'}
    b = summarise(met_fixture(), alertas=[alerta])
    beats, _ = pauta(b)
    tipos = [x['tipo'] for x in beats]
    assert tipos[0] == 'nenhum' and tipos[1] == 'alerta' and tipos[2] == 'gancho'
    assert tipos[3] == 'ceu' and tipos[-1] == 'cta' and 'dica' in tipos
    assert beats[2]['dados']['sub'] == 'MAIOR CHUVA PREVISTA'
    assert 'ALERTA OFICIAL — Defesa Civil de SP' in b['caption']

def test_alertas_oficiais_validos(tmp_path):
    arq = tmp_path / 'a.json'
    agora = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    bom = {'orgao': 'CGE', 'titulo': 'Chuva forte', 'url': 'https://cgesp.org',
           'issued_at': '2026-11-09T08:00:00-03:00', 'expires_at': '2026-11-09T23:00:00-03:00'}
    vencido = dict(bom, expires_at='2026-11-09T07:00:00-03:00')
    sem_url = dict(bom, url='http://x')
    arq.write_text(json.dumps({'alerts': [bom, vencido, sem_url, {'titulo': 'incompleto'}]}))
    ok = ALERTAS.ativos('2026-11-09', agora, arq)
    assert [a['titulo'] for a in ok] == ['Chuva forte']
    assert ALERTAS.ativos('2026-11-10', agora, arq) == []  # expira antes do dia seguinte
    assert ALERTAS.ativos('2026-11-09', agora, tmp_path / 'nao_existe.json') == []

def test_simbolos_da_met():
    assert CEU.categoria('rainshowers_day') == 'chuva'
    assert CEU.categoria('heavyrainandthunder') == 'trovoadas'
    assert CEU.categoria('partlycloudy_night') == 'poucas nuvens'
    assert CEU.categoria('clearsky_day') == 'sol'
    assert CEU.frase_falada({'noite': 'sol'}) == 'À noite, céu limpo.'

def test_bloqueia_publicacao_automaticamente():
    with pytest.raises(RuntimeError, match='BLOQUEADA'):
        guard(fixture(),summarise(fixture(), alertas=[]),'https://example.org/reel.mp4')

def test_met_nao_exige_licenca_comercial_mas_bloqueia_ficticio(monkeypatch):
    monkeypatch.setenv('PUBLISH_ENABLED', 'true')
    monkeypatch.delenv('COMMERCIAL_DATA_LICENSE_OK', raising=False)
    with pytest.raises(RuntimeError, match='fictício'):
        guard(met_fixture(), summarise(met_fixture(), alertas=[]), 'https://example.org/reel.mp4')

def test_outra_fonte_ainda_exige_licenca(monkeypatch):
    monkeypatch.setenv('PUBLISH_ENABLED', 'true')
    monkeypatch.delenv('COMMERCIAL_DATA_LICENSE_OK', raising=False)
    snap = fixture(); snap['is_fixture'] = False
    with pytest.raises(RuntimeError, match='COMMERCIAL_DATA_LICENSE_OK'):
        guard(snap, summarise(snap, alertas=[]), 'https://example.org/reel.mp4')

from src.otemposp.geo import locations
from src.otemposp.editorial import summarise
from src.otemposp.publish import guard
import pytest

def fixture():
    return {'is_fixture':True, 'forecast_date':'2026-11-08',
        'source':'SIMULADO', 'points': [
        {'id':p['id'],'name':p['name'],'sector':p['sector'],
        'min_c':18+i%3,'max_c':25+i,'rain_probability_pct':10+i*7}
        for i,p in enumerate(locations(1))]}

def met_fixture():
    snap = fixture()
    snap.update(source='MET Norway (met.no), licença CC BY 4.0', source_url='https://api.met.no/',
                license='CC BY 4.0')
    for i, p in enumerate(snap['points']):
        p['rain_probability_pct'] = None
        p['rain_mm'] = float(i) / 2
    return snap

def test_8_cartoes_e_fonte():
    b=summarise(fixture())
    assert len(b['cards'])==8
    assert 'SIMULADO' in b['caption']
    assert '@otemposp' not in b['script']

def test_met_usa_milimetros_e_credita_fonte():
    b = summarise(met_fixture())
    assert b['rain_metric'] == 'mm'
    assert 'Dados: MET Norway' in b['caption']
    assert ' mm' in b['caption'] and '%' not in b['caption']
    assert 'milímetros' in b['script']
    assert b['wettest']['rain_mm'] == 3.5

def test_met_sem_chuva():
    snap = met_fixture()
    for p in snap['points']:
        p['rain_mm'] = 0.0
    assert 'Não há chuva prevista' in summarise(snap)['script']

def test_bloqueia_publicacao_automaticamente():
    with pytest.raises(RuntimeError, match='BLOQUEADA'):
        guard(fixture(),summarise(fixture()),'https://example.org/reel.mp4')

def test_met_nao_exige_licenca_comercial_mas_bloqueia_ficticio(monkeypatch):
    monkeypatch.setenv('PUBLISH_ENABLED', 'true')
    monkeypatch.delenv('COMMERCIAL_DATA_LICENSE_OK', raising=False)
    with pytest.raises(RuntimeError, match='fictício'):
        guard(met_fixture(), summarise(met_fixture()), 'https://example.org/reel.mp4')

def test_outra_fonte_ainda_exige_licenca(monkeypatch):
    monkeypatch.setenv('PUBLISH_ENABLED', 'true')
    monkeypatch.delenv('COMMERCIAL_DATA_LICENSE_OK', raising=False)
    snap = fixture(); snap['is_fixture'] = False
    with pytest.raises(RuntimeError, match='COMMERCIAL_DATA_LICENSE_OK'):
        guard(snap, summarise(snap), 'https://example.org/reel.mp4')

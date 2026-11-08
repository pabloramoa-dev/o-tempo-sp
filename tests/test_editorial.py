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

def test_8_cartoes_e_fonte():
    b=summarise(fixture())
    assert len(b['cards'])==8
    assert 'SIMULADO' in b['caption']
    assert '@otemposp' not in b['script']

def test_bloqueia_publicacao_automaticamente():
    with pytest.raises(RuntimeError, match='BLOQUEADA'):
        guard(fixture(),summarise(fixture()),'https://example.org/reel.mp4')

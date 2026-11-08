"""Gera DADOS FICTÍCIOS para teste gráfico — nunca publicar."""
import json
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from src.otemposp.geo import locations

parser = argparse.ArgumentParser()
parser.add_argument("--when", choices=["hoje","amanhã"], default="hoje")
when = parser.parse_args().when
target = datetime.now(ZoneInfo("America/Sao_Paulo")).date() + timedelta(days=int(when == "amanhã"))
points = []
for idx,p in enumerate(locations(1)):
    points.append({'id':p['id'],'name':p['name'],'sector':p['sector'],
                   'min_c':18+(idx%3),'max_c':25+idx,
                   'rain_probability_pct':10+idx*7, 'rain_mm':float(idx)})
fixture={'brand':'@otemposp','is_fixture':True,'forecast_date':target.isoformat(),
         'source':'DADOS FICTÍCIOS','points':points}
Path('output').mkdir(exist_ok=True)
Path('output/fixture.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2),encoding='utf-8')
print('output/fixture.json')

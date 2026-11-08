"""Gera DADOS FICTÍCIOS para teste gráfico — nunca publicar."""
import json
from datetime import date
from pathlib import Path
from src.otemposp.geo import locations

points = []
for idx,p in enumerate(locations(1)):
    points.append({'id':p['id'],'name':p['name'],'sector':p['sector'],
                   'min_c':18+(idx%3),'max_c':25+idx,
                   'rain_probability_pct':10+idx*7, 'rain_mm':float(idx)})
fixture={'brand':'@otemposp','is_fixture':True,'forecast_date':date.today().isoformat(),
         'source':'DADOS FICTÍCIOS','points':points}
Path('output').mkdir(exist_ok=True)
Path('output/fixture.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2),encoding='utf-8')
print('output/fixture.json')

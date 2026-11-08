"""Coleta real Open-Meteo, com validação de atualização e setor.

IMPORTANTE: API free do Open-Meteo NÃO autoriza exploração comercial.
A publicação comercial exige contrato/licença ou substituição da fonte.
"""
from __future__ import annotations
from datetime import datetime, timezone
import os
from typing import Any
import requests
from .geo import locations, sectors

ENDPOINT = os.getenv('OPEN_METEO_URL', 'https://api.open-meteo.com/v1/forecast')
DAILY = ('temperature_2m_min', 'temperature_2m_max',
         'precipitation_probability_max', 'precipitation_sum', 'weather_code')
HOURLY = ('precipitation_probability', 'precipitation')


def parse(payload: Any, points: list[dict], model: str = 'best_match', day_offset: int = 0) -> dict:
    rows = payload if isinstance(payload, list) else [payload]
    if len(rows) != len(points):
        raise ValueError(f'Resposta parcial: {len(rows)} entradas para {len(points)} pontos')
    output = []
    for point, row in zip(points, rows):
        daily = row.get('daily') or {}
        for name in DAILY + ('time',):
            if not daily.get(name):
                raise ValueError(f'Dado ausente {point["id"]}:{name}')
        if day_offset < 0 or day_offset >= len(daily['time']):
            raise ValueError('dia solicitado indisponível')
        # Dia-base = data local retornada pela API, não o fuso UTC de execução.
        def n(key):
            val = daily[key][day_offset]
            if val is None:
                raise ValueError(f'{point["id"]}: dado {key} ausente')
            return round(float(val), 1)
        record = {
            'id': point['id'], 'name': point['name'], 'sector': point['sector'],
            'latitude': point['latitude'], 'longitude': point['longitude'],
            'spatial_fit': point['spatial_fit'], 'date': daily['time'][day_offset],
            'min_c': n('temperature_2m_min'), 'max_c': n('temperature_2m_max'),
            'rain_probability_pct': n('precipitation_probability_max'),
            'rain_mm': n('precipitation_sum'),
            'weather_code': int(daily['weather_code'][day_offset]),
        }
        hourly = row.get('hourly') or {}
        times = hourly.get('time') or []
        probs = hourly.get('precipitation_probability') or []
        peak = sorted([(float(prob), t) for t, prob in zip(times, probs)
                       if prob is not None and t.startswith(record['date'])], reverse=True)
        if peak:
            record['rain_peak_hour'] = peak[0][1][11:16]
        output.append(record)
    base = {r['date'] for r in output}
    if len(base) != 1:
        raise ValueError(f'Datas inconsistentes: {base}')
    return {
        'brand': '@otemposp', 'is_fixture': False,
        'fetched_at': datetime.now(timezone.utc).isoformat(),
        'forecast_date': next(iter(base)),
        'source': f'Open-Meteo / {model}',
        'source_url': 'https://open-meteo.com/',
        'api_endpoint': os.getenv('OPEN_METEO_URL', ENDPOINT),
        'points': output,
    }


def collect(tier: int = 1, day_offset: int = 0, session=None) -> dict:
    points = locations(tier)
    model = os.getenv('WEATHER_MODEL', 'best_match')
    query = {
        'latitude': ','.join(str(p['latitude']) for p in points),
        'longitude': ','.join(str(p['longitude']) for p in points),
        'timezone': 'America/Sao_Paulo',
        'forecast_days': 3,
        'models': model,
        'daily': ','.join(DAILY),
        'hourly': ','.join(HOURLY),
    }
    api_key = os.getenv('OPEN_METEO_API_KEY')
    if api_key:
        query['apikey'] = api_key
    s = session or requests.Session()
    res = s.get(os.getenv('OPEN_METEO_URL', ENDPOINT), params=query, timeout=35)
    res.raise_for_status()
    result = parse(res.json(), points, model=model, day_offset=day_offset)
    covered = {p['sector'] for p in result['points']}
    if covered != set(sectors()):
        raise ValueError(f'Setores sem previsão: {set(sectors())-covered}')
    return result

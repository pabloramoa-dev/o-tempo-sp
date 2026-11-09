"""Coleta real de previsão, com validação de atualização e setor.

Fonte padrão: MET Norway (api.met.no), licença CC BY 4.0 — uso comercial
permitido com crédito à fonte ("Dados: MET Norway").
A MET Norway não fornece probabilidade de chuva para São Paulo: o campo
rain_probability_pct fica AUSENTE (None), nunca zero; usa-se o volume em mm.

Alternativa: WEATHER_SOURCE=open_meteo. A API free do Open-Meteo NÃO autoriza
exploração comercial; publicar com ela exige a API paga (customer-api).
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import os
from typing import Any
import requests
from .geo import locations, sectors, daily_locations

TZ = ZoneInfo('America/Sao_Paulo')

# ----------------------------------------------------------------- MET Norway
MET_ENDPOINT = os.getenv('MET_NO_URL', 'https://api.met.no/weatherapi/locationforecast/2.0/compact')
MET_USER_AGENT = os.getenv('MET_NO_USER_AGENT', 'otemposp/1.0 github.com/pabloramoa-dev/o-tempo-sp')
MET_SOURCE = 'MET Norway (met.no), licença CC BY 4.0'
MET_SOURCE_URL = 'https://api.met.no/'
MIN_HOURS = 6  # menos horas que isso no dia = previsão incompleta, não publica

# symbol_code da MET -> código WMO aproximado (mesma escala do Open-Meteo).
# Ordem = gravidade: o pior símbolo do dia define o código diário.
_SYMBOLS = [
    ('thunder', 95), ('heavysleet', 67), ('sleet', 66), ('heavysnow', 75), ('snow', 71),
    ('heavyrain', 65), ('rainshowers', 80), ('rain', 61), ('lightrain', 51),
    ('fog', 45), ('cloudy', 3), ('partlycloudy', 2), ('fair', 1), ('clearsky', 0),
]


def _symbol_to_wmo(symbol: str | None) -> int | None:
    if not symbol:
        return None
    base = symbol.split('_')[0]
    for key, code in _SYMBOLS:
        if key in base:
            return code
    return None


def parse_met(payloads: list[dict], points: list[dict], day_offset: int = 0,
              now: datetime | None = None) -> dict:
    if len(payloads) != len(points):
        raise ValueError(f'Resposta parcial: {len(payloads)} entradas para {len(points)} pontos')
    if day_offset < 0:
        raise ValueError('dia solicitado indisponível')
    now = (now or datetime.now(timezone.utc)).astimezone(TZ)
    target = (now + timedelta(days=day_offset)).date()
    output = []
    for point, payload in zip(points, payloads):
        series = ((payload or {}).get('properties') or {}).get('timeseries') or []
        temps, rain_hours, codes = [], [], []
        rain_total, covered_until = 0.0, None
        for step in series:
            t = datetime.fromisoformat(step['time'].replace('Z', '+00:00')).astimezone(TZ)
            if t.date() != target:
                continue
            data = step.get('data') or {}
            temp = ((data.get('instant') or {}).get('details') or {}).get('air_temperature')
            if temp is not None:
                temps.append(float(temp))
            # Chuva: soma blocos de 1 h; onde só há blocos de 6 h, soma sem sobrepor.
            for block, hours in (('next_1_hours', 1), ('next_6_hours', 6)):
                info = data.get(block)
                if not info:
                    continue
                if covered_until and t < covered_until:
                    break
                amount = (info.get('details') or {}).get('precipitation_amount')
                if amount is None:
                    continue
                rain_total += float(amount)
                if hours == 1:
                    rain_hours.append((float(amount), t.strftime('%H:%M')))
                covered_until = t + timedelta(hours=hours)
                codes.append(_symbol_to_wmo((info.get('summary') or {}).get('symbol_code')))
                break
        if len(temps) < MIN_HOURS:
            raise ValueError(f'{point["id"]}: previsão incompleta para {target} ({len(temps)} horas)')
        known = [c for c in codes if c is not None]
        record = {
            'id': point['id'], 'name': point['name'], 'sector': point['sector'],
            'latitude': point['latitude'], 'longitude': point['longitude'],
            'spatial_fit': point.get('spatial_fit'), 'date': target.isoformat(),
            'min_c': round(min(temps), 1), 'max_c': round(max(temps), 1),
            'rain_probability_pct': None,  # MET Norway não fornece: ausente, não zero
            'rain_mm': round(rain_total, 1),
            'weather_code': max(known) if known else None,
        }
        wettest = sorted(rain_hours, reverse=True)
        if wettest and wettest[0][0] > 0:
            record['rain_peak_hour'] = wettest[0][1]
        output.append(record)
    return {
        'brand': '@otemposp', 'is_fixture': False,
        'fetched_at': datetime.now(timezone.utc).isoformat(),
        'forecast_date': target.isoformat(),
        'source': MET_SOURCE,
        'source_url': MET_SOURCE_URL,
        'license': 'CC BY 4.0',
        'api_endpoint': MET_ENDPOINT,
        'points': output,
    }


def collect_met(tier: int = 1, day_offset: int = 0, session=None) -> dict:
    points = daily_locations(datetime.now(TZ).date(), 'amanhã' if day_offset else 'hoje') if tier == 1 else locations(tier)
    s = session or requests.Session()
    payloads = []
    for p in points:
        # A MET pede no máximo 4 casas decimais e um User-Agent identificável.
        params = {'lat': round(float(p['latitude']), 4), 'lon': round(float(p['longitude']), 4)}
        res = s.get(MET_ENDPOINT, params=params, headers={'User-Agent': MET_USER_AGENT}, timeout=35)
        res.raise_for_status()
        payloads.append(res.json())
    return parse_met(payloads, points, day_offset=day_offset)


# ------------------------------------------------------------------ Open-Meteo
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


def collect_open_meteo(tier: int = 1, day_offset: int = 0, session=None) -> dict:
    points = daily_locations(datetime.now(TZ).date(), 'amanhã' if day_offset else 'hoje') if tier == 1 else locations(tier)
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
    return parse(res.json(), points, model=model, day_offset=day_offset)


# ------------------------------------------------------------------- comum
def collect(tier: int = 1, day_offset: int = 0, session=None, source: str | None = None) -> dict:
    source = (source or os.getenv('WEATHER_SOURCE') or 'met_no').strip().lower()
    if source == 'met_no':
        result = collect_met(tier, day_offset, session)
    elif source == 'open_meteo':
        result = collect_open_meteo(tier, day_offset, session)
    else:
        raise ValueError(f'WEATHER_SOURCE desconhecida: {source} (use met_no ou open_meteo)')
    covered = {p['sector'] for p in result['points']}
    if covered != set(sectors()):
        raise ValueError(f'Setores sem previsão: {set(sectors())-covered}')
    return result

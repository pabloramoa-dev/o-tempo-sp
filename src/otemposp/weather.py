"""Coleta real de previsão — motor ÚNICO do @otemposp (produção e testes).

Fonte padrão: MET Norway (api.met.no), licença CC BY 4.0 — uso comercial
permitido com crédito à fonte ("Dados: MET Norway").
A MET Norway não fornece probabilidade de chuva confiável para São Paulo: o
campo rain_probability_pct fica AUSENTE (None), nunca zero; usa-se o volume em mm.

Além de mínima/máxima e chuva, cada ponto traz:
- condição do céu por período (manhã, tarde, noite), a partir do symbol_code;
- janela de horário da chuva (ex.: 15h–18h);
- umidade relativa mínima, índice UV (céu limpo) e rajada máxima, quando a MET envia.

Alternativa: WEATHER_SOURCE=open_meteo. A API free do Open-Meteo NÃO autoriza
exploração comercial; publicar com ela exige a API paga (customer-api).
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import os
from typing import Any
import requests
from .geo import locations, sectors
from .ceu import categoria, periodos
from .chuva import janela_de_chuva

TZ = ZoneInfo('America/Sao_Paulo')

# ----------------------------------------------------------------- MET Norway
# 'complete' = mesmo serviço gratuito da 'compact', com umidade, UV, rajada e
# máxima/mínima de 6 em 6 horas.
MET_ENDPOINT = os.getenv('MET_NO_URL', 'https://api.met.no/weatherapi/locationforecast/2.0/complete')
MET_USER_AGENT = os.getenv('MET_NO_USER_AGENT', 'otemposp/1.1 github.com/pabloramoa-dev/o-tempo-sp')
MET_SOURCE = 'MET Norway (met.no), licença CC BY 4.0'
MIN_HOURS = 8          # menos horas que isso no dia = previsão incompleta, não publica
MAX_IDADE_H = 12       # rodada do modelo mais velha que isso = dado vencido, não publica

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


def _when(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace('Z', '+00:00'))


def conferir_atualizacao(payload: dict, now: datetime, ponto: str) -> str:
    """Recusa rodada do modelo vencida (ou sem data de atualização)."""
    updated = (((payload or {}).get('properties') or {}).get('meta') or {}).get('updated_at')
    if not updated:
        raise ValueError(f'{ponto}: resposta sem data de atualização (meta.updated_at)')
    idade = now.astimezone(timezone.utc) - _when(updated).astimezone(timezone.utc)
    if idade > timedelta(hours=MAX_IDADE_H):
        raise ValueError(f'{ponto}: previsão desatualizada ({idade} desde {updated})')
    return updated


def dia_met(payload: dict, target, ponto: str = '?', exigir_dia_inteiro: bool = False) -> dict:
    """Resumo diário de UM ponto, a partir dos passos horários do dia-alvo."""
    series = ((payload or {}).get('properties') or {}).get('timeseries') or []
    horas = []
    for step in series:
        t = _when(step['time']).astimezone(TZ)
        data = step.get('data') or {}
        if t.date() == target and data.get('next_1_hours'):
            horas.append((t, data))
    if len(horas) < MIN_HOURS:
        raise ValueError(f'{ponto}: previsão incompleta para {target} ({len(horas)} horas)')
    span = (horas[-1][0] - horas[0][0]).total_seconds() / 3600
    if horas[-1][0].hour != 23 or len(horas) - 1 != span:
        raise ValueError(f'{ponto}: previsão horária incompleta ou com buracos para {target}')
    if exigir_dia_inteiro and horas[0][0].hour != 0:
        raise ValueError(f'{ponto}: previsão de amanhã sem as 24 horas')

    temps, rain_hours, codes, ceu_horas = [], [], [], []
    rh, uv, gust, pop = [], [], [], []
    rain_total = 0.0
    for t, data in horas:
        inst = (data.get('instant') or {}).get('details') or {}
        if inst.get('air_temperature') is not None:
            temps.append(float(inst['air_temperature']))
        if inst.get('relative_humidity') is not None:
            rh.append(float(inst['relative_humidity']))
        if inst.get('ultraviolet_index_clear_sky') is not None:
            uv.append(float(inst['ultraviolet_index_clear_sky']))
        if inst.get('wind_speed_of_gust') is not None:
            gust.append(float(inst['wind_speed_of_gust']))
        info = data['next_1_hours']
        det = info.get('details') or {}
        amount = float(det.get('precipitation_amount') or 0.0)
        rain_total += amount
        rain_hours.append((amount, t.strftime('%H:%M')))
        if det.get('probability_of_precipitation') is not None:
            pop.append(float(det['probability_of_precipitation']))
        symbol = (info.get('summary') or {}).get('symbol_code')
        codes.append(_symbol_to_wmo(symbol))
        ceu_horas.append((t.hour, categoria(symbol), amount))
    if len(temps) < MIN_HOURS:
        raise ValueError(f'{ponto}: temperatura incompleta para {target}')

    # Máx./mín. de 6 h (só blocos inteiramente dentro do período coberto) pegam
    # o pico entre duas horas cheias, que a leitura hora a hora deixa escapar.
    primeira = horas[0][0]
    fim_dia = datetime(target.year, target.month, target.day, tzinfo=TZ) + timedelta(days=1)
    for step in series:
        t = _when(step['time']).astimezone(TZ)
        six = ((step.get('data') or {}).get('next_6_hours') or {}).get('details') or {}
        if t < primeira or t + timedelta(hours=6) > fim_dia or t.date() != target:
            continue
        if six.get('air_temperature_max') is not None:
            temps.append(float(six['air_temperature_max']))
        if six.get('air_temperature_min') is not None:
            temps.append(float(six['air_temperature_min']))

    known = [c for c in codes if c is not None]
    record = {
        'min_c': round(min(temps), 1), 'max_c': round(max(temps), 1),
        'rain_probability_pct': None,  # MET Norway: ausente, não zero
        'rain_mm': round(rain_total, 1),
        'weather_code': max(known) if known else None,
        'periods': periodos(ceu_horas),
        'rain_window': janela_de_chuva([(int(h[:2]), mm) for mm, h in rain_hours]),
        'rh_min': round(min(rh)) if rh else None,
        'uv_max': round(max(uv), 1) if uv else None,
        'gust_kmh': round(max(gust) * 3.6) if gust else None,
        'rain_prob_max_pct': round(max(pop)) if pop else None,
        'start_hour': horas[0][0].hour,
    }
    wettest = sorted(rain_hours, reverse=True)
    if wettest and wettest[0][0] > 0:
        record['rain_peak_hour'] = wettest[0][1]
    return record


def parse_met(payloads: list[dict], points: list[dict], day_offset: int = 0,
              now: datetime | None = None, endpoint: str | None = None) -> dict:
    if len(payloads) != len(points):
        raise ValueError(f'Resposta parcial: {len(payloads)} entradas para {len(points)} pontos')
    if day_offset < 0:
        raise ValueError('dia solicitado indisponível')
    now = (now or datetime.now(timezone.utc)).astimezone(TZ)
    target = (now + timedelta(days=day_offset)).date()
    output, updates = [], []
    for point, payload in zip(points, payloads):
        updates.append(conferir_atualizacao(payload, now, point['id']))
        dia = dia_met(payload, target, point['id'], exigir_dia_inteiro=day_offset > 0)
        output.append({
            'id': point['id'], 'name': point['name'], 'sector': point['sector'],
            'latitude': point['latitude'], 'longitude': point['longitude'],
            'altitude': point.get('altitude'), 'tier': point.get('tier', 1),
            'spatial_fit': point.get('spatial_fit'), 'date': target.isoformat(), **dia,
        })
    inicio = {p['start_hour'] for p in output}
    if len(inicio) != 1:
        raise ValueError(f'Os pontos têm períodos diferentes: {sorted(inicio)}')
    return {
        'brand': '@otemposp', 'is_fixture': False,
        'fetched_at': now.astimezone(timezone.utc).isoformat(),
        'model_updated_at': min(updates),
        'forecast_date': target.isoformat(),
        'start_hour': inicio.pop(),
        'source': MET_SOURCE,
        'source_url': endpoint or MET_ENDPOINT,
        'license': 'CC BY 4.0',
        'api_endpoint': endpoint or MET_ENDPOINT,
        'points': output,
    }


def collect_met(tier: int = 2, day_offset: int = 0, session=None) -> dict:
    points = locations(tier)
    s = session or requests.Session()
    payloads = []
    for p in points:
        # A MET pede no máximo 4 casas decimais e um User-Agent identificável.
        # A altitude corrige a temperatura pelo relevo (Cantareira, Parelheiros).
        params = {'lat': round(float(p['latitude']), 4), 'lon': round(float(p['longitude']), 4)}
        if p.get('altitude') is not None:
            params['altitude'] = int(p['altitude'])
        res = s.get(MET_ENDPOINT, params=params, headers={'User-Agent': MET_USER_AGENT}, timeout=45)
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
            'tier': point.get('tier', 1),
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
    return parse(res.json(), points, model=model, day_offset=day_offset)


# ------------------------------------------------------------------- comum
def collect(tier: int = 2, day_offset: int = 0, session=None, source: str | None = None) -> dict:
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

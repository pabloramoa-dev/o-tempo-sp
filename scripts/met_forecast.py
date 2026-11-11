"""Previsão horária real da MET Norway para todos os setores paulistas.

O boletim de hoje usa o intervalo contínuo comum a TODOS os setores.
Nenhum dado é estimado ou completado artificialmente.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import time
import requests
from src.otemposp.geo import daily_locations

ENDPOINT = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
LOCAL = ZoneInfo("America/Sao_Paulo")
SOURCE = "MET Norway • CC BY 4.0 • https://api.met.no/"

def hourly(row, day):
    """Temperatura e chuva horárias reais, indexadas pela hora local."""
    hours = {}
    for period in row["properties"]["timeseries"]:
        at = datetime.fromisoformat(period["time"].replace("Z", "+00:00")).astimezone(LOCAL)
        if at.date() == day and "next_1_hours" in period["data"]:
            if at.hour in hours:
                raise ValueError("Previsão horária duplicada")
            hours[at.hour] = period["data"]
    if (len(hours) < 8 or 23 not in hours or
            any(h not in hours for h in range(min(hours), 24))):
        raise ValueError("Previsão horária incompleta")
    return hours

def summarize(hours, start_hour):
    """Calcula os extremos apenas para o mesmo intervalo em todos os setores."""
    if (start_hour not in hours or 24 - start_hour < 8 or
            any(h not in hours for h in range(start_hour, 24))):
        raise ValueError("Setor sem cobertura de todo o período comum")
    values = [hours[h] for h in range(start_hour, 24)]
    temps = [v["instant"]["details"]["air_temperature"] for v in values]
    rain = sum(v["next_1_hours"]["details"]["precipitation_amount"] for v in values)
    return dict(min_c=min(temps), max_c=max(temps), rain_mm=round(rain, 1),
                start_hour=start_hour)

def daily(row, day, start_hour=None):
    """Compatibilidade com consultas pontuais; permite intervalo inicial comum."""
    hours = hourly(row, day)
    if start_hour is None:
        start_hour = min(hours)
    return summarize(hours, start_hour)

def collect(offset):
    if offset not in (0, 1):
        raise ValueError("Somente os turnos de hoje e amanhã são permitidos")
    now = datetime.now(timezone.utc)
    publication_day = now.astimezone(LOCAL).date()
    day = publication_day + timedelta(days=offset)
    turn = "amanhã" if offset else "hoje"
    chosen = daily_locations(publication_day, turn)
    readings = []
    with requests.Session() as session:
        session.headers["User-Agent"] = "OTempoSP/1.0 (https://www.instagram.com/otemposp/)"
        for point in chosen:
            for attempt in range(3):
                try:
                    response = session.get(
                        ENDPOINT,
                        params={"lat": point["latitude"], "lon": point["longitude"]},
                        timeout=45,
                    )
                    response.raise_for_status()
                    hours = hourly(response.json(), day)
                    break
                except (requests.RequestException, ValueError, KeyError) as exc:
                    if attempt == 2:
                        raise RuntimeError(
                            f"MET Norway: 3 tentativas falharam no setor {point['sector']}"
                        ) from exc
                    time.sleep(2 * (attempt + 1))
            readings.append((point, hours))
    # Algumas coordenadas recebem dados a partir de horas diferentes.
    # Alinhar pelo início MAIS TARDIO evita misturar chuva de períodos desiguais.
    shared_start = max(min(hours) for _, hours in readings)
    if offset and shared_start != 0:
        raise ValueError("Previsão de amanhã sem as 24 horas")
    points = [dict(point, **summarize(hours, shared_start))
              for point, hours in readings]
    return dict(brand="@otemposp", is_fixture=False, forecast_date=day.isoformat(),
                rotation_publication_day=publication_day.isoformat(), rotation_turn=turn,
                fetched_at=now.isoformat(), source=SOURCE, source_url=ENDPOINT,
                api_endpoint=ENDPOINT, points=points)

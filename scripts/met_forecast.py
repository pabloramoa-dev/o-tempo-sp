"""Previsão horária da MET Norway para os pontos do boletim paulista."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from src.otemposp.geo import locations

ENDPOINT = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
LOCAL = ZoneInfo("America/Sao_Paulo")
SOURCE = "MET Norway • CC BY 4.0 • https://api.met.no/"

def daily(row, day):
    hours = []
    for period in row["properties"]["timeseries"]:
        at = datetime.fromisoformat(period["time"].replace("Z", "+00:00")).astimezone(LOCAL)
        if at.date() == day and "next_1_hours" in period["data"]:
            hours.append((at, period["data"]))
    if len(hours) < 8 or hours[-1][0].hour != 23 or (len(hours)-1 != (hours[-1][0]-hours[0][0]).total_seconds()/3600):
        raise ValueError("Previsão horária incompleta")
    temps = [v["instant"]["details"]["air_temperature"] for _, v in hours]
    rain = sum(v["next_1_hours"]["details"]["precipitation_amount"] for _, v in hours)
    return dict(min_c=min(temps), max_c=max(temps), rain_mm=round(rain, 1),
                start_hour=hours[0][0].hour)

def collect(offset):
    now = datetime.now(timezone.utc)
    day = now.astimezone(LOCAL).date() + timedelta(days=offset)
    points = []
    with requests.Session() as session:
        session.headers["User-Agent"] = "OTempoSP/1.0 (https://www.instagram.com/otemposp/)"
        for point in locations(1):
            response = session.get(ENDPOINT, params={"lat":point["latitude"],"lon":point["longitude"]},timeout=45)
            response.raise_for_status()
            values = daily(response.json(),day)
            if offset and values["start_hour"] != 0:
                raise ValueError("Previsão de amanhã sem as 24 horas")
            points.append(dict(point,**values))
    if len({p["start_hour"] for p in points}) != 1:
        raise ValueError("Os setores têm períodos diferentes")
    return dict(brand="@otemposp",is_fixture=False,forecast_date=day.isoformat(),
                fetched_at=now.isoformat(),source=SOURCE,source_url=ENDPOINT,
                api_endpoint=ENDPOINT,points=points)

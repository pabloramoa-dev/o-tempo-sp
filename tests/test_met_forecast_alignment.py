"""Cobertura comum real da MET Norway: regressão da falha em 11/11/2026."""
from datetime import datetime, time, timedelta, timezone

import pytest
from scripts import met_forecast


def make_payload(day, start_hour, missing_hour=None):
    start = datetime.combine(day, time.min, tzinfo=met_forecast.LOCAL)
    series = []
    for h in range(start_hour, 24):
        if h == missing_hour:
            continue
        at = (start + timedelta(hours=h)).astimezone(timezone.utc)
        series.append({
            "time": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {
                "instant": {"details": {"air_temperature": 10.0 + h}},
                "next_1_hours": {"details": {
                    "precipitation_amount": 99.0 if h == 5 else 1.0
                }},
            },
        })
    return {"properties": {"timeseries": series}}


def test_alinha_setores_sem_somar_horas_diferentes(monkeypatch):
    day = datetime.now(met_forecast.LOCAL).date()
    class Response:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): pass
        def json(self): return self.payload
    class Session:
        def __init__(self):
            self.headers = {}
            self.count = 0
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, url, params, timeout):
            self.count += 1
            start_hour = 5 if self.count % 2 else 6
            return Response(make_payload(day, start_hour))
    monkeypatch.setattr(met_forecast.requests, "Session", Session)
    snap = met_forecast.collect(0)
    assert len(snap["points"]) == 11
    assert {p["start_hour"] for p in snap["points"]} == {6}
    assert all(p["min_c"] == 16.0 and p["max_c"] == 33.0 for p in snap["points"])
    assert all(p["rain_mm"] == 18.0 for p in snap["points"])


def test_recusa_buraco_de_horas_ao_inves_de_inventar_dados():
    day = datetime.now(met_forecast.LOCAL).date()
    with pytest.raises(ValueError, match="incompleta"):
        met_forecast.daily(make_payload(day, 5, missing_hour=12), day)


def test_amanha_exige_dia_completo():
    day = datetime.now(met_forecast.LOCAL).date() + timedelta(days=1)
    data = make_payload(day, 6)
    with pytest.raises(ValueError, match="incompleta|24 horas|período comum"):
        met_forecast.daily(data, day, start_hour=0)

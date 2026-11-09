"""Rodízio sem repetição diária, sem perder qualquer região da capital/litoral."""
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo

import pytest

from src.otemposp.geo import daily_locations, locations, sectors


def _ids(items):
    return {x["sector"]: x["id"] for x in items}


def test_rodizio_em_31_dias_cobre_todos_os_setores_sem_repetir_dia_anterior():
    begin = date(2026, 11, 9)
    pools = {
        key: {p["id"] for p in locations(2) if p["sector"] == key}
        for key in sectors()
    }
    seen = {key: set() for key in sectors()}
    previous_morning = previous_evening = None
    previous_day_evening = None

    for i in range(31):
        day = begin + timedelta(days=i)
        morning = daily_locations(day, "hoje")
        evening = daily_locations(day, "amanhã")
        assert morning == daily_locations(day, "hoje")
        assert evening == daily_locations(day, "amanhã")
        assert len(morning) == len(evening) == len(sectors()) == 11
        m, e = _ids(morning), _ids(evening)
        assert set(m) == set(e) == set(sectors())
        assert all(m[k] != e[k] for k in sectors()), "Bira e Bia com a mesma localidade"
        if previous_morning:
            assert all(m[k] != previous_morning[k] for k in sectors())
            assert all(e[k] != previous_evening[k] for k in sectors())
            assert all(m[k] != previous_day_evening[k] for k in sectors())
        previous_morning, previous_evening = m, e
        previous_day_evening = e
        for key in sectors():
            seen[key].update((m[key], e[key]))
            assert m[key] in pools[key] and e[key] in pools[key]
    assert seen == pools, "Todos os bairros/municípios devem aparecer no ciclo"


def test_rodizio_determinista_para_cada_dia_independente_da_ordem_de_chamada():
    d0 = date(2026, 11, 9)
    d1 = d0 + timedelta(days=1)
    first = daily_locations(d0, "hoje")
    daily_locations(d1, "amanhã")
    assert first == daily_locations(d0, "hoje")
    assert first != daily_locations(d1, "hoje")


@pytest.mark.parametrize("invalid", ["ontem", "tarde", ""])
def test_turno_invalido_recusado(invalid):
    with pytest.raises(ValueError, match="turno"):
        daily_locations(date(2026, 11, 9), invalid)


def test_todos_os_seis_grupos_incluidos_em_ambos_os_turnos():
    for when in ("hoje", "amanhã"):
        chosen = daily_locations(date(2026, 11, 9), when)
        grupos = {sectors()[p["sector"]]["group"] for p in chosen}
        assert grupos == {"norte", "centro", "oeste", "leste", "sul", "litoral"}
        assert sum(sectors()[p["sector"]]["group"] == "litoral" for p in chosen) == 3


def test_coleta_do_pipeline_usa_os_bairros_escolhidos_para_a_data(monkeypatch):
    from scripts import met_forecast
    local_now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    local_today = local_now.date()
    # A entrada é horária e completa nos dois dias para o coletor real.
    start = datetime(local_today.year, local_today.month, local_today.day,
                     tzinfo=ZoneInfo("America/Sao_Paulo"))
    hours = [
        {
            "time": (start + timedelta(hours=i)).astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
            "data": {
                "instant": {"details": {"air_temperature": 20 + (i % 7)}},
                "next_1_hours": {"details": {"precipitation_amount": 0.5}},
            },
        }
        for i in range(48)
    ]
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"properties": {"timeseries": hours}}
    class Session:
        def __init__(self):
            self.points = []
            self.headers = {}
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
        def get(self, url, params, timeout):
            self.points.append(params)
            return Response()

    monkeypatch.setattr(met_forecast.requests, "Session", Session)
    for offset, when in ((0, "hoje"), (1, "amanhã")):
        snap = met_forecast.collect(offset)
        assert snap["rotation_publication_day"] == local_today.isoformat()
        assert snap["rotation_turn"] == when
        chosen = daily_locations(local_today, when)
        assert [p["id"] for p in snap["points"]] == [p["id"] for p in chosen]
        assert [p["name"] for p in snap["points"]] == [p["name"] for p in chosen]
        assert len(snap["points"]) == 11
        assert all(p["rain_mm"] >= 0 for p in snap["points"])

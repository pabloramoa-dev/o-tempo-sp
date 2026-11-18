"""Pauta de eventos de sexta-feira; previsao horaria real (Open-Meteo).
Somente eventos previamente confirmados no catalogo da edicao vigente.
Nunca publica nem inventa evento, horario ou condicao meteorologica.
"""
import json
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "eventos_fim_de_semana.json"
OUT = ROOT / "output" / "eventos_fim_de_semana"

def forecast(lat, lon):
    q = urlencode({"latitude": lat, "longitude": lon,
                   "hourly": "temperature_2m,precipitation_probability,precipitation,wind_gusts_10m",
                   "timezone": "America/Sao_Paulo", "forecast_days": 5})
    with urlopen("https://api.open-meteo.com/v1/forecast?" + q, timeout=30) as response:
        d = json.load(response)
    h = d["hourly"]
    return {t: {k: h[k][i] for k in ("temperature_2m","precipitation_probability","precipitation","wind_gusts_10m")}
            for i, t in enumerate(h["time"])}

def condition(p):
    temp = p["temperature_2m"]
    prob = p["precipitation_probability"]
    gust = p["wind_gusts_10m"]
    if temp is None or prob is None or gust is None:
        raise ValueError("Modelo nao retornou campos suficientes")
    tips = []
    if prob >= 50:
        tips.append("Leve capa de chuva e confira os avisos oficiais e as regras do evento.")
    if temp <= 18:
        tips.append("Leve agasalho.")
    elif temp >= 30:
        tips.append("Leve agua e protecao contra o sol.")
    if gust >= 50:
        tips.append("Atencao a rajadas de vento; siga orientacoes da organizacao.")
    if not tips:
        tips.append("Confira a atualizacao da previsao antes de sair.")
    return tips

def run(now=None):
    now = now or datetime.now(TZ)
    edition = now.date() if now.weekday() == 4 else now.date() + timedelta(days=(4-now.weekday())%7)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if catalog["edition"] != edition.isoformat():
        raise RuntimeError("Catalogo de eventos desatualizado. Nao criar pauta com eventos antigos.")
    if len(catalog["events"]) != 2:
        raise ValueError("Sao necessarios dois eventos confirmados.")
    output = []
    for e in catalog["events"]:
        if not e.get("source") or not e.get("venue"):
            raise ValueError("Evento sem fonte ou local")
        values = forecast(e["latitude"], e["longitude"])
        sessions = []
        for s in e["sessions"]:
            dt = datetime.fromisoformat(s["starts_at"]).astimezone(TZ)
            if dt < now or dt.date() > edition + timedelta(days=2):
                continue
            key = dt.strftime("%Y-%m-%dT%H:00")
            if key not in values:
                raise RuntimeError("Previsao horaria indisponivel para " + key)
            p = values[key]
            sessions.append({"data_hora": dt.isoformat(), "atracao": s["headline"],
                             "temperatura_c": p["temperature_2m"],
                             "probabilidade_chuva_pct": p["precipitation_probability"],
                             "chuva_mm_na_hora": p["precipitation"],
                             "rajadas_kmh": p["wind_gusts_10m"],
                             "orientacoes": condition(p)})
        if not sessions:
            raise RuntimeError("Evento sem sessao futura confirmada")
        output.append({"evento": e["name"], "local": e["venue"], "fonte_evento": e["source"],
                       "criterio_selecao": e["priority"], "sessoes": sessions})
    lines = ["VAI SAIR? CONFIRA O TEMPO! | @otemposp", "Previsao para os eventos do feriado/fim de semana"]
    for e in output:
        s = e["sessoes"][0]
        hora = datetime.fromisoformat(s["data_hora"]).strftime("%d/%m %Hh")
        lines += ["", e["evento"] + " — " + s["atracao"],
                  e["local"] + " | " + hora,
                  f'Temperatura prevista: {s["temperatura_c"]}°C; chance de chuva: {s["probabilidade_chuva_pct"]}%; rajadas: {s["rajadas_kmh"]} km/h.',
                  " ".join(s["orientacoes"])]
    lines += ["", "Previsao horaria Open-Meteo; sujeito a mudancas. Consulte atualizacoes antes do evento.",
              "#OTempoSP #SaoPaulo #PrevisaoDoTempo #AgendaSP"]
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"edicao": edition.isoformat(), "gerado_em": now.isoformat(),
               "fonte_meteorologica": "Open-Meteo /v1/forecast hourly", "publicado": False,
               "eventos": output}
    (OUT / "pauta.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "legenda.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return payload

if __name__ == "__main__":
    run()

import json
import sys
from pathlib import Path
from scripts.met_forecast import collect, SOURCE
from src.otemposp.geo import sectors
from scripts.produce import render_brief, pauta as pauta_de_producao
from src.otemposp.temperatura import graus_inteiros

def pauta(brief):
    """Usa a mesma pauta agrupada do renderizador para evitar narrações divergentes."""
    return pauta_de_producao(brief)


def run(when):
    snap=collect(int(when=="amanhã"))
    points=snap["points"]
    cards=[dict(point=p["name"],short=sectors()[p["sector"]]["short"], min_c=p["min_c"],
                max_c=p["max_c"],rain_mm=p["rain_mm"],rain_pct=None) for p in points]
    hour=points[0]["start_hour"]
    caption=f"O TEMPO SP • {when} ({snap['forecast_date']})\nPrevisão das {hour:02d}h às 24h, horário de São Paulo.\n"
    for c in cards:
        caption+=f"\n{c['point']}: {c['min_c']:.0f}° a {c['max_c']:.0f}° · {c['rain_mm']:g} mm"
    caption+=f"\n\nFonte: {SOURCE}. Valores calculados a partir da previsão horária. #OTempoSP #SaoPaulo"
    brief=dict(when=when,date=snap["forecast_date"],is_fixture=False,hora_inicio=hour,cards=cards,caption=caption,
               hottest=max(cards,key=lambda c:c["max_c"]),wettest=max(cards,key=lambda c:c["rain_mm"]))
    out=Path("output");out.mkdir(exist_ok=True)
    for name,value in (("snapshot",snap),("brief",brief)):
        (out/f"{name}.json").write_text(json.dumps(value,ensure_ascii=False))
    render_brief(brief,out/("bira.mp4" if when=="hoje" else "bia.mp4"))

if __name__=="__main__":
    run(sys.argv[1])

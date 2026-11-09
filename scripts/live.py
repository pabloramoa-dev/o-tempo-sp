import json
import sys
from pathlib import Path
from scripts.met_forecast import collect, SOURCE
from src.otemposp.geo import sectors
from scripts.produce import render_brief

def pauta(brief):
    """Narração curta: só temperaturas. Chuva permanece nos dados e na legenda."""
    cards = brief["cards"]
    cities = [dict(nome=c["point"], setor=c.get("short", ""),
                   min=c["min_c"], max=c["max_c"], chuva_mm=c["rain_mm"],
                   prob_chuva=None) for c in cards]
    hot = brief["hottest"]

    def beat(kind, text, **data):
        return dict(tipo=kind, fala=text, legenda=text, dados=data)

    morning = brief["when"] == "hoje"
    beats = [
        beat("nenhum", ("Bom dia, São Paulo! " if morning else "Boa noite, São Paulo! ")
             + f"Confira as temperaturas de {brief['when']} por região."),
        beat("gancho", f"Em {hot['point']}, a máxima chega a {round(hot['max_c'])} graus.",
             numero=f"{round(hot['max_c'])}°", sub="MAIOR MÁXIMA"),
    ]
    for group in (cities[:4], cities[4:]):
        fala = " ".join(
            f"{x['nome']}: mínima de {round(x['min'])} e máxima de {round(x['max'])} graus."
            for x in group
        )
        beats.append(beat("resumo", fala, cidades=group, titulo="TEMPERATURAS POR REGIÃO"))
    beats.append(beat("cta", "Conte pra gente de qual bairro você acompanha a previsão.",
                      chamada="QUAL É O SEU BAIRRO?", sub="@otemposp"))
    return beats, cities

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

"""Roteiro paulista e exportação com o estúdio de produção HyperFrames."""
import json
import sys
from pathlib import Path
from src.otemposp.editorial import summarise

def pauta(brief):
    cards = brief["cards"]
    cities = [dict(nome=c["point"], setor=c["short"], min=c["min_c"], max=c["max_c"],
                   prob_chuva=c["rain_pct"], chuva_mm=c.get("rain_mm")) for c in cards]
    when = brief["when"]
    hot = brief["hottest"]
    def beat(tipo, fala, **dados):
        return dict(tipo=tipo, fala=fala, legenda=fala, dados=dados)
    beats = [beat("nenhum", ("Bom dia, São Paulo!" if when=="hoje" else "Boa noite, São Paulo!") +
                  (" Confira a previsão para amanhã." if when=="amanhã" else " Confira a previsão de hoje.")),
             beat("gancho", f"Em {hot['point']}, a máxima chega a {hot['max_c']:g} graus.",
                  numero=f"{hot['max_c']:g}°", sub="MAIOR MÁXIMA"),
             ]
    for i in (0, 4):
        rows=cities[i:i+4]
        fala=" ".join(f"{c['nome']}: mínima de {round(c['min'])} e máxima de {round(c['max'])} graus." for c in rows)
        beats.append(beat("resumo",fala,cidades=rows,titulo="PREVISÃO POR SETOR"))
    beats.append(beat("cta","Siga O Tempo SP e conte de qual bairro você acompanha a previsão.",
                      chamada="QUAL É O SEU BAIRRO?",sub="@otemposp"))
    return beats,cities

def render_brief(brief,destination):
    from hyperframes.gerar_hf import preparar, renderizar
    name="bira" if brief["when"]=="hoje" else "bia"
    out=Path(destination)
    out.parent.mkdir(parents=True,exist_ok=True)
    package,beats,_,_=preparar(name,out,brief)
    out.with_suffix(".json").write_text(json.dumps(beats,ensure_ascii=False,indent=2))
    out.with_suffix(".txt").write_text(brief["caption"])
    return renderizar(out,package)

def produce(snapshot,when):
    brief=summarise(json.loads(Path(snapshot).read_text()),when)
    return render_brief(brief,"output/bira.mp4" if when=="hoje" else "output/bia.mp4")

if __name__ == "__main__":
    produce(*sys.argv[1:])

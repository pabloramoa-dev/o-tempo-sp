"""Roteiro paulista e exportação com o estúdio de produção HyperFrames."""
import json
import sys
from pathlib import Path
from src.otemposp.editorial import summarise
from src.otemposp.chuva import maior_chuva
from src.otemposp.temperatura import (graus_inteiros, agrupar_cidades_por_faixa,
                                   frase_faixa, juntar_nomes)

def pauta(brief):
    cards = brief["cards"]
    cities = [dict(nome=c["point"], setor=c["short"], min=graus_inteiros(c["min_c"]), max=graus_inteiros(c["max_c"]),
                   prob_chuva=c["rain_pct"], chuva_mm=c.get("rain_mm")) for c in cards]
    when = brief["when"]
    hot = brief["hottest"]
    def beat(tipo, fala, **dados):
        return dict(tipo=tipo, fala=fala, legenda=fala, dados=dados)
    beats = [beat("nenhum", ("Bom dia, São Paulo!" if when=="hoje" else "Boa noite, São Paulo!") +
                  (" Confira a previsão para amanhã." if when=="amanhã" else " Confira a previsão de hoje.")),
             beat("gancho", f"Em {hot['point']}, a máxima chega a {graus_inteiros(hot['max_c'])} graus.",
                  numero=f"{graus_inteiros(hot['max_c'])}°", sub="MAIOR MÁXIMA"),
             ]
    # Agrupamos TODOS os oito pontos antes de paginar: localidades de
    # quadros diferentes com a mesma faixa são narradas numa única frase.
    grupos = agrupar_cidades_por_faixa(cities)
    for i in range(0, len(grupos), 4):
        lote = grupos[i:i + 4]
        rows = [dict(nome=juntar_nomes(g["nomes"]), min=g["min"],
                     max=g["max"], nomes=g["nomes"]) for g in lote]
        fala = " ".join(frase_faixa(g) for g in lote)
        beats.append(beat("resumo", fala, cidades=rows,
                          titulo="TEMPERATURAS POR REGIÃO"))
    beats.append(beat("cta","Siga O Tempo SP e conte de qual bairro você acompanha a previsão.",
                      chamada="QUAL É O SEU BAIRRO?",sub="@otemposp"))
    # A última fala do vídeo destaca apenas a localidade com MAIOR acumulado,
    # preservando o CTA antes do quadro final da chuva.
    chuva = maior_chuva(cards, when)
    if chuva is not None:
        beats.append(beat("gancho", chuva["fala"], numero=f'{chuva["mm_fala"]} mm',
                          sub="MAIOR CHUVA PREVISTA", local=chuva["point"]))
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

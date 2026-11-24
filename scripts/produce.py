"""Roteiro paulista e exportação com o estúdio de produção HyperFrames."""
import json
import sys
from pathlib import Path
from src.otemposp.editorial import summarise
from src.otemposp.chuva import maior_chuva
from src.otemposp.temperatura import (graus_inteiros, agrupar_cidades_por_faixa,
                                   frase_faixa)

# Cada região tem uma cena e uma fala própria: não fundir zonas distintas
# apenas por terem as mesmas temperaturas.
REGIOES = [
    ("norte", "Zona Norte"), ("centro", "Centro"),
    ("oeste", "Zona Oeste"), ("leste", "Zona Leste"),
    ("sul", "Zona Sul"), ("litoral", "Litoral Paulista"),
    ("vale_oeste", "Vale do Paraíba Oeste"),
    ("vale_leste", "Vale do Paraíba Leste"),
    ("mantiqueira", "Serra da Mantiqueira"),
    ("vale_historico", "Vale Histórico e Bocaina"),
]

def numero_extenso(n):
    return {8: "oito", 11: "onze", 15: "quinze"}.get(n, str(n))

def pauta(brief):
    from src.otemposp.geo import sectors
    cards = brief["cards"]
    conf = sectors()
    if len(cards) != len(conf) or {c.get("sector") for c in cards} != set(conf):
        raise ValueError("Boletim incompleto: uma cidade de cada setor da capital, litoral e interior é obrigatória")
    cities = [dict(nome=c["point"], setor=c["short"], regiao=conf[c["sector"]]["group"],
                   min=graus_inteiros(c["min_c"]), max=graus_inteiros(c["max_c"]),
                   prob_chuva=c.get("rain_pct"), chuva_mm=c.get("rain_mm")) for c in cards]
    when = brief["when"]
    hot = brief["hottest"]
    def beat(tipo, fala, **dados):
        return dict(tipo=tipo, fala=fala, legenda=fala, dados=dados)
    chuva = maior_chuva(cards, when)
    # A primeira fala é um fato local verificável, e não uma apresentação genérica.
    # O destaque de chuva continua reservado à parte final do vídeo.
    beats = [beat("gancho",
                  f"{hot['point']}: {graus_inteiros(hot['max_c'])} graus {when}.",
                  numero=f"{graus_inteiros(hot['max_c'])}°",
                  sub="MAIOR MÁXIMA", local=hot["point"])]
    for chave, titulo in REGIOES:
        locais = [c for c in cities if c["regiao"] == chave]
        if not locais:
            raise ValueError(f"Região ausente do roteiro: {titulo}")
        # Agrupar temperaturas repetidas só DENTRO da região; todos os
        # nomes continuam aparecendo em linhas individuais.
        # Todas as localidades seguem visíveis; uma fala curta por região.
        # A região continua independente das demais e usa dado da sua localidade.
        faixas = agrupar_cidades_por_faixa(locais)
        pico = max(locais, key=lambda item: item["max"])
        fala = f"{titulo}: {pico['nome']}, {pico['max']} graus."
        beats.append(beat("resumo", fala, cidades=locais, grupos_falados=faixas,
                          titulo=titulo.upper()))
    if chuva is not None:
        beats.append(beat("gancho", chuva["fala"], numero=f'{chuva["mm_fala"]} mm',
                          sub="MAIOR CHUVA PREVISTA", local=chuva["point"]))
    elif all(c.get("rain_mm") is not None for c in cards):
        n = len(cards)
        beats.append(beat("gancho",
                          f"Nos {numero_extenso(n)} locais acompanhados, não há chuva prevista {when}.",
                          numero="0 mm", sub="SEM CHUVA PREVISTA",
                          local=f"{n} LOCAIS MONITORADOS"))
    # Depois da informação útil, apenas um convite de compartilhamento.
    destino = chuva["point"] if chuva else hot["point"]
    chamada = (f"Manda pra quem mora em {destino} e precisa ver essa previsão."
               if chuva else f"Manda pra quem mora em {destino} conferir a previsão.")
    beats.append(beat("cta", chamada, chamada="ENVIE A PREVISÃO",
                      sub=f"@otemposp • {destino}"))
    return beats,cities

def render_brief(brief,destination):
    # Formato padrão desde 18/11/2026: Bira e Bia em DUPLA (hyperframes/gerar_dupla.py).
    # Reversão sem editar código: variável SP_FORMATO=solo.
    import os
    if os.environ.get("SP_FORMATO", "dupla").strip().lower() != "solo":
        from hyperframes.gerar_dupla import render_brief_dupla
        return render_brief_dupla(brief, destination)
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

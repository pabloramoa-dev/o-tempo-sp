"""Roteiro paulista e exportação com o estúdio de produção HyperFrames.

Ordem do vídeo (o mais importante primeiro, antes que o seguidor saia):
  abertura → [alerta oficial] → GANCHO (chuva relevante OU maior máxima) →
  céu por período → quadros de temperatura → complemento (calor ou chuva fraca /
  sem chuva) → menor mínima → dica prática → chamada para seguir (sempre no fim).
"""
import json
import sys
from pathlib import Path
from src.otemposp.editorial import summarise
from src.otemposp.chuva import maior_chuva, ORDEM
from src.otemposp.temperatura import (graus_inteiros, agrupar_cidades_por_faixa,
                                      frase_faixa)


def _beat(tipo, fala, **dados):
    return dict(tipo=tipo, fala=fala, legenda=fala, dados=dados)


def pauta(brief):
    cards = brief["cards"]
    cities = [dict(nome=c["point"], setor=c["short"], min=graus_inteiros(c["min_c"]),
                   max=graus_inteiros(c["max_c"]), prob_chuva=c.get("rain_pct"),
                   chuva_mm=c.get("rain_mm")) for c in cards]
    when = brief["when"]
    hot = brief["hottest"]
    cold = brief.get("coldest")
    chuva = brief["chuva"] if "chuva" in brief else maior_chuva(cards, when)
    beats = [_beat("nenhum", ("Bom dia, São Paulo!" if when == "hoje" else "Boa noite, São Paulo!") +
                   (" Confira a previsão para amanhã." if when == "amanhã" else " Confira a previsão de hoje."))]

    # Alerta OFICIAL (Defesa Civil/CGE/INMET) logo depois da abertura.
    for a in brief.get("alertas") or []:
        beats.append(_beat("alerta", f'Alerta oficial, {a["orgao"]}: {a["titulo"]}.',
                           titulo=a["titulo"], detalhe=a.get("detalhe") or a["orgao"]))

    # Gancho dinâmico: chuva relevante abre o vídeo; senão, o calor.
    chuva_no_gancho = bool(chuva and ORDEM[chuva["classe"]] >= ORDEM["moderada"])
    if chuva_no_gancho:
        beats.append(_beat("gancho", chuva["fala"], numero=chuva["numero"],
                           sub=chuva["sub"], local=chuva["point"]))
    else:
        beats.append(_beat("gancho", f"Em {hot['point']}, a máxima chega a {graus_inteiros(hot['max_c'])} graus.",
                           numero=f"{graus_inteiros(hot['max_c'])}°", sub="MAIOR MÁXIMA"))

    if brief.get("frase_ceu"):
        beats.append(_beat("ceu", brief["frase_ceu"]))

    # Grupos globais apenas para a FALA; cada cidade segue como linha isolada.
    # Não dividir um grupo falado em dois quadros: seus nomes ficam visíveis
    # durante a narração. Quadros com 5 a 8 linhas usam um modo compacto.
    grupos = agrupar_cidades_por_faixa(cities)
    por_nome = {cidade["nome"]: cidade for cidade in cities}
    paginas, lote, linhas = [], [], []
    for grupo in grupos:
        integrantes = [por_nome[nome] for nome in grupo["nomes"]]
        if linhas and len(linhas) + len(integrantes) > 4:
            paginas.append((lote, linhas))
            lote, linhas = [], []
        lote.append(grupo)
        linhas.extend(integrantes)
    if lote:
        paginas.append((lote, linhas))
    for lote, linhas in paginas:
        fala = " ".join(frase_faixa(g) for g in lote)
        beats.append(_beat("resumo", fala, cidades=linhas,
                           grupos_falados=lote, titulo="TEMPERATURAS POR REGIÃO"))

    # Complemento: o que não abriu o vídeo aparece aqui, uma vez só.
    if chuva_no_gancho:
        beats.append(_beat("frase", f"A maior máxima fica em {hot['point']}, com {graus_inteiros(hot['max_c'])} graus."))
    elif chuva is not None:  # chuva fraca: informa sem virar manchete
        beats.append(_beat("frase", chuva["fala"]))
    elif all(c.get("rain_mm") is not None for c in cards):
        beats.append(_beat("frase", f"Sem chuva significativa prevista {when} nos pontos acompanhados."))

    if cold and cold["point"] != hot["point"]:
        beats.append(_beat("frase", f"A menor mínima fica em {cold['point']}, com {graus_inteiros(cold['min_c'])} graus."))

    for d in (brief.get("dicas") or [])[:2]:
        beats.append(_beat("dica", d["fala"]))

    beats.append(_beat("cta", "Siga O Tempo SP e conte de qual bairro você acompanha a previsão.",
                       chamada="QUAL É O SEU BAIRRO?", sub="@otemposp · todo dia às 6h e às 18h"))
    return beats, cities


def render_brief(brief, destination):
    from hyperframes import gerar_hf as HF
    name = "bira" if brief["when"] == "hoje" else "bia"
    out = Path(destination)
    out.parent.mkdir(parents=True, exist_ok=True)
    package, beats, _, _ = HF.preparar(name, out, brief)
    # Céu do cenário e dica curta no quadro vêm do brief (antes: só sol/chuva e sem dicas).
    package["ceu"] = brief.get("ceu") or package.get("ceu", "sol")
    package["dicas_praticas"] = [d["tela"] for d in (brief.get("dicas") or [])[:1]]
    from compor import compor  # o gerar_hf já colocou a pasta hyperframes no sys.path
    (HF.BUILD / "pacote.json").write_text(json.dumps(package, ensure_ascii=False, indent=1), encoding="utf-8")
    (HF.AQUI / "index.html").write_text(compor(package), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(beats, ensure_ascii=False, indent=2))
    out.with_suffix(".txt").write_text(brief["caption"])
    return HF.renderizar(out, package)


def produce(snapshot, when):
    brief = summarise(json.loads(Path(snapshot).read_text()), when)
    return render_brief(brief, "output/bira.mp4" if when == "hoje" else "output/bia.mp4")


if __name__ == "__main__":
    produce(*sys.argv[1:])

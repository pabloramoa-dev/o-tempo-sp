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


def gancho_rotativo(locs, data, quando, *, ancora=None, canal=""):
    """Gancho de retenção por edição, com fatos validados e sem alarmismo."""
    from datetime import date, timedelta
    from math import isfinite
    def num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool) and isfinite(x)
    def valor(c, *keys):
        return next((c[k] for k in keys if num(c.get(k))), None)
    def nome(c):
        return c.get("name") or c.get("nome") or c.get("point")
    validos = [c for c in locs if nome(c) and valor(c, "max_c", "max") is not None]
    if not validos:
        return "Confira a previsão " + quando + "."
    try:
        dia = date.fromisoformat(str(data)[:10])
    except (ValueError, TypeError):
        dia = date.today()
    noite = quando == "amanhã"
    pub = dia - timedelta(days=int(noite))
    fase = sum(ord(ch) for ch in canal) % 12
    slot = pub.toordinal() * 2 + int(noite) + fase
    c = ancora if ancora in validos else validos[(slot // 2 + int(noite)) % len(validos)]
    n = nome(c)
    mx = graus_inteiros(valor(c, "max_c", "max"))
    mn0 = valor(c, "min_c", "min")
    mn = graus_inteiros(mn0) if mn0 is not None else None
    outros = [x for x in validos if nome(x) != n]
    outro = max(outros, key=lambda x: abs(valor(x, "max_c", "max") - mx), default=None)
    dif = graus_inteiros(valor(outro, "max_c", "max")) if outro else mx
    fato = f"{n}: {mx} graus {quando}."
    faixa = f"{n}: de {mn} a {mx} graus {quando}." if mn is not None else fato
    # 12 famílias: identificação, curiosidade, antecipação, contraste,
    # proteção, urgência, surpresa, pergunta, comparação, benefício,
    # informação específica e expectativa. Condições especiais têm gate.
    familias = {
        0: (f"Mora em {n}? {mx} graus {quando}.", f"Alô, {n}! Máxima de {mx} graus {quando}.", fato, f"{n}, sua máxima: {mx} graus {quando}."),
        1: (f"Quanto vai fazer em {n}? {mx} graus {quando}.", f"{n}: sabe qual a máxima {quando}? {mx} graus.", f"{fato} E na sua cidade?", f"{n}: como fica {quando}? {mx} graus."),
        2: (f"Planeje {quando}: {faixa}", f"Já se programe: {faixa}", f"Para {quando}, {faixa}", f"Antecipe seus planos: {fato}"),
        4: (f"Antes de sair, {fato}", f"Vai sair em {n}? {mx} graus {quando}.", f"Prepare-se: {faixa}", f"De olho na temperatura: {fato}"),
        7: (f"Vai fazer calor em {n}? {mx} graus {quando}.", f"Casaco ou roupa leve? {faixa}", f"Vai sair {quando}? {faixa}", f"Como se vestir em {n}? {faixa}"),
        8: (f"Compare as temperaturas: {fato}", f"Veja os números: {fato}", f"De cidade em cidade: {fato}", f"Compare com a sua rotina: {faixa}"),
        9: (f"Organize seu dia: {faixa}", f"Para planejar a rotina: {fato}", f"Seu dia em {n}: {mx} graus {quando}.", f"Programe sua saída: {fato}"),
        10: (fato, f"Máxima de {mx} graus em {n} {quando}.", faixa, f"{quando.capitalize()}, {n} pode chegar a {mx} graus."),
        11: (f"{fato} E as demais cidades?", f"{fato} Veja as outras temperaturas.", f"Começando por {n}: {mx} graus {quando}.", f"Primeiro, {fato}"),
    }
    if mn is not None and mx - mn >= 7:
        familias[3] = (f"De {mn} a {mx} graus em {n} {quando}.", f"{n}: mínima de {mn}, máxima de {mx} {quando}.", faixa, f"Do mínimo de {mn} ao máximo de {mx} graus em {n} {quando}.")
    if outro and abs(dif - mx) >= 4:
        familias[6] = (f"{n}: {mx} graus. {nome(outro)}: {dif} {quando}.", f"Olha a diferença {quando}: {n}, {mx}; {nome(outro)}, {dif} graus.", f"Temperaturas bem diferentes: {n}, {mx}; {nome(outro)}, {dif} graus {quando}.", f"{n} e {nome(outro)}: {mx} e {dif} graus {quando}.")
        familias[8] = familias[6][::-1]
    rajada = valor(c, "gust_kmh", "wind_gust_kmh", "rajada_kmh")
    if rajada is not None and rajada >= 60:
        familias[5] = (f"Atenção em {n}: rajadas fortes {quando}.", f"Vento forte previsto em {n} {quando}.", f"{n}: cuidado com as rajadas {quando}.", f"De olho no vento forte em {n} {quando}.")
    elif mx >= 38:
        familias[5] = (f"Atenção em {n}: máxima de {mx} graus {quando}.", f"{n}: calor intenso, {mx} graus {quando}.", f"Cuidado com o calor em {n}: {mx} graus {quando}.", f"{mx} graus previstos em {n} {quando}: cuide-se.")
    # Se um fenômeno não existe, mantém a alternância sem fabricar o fato.
    k = slot % 12
    fallback = {3: 9, 5: 11, 6: 0}
    k = k if k in familias else fallback.get(k, 10)
    return familias[k][(slot // 12) % 4]


def engajamento_rotativo(data, quando, local="", canal=""):
    """Um pedido útil por edição, com rodízio independente do gancho."""
    from datetime import date, timedelta
    try:
        dia = date.fromisoformat(str(data)[:10])
    except (ValueError, TypeError):
        dia = date.today()
    noite = quando == "amanhã"
    pub = dia - timedelta(days=int(noite))
    slot = pub.toordinal() * 2 + int(noite) + sum(ord(ch) for ch in canal)
    familias = (
        ("Envie a previsão a quem vai sair.", "Compartilhe com quem mora na região.", "Manda pra quem precisa dessa previsão.", "Envie para quem vai viajar."),
        ("Qual sua cidade? Comente aqui.", "Como está o tempo aí? Comente.", "De qual bairro você nos acompanha?", "Qual cidade quer ver por aqui?"),
        ("Salve para consultar antes de sair.", "Guarde esta previsão para seu dia.", "Salve o boletim para planejar.", "Salve para conferir mais tarde."),
        ("Siga para acompanhar a previsão diária.", "Siga e acompanhe o tempo na região.", "Acompanhe o perfil para novos boletins.", "Siga para conferir a próxima previsão."),
    )
    return familias[slot % len(familias)][(slot // len(familias)) % 4]


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
                  gancho_rotativo(cards, brief.get("date"), when, ancora=hot, canal="sp"),
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
    chamada = engajamento_rotativo(brief.get("date"), when, destino, "sp")
    beats.append(beat("cta", chamada, chamada="ACOMPANHE A PREVISÃO",
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

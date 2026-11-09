"""Chuva do boletim: faixas de intensidade, janela de horário e destaque, sem exagero."""
import math

# Abaixo disso o modelo está indicando chuvisco/ruído: não vira manchete.
SECO_ATE_MM = 0.5
FRACA_ATE_MM = 2.0
MODERADA_ATE_MM = 10.0
# Hora com pelo menos este volume conta como "hora com chuva" na janela.
HORA_CHUVOSA_MM = 0.2

ORDEM = {"seco": 0, "fraca": 1, "moderada": 2, "forte": 3}


def classificar(mm) -> str:
    """seco (< 0,5 mm) · fraca (0,5 a 2) · moderada (2 a 10) · forte (10 ou mais)."""
    if mm is None:
        raise ValueError("Volume de chuva ausente")
    v = float(mm)
    if not math.isfinite(v) or v < 0:
        raise ValueError("Previsão de chuva inválida")
    if v < SECO_ATE_MM:
        return "seco"
    if v < FRACA_ATE_MM:
        return "fraca"
    if v < MODERADA_ATE_MM:
        return "moderada"
    return "forte"


def janela_de_chuva(horas: list) -> tuple[int, int] | None:
    """Recebe [(hora_local, mm), ...] e devolve (início, fim) do bloco mais chuvoso.

    Horas vizinhas (com no máximo 1 h seca entre elas) formam um bloco.
    O fim é exclusivo: (15, 18) = das 15h às 18h.
    """
    chuvosas = sorted((int(h), float(mm)) for h, mm in horas if mm is not None and float(mm) >= HORA_CHUVOSA_MM)
    if not chuvosas:
        return None
    blocos, atual = [], [chuvosas[0]]
    for h, mm in chuvosas[1:]:
        if h - atual[-1][0] <= 2:
            atual.append((h, mm))
        else:
            blocos.append(atual)
            atual = [(h, mm)]
    blocos.append(atual)
    melhor = max(blocos, key=lambda b: sum(mm for _, mm in b))
    return melhor[0][0], melhor[-1][0] + 1


def texto_janela(janela, falado: bool = True) -> str:
    """'entre 15 e 18 horas' (fala) ou '15h–18h' (legenda). Vazio sem janela."""
    if not janela:
        return ""
    ini, fim = janela
    if fim - ini >= 10:
        return "ao longo do dia" if falado else "várias horas do dia"
    if falado:
        if fim >= 24:
            return f"a partir das {ini} horas"
        return f"entre {ini} e {fim} horas"
    return f"{ini}h–{'24' if fim >= 24 else fim}h"


def maior_chuva(cards: list[dict], quando: str) -> dict | None:
    """Seleciona somente UM ponto de maior acumulado — e só se for chuva de verdade.

    Comparação usa milímetros reais; empate fica com a primeira localidade na
    ordem editorial. Volumes abaixo de 0,5 mm (chuvisco/ruído do modelo) NÃO
    viram destaque. Para chuva moderada ou forte, o volume falado é arredondado
    para cima ("até N milímetros"), para não afirmar menos que o previsto.
    """
    if quando not in {"hoje", "amanhã"}:
        raise ValueError("Turno inválido")
    validos = []
    for card in cards:
        value = card.get("rain_mm")
        if value is None:
            continue
        classificar(value)  # valida (negativo/NaN levanta erro)
        validos.append((float(value), card))
    if not validos:
        return None
    volume, cidade = max(validos, key=lambda item: item[0])
    classe = classificar(volume)
    if classe == "seco":
        return None
    janela = cidade.get("rain_window")
    jt = texto_janela(janela)
    sufixo = f" {jt}" if jt else ""
    nome = cidade["point"]
    if classe == "fraca":
        mm = None
        fala = f"{nome} pode ter garoa ou chuva fraca {quando}{sufixo}."
        numero, sub = "< 2 mm", "CHUVA FRACA"
    else:
        mm = math.ceil(volume)
        unidade = "milímetro" if mm == 1 else "milímetros"
        if classe == "forte":
            fala = f"Atenção: {nome} pode ter chuva forte {quando}{sufixo}, até {mm} {unidade}."
            sub = "CHUVA FORTE PREVISTA"
        else:
            fala = f"{nome} pode ter até {mm} {unidade} de chuva {quando}{sufixo}."
            sub = "MAIOR CHUVA PREVISTA"
        numero = f"{mm} mm"
    com_chuva = sum(1 for v, _ in validos if v >= SECO_ATE_MM)
    return {
        "point": nome,
        "rain_mm": volume,
        "mm_fala": mm,
        "classe": classe,
        "janela": janela,
        "fala": fala,
        "numero": numero,
        "sub": sub,
        "locais_com_chuva": com_chuva,
        "locais_total": len(validos),
    }

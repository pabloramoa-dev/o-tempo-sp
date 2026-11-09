"""Seleção de destaque de chuva do boletim, sem inventar valores."""
import math


def maior_chuva(cards: list[dict], quando: str) -> dict | None:
    """Seleciona somente UM ponto de maior acumulado positivo de chuva.

    Comparação usa milímetros reais antes de arredondar; empate usa a primeira
    localidade na ordem editorial. O volume falado é arredondado para cima
    para não afirmar um limite inferior ao acumulado previsto.
    """
    if quando not in {"hoje", "amanhã"}:
        raise ValueError("Turno inválido")
    validos = []
    for card in cards:
        value = card.get("rain_mm")
        if value is None:
            continue
        volume = float(value)
        if not math.isfinite(volume) or volume < 0:
            raise ValueError("Previsão de chuva inválida")
        validos.append((volume, card))
    if not validos:
        return None
    volume, cidade = max(validos, key=lambda item: item[0])
    if volume <= 0:
        return None
    mm = math.ceil(volume)
    unidade = "milímetro" if mm == 1 else "milímetros"
    return {
        "point": cidade["point"],
        "rain_mm": volume,
        "mm_fala": mm,
        "fala": f'{cidade["point"]} poderá ter até {mm} {unidade} de chuva {quando}.',
    }

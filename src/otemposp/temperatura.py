"""Temperaturas inteiras para locução, telas e legenda — sempre o MESMO número."""
import math


def graus_inteiros(valor: float) -> int:
    """Arredondamento convencional (meio para cima): 17,4 → 17; 17,5 → 18; 33,9 → 34.

    Antes a fração era descartada (33,9 virava 33), o que diminuía o calor e
    fazia o vídeo divergir da legenda. Agora vídeo, quadro e legenda usam
    esta mesma função.
    """
    return int(math.floor(float(valor) + 0.5))


def juntar_nomes(nomes: list[str]) -> str:
    """Enumeração natural, inclusive quando cidades estão em regiões distintas."""
    if not nomes:
        raise ValueError("Grupo de localidades vazio")
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def agrupar_cidades_por_faixa(cidades: list[dict]) -> list[dict]:
    """Agrupa por mínima E máxima inteiras, nunca por uma só temperatura.

    Não altera os registros originais nem seus valores meteorológicos.
    """
    grupos = {}
    for cidade in cidades:
        faixa = (graus_inteiros(cidade["min"]), graus_inteiros(cidade["max"]))
        if faixa not in grupos:
            grupos[faixa] = {"min": faixa[0], "max": faixa[1], "nomes": []}
        grupos[faixa]["nomes"].append(cidade["nome"])
    return list(grupos.values())


def frase_faixa(grupo: dict) -> str:
    """Uma única referência de temperatura para todas as cidades do grupo."""
    return f'{juntar_nomes(grupo["nomes"])}, de {grupo["min"]} a {grupo["max"]} graus.'

"""Temperaturas inteiras para locução e telas; dados meteorológicos seguem exatos."""


def graus_inteiros(valor: float) -> int:
    """Descarta a fração sem arredondar: 17,6 °C é narrado como 17 graus."""
    return int(float(valor))


def juntar_nomes(nomes: list[str]) -> str:
    """Enumeração natural, inclusive quando cidades estão em regiões distintas."""
    if not nomes:
        raise ValueError("Grupo de localidades vazio")
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def agrupar_cidades_por_faixa(cidades: list[dict]) -> list[dict]:
    """Agrupa por mínima E máxima inteiras, nunca por uma só temperatura.

    Exemplo: Pirituba, Sé e Santo Amaro com 17/28 ficam no mesmo grupo,
    mesmo quando originalmente apareceriam em quadros de quatro diferentes.
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

"""Condição do céu por período (manhã, tarde, noite) a partir do symbol_code da MET."""
from __future__ import annotations
from collections import Counter

PERIODOS = (("manha", "manhã", 6, 12), ("tarde", "tarde", 12, 18), ("noite", "noite", 18, 24))

# Gravidade crescente: quando há empate, vence a condição mais severa.
GRAVIDADE = {"sol": 0, "poucas nuvens": 1, "nublado": 2, "neblina": 3, "chuva": 4, "trovoadas": 5}

EMOJI = {"sol": "☀️", "poucas nuvens": "🌤️", "nublado": "☁️", "neblina": "🌫️",
         "chuva": "🌧️", "trovoadas": "⛈️"}


def categoria(symbol: str | None) -> str | None:
    """Traduz o symbol_code da MET Norway (ex.: 'rainshowers_day') para português."""
    if not symbol:
        return None
    base = symbol.split("_")[0]
    if "thunder" in base:
        return "trovoadas"
    if any(k in base for k in ("rain", "sleet", "snow")):
        return "chuva"
    if "fog" in base:
        return "neblina"
    if base == "cloudy":
        return "nublado"
    if base == "partlycloudy":
        return "poucas nuvens"
    if base in ("fair", "clearsky"):
        return "sol"
    return None


def resumir_periodo(horas: list[tuple[int, str | None, float]]) -> str | None:
    """horas = [(hora_local, categoria, mm)]. Precisa de 3 h ou mais no período.

    Trovoada em qualquer hora domina. Chuva vence se ocupar 2 h ou mais, ou se
    somar 1 mm ou mais. Caso contrário, a condição mais frequente.
    """
    cats = [(c, mm) for _, c, mm in horas if c]
    if len(cats) < 3:
        return None
    if any(c == "trovoadas" for c, _ in cats):
        return "trovoadas"
    chuva_h = sum(1 for c, mm in cats if c == "chuva")
    chuva_mm = sum(mm or 0 for _, mm in cats)
    if chuva_h >= 2 or chuva_mm >= 1.0:
        return "chuva"
    secas = [c if c != "chuva" else "nublado" for c, _ in cats]
    contagem = Counter(secas)
    return max(contagem, key=lambda c: (contagem[c], GRAVIDADE[c]))


def periodos(horas: list[tuple[int, str | None, float]]) -> dict:
    """{'manha': 'sol', 'tarde': 'chuva', 'noite': 'nublado'} (só períodos cobertos)."""
    out = {}
    for chave, _, ini, fim in PERIODOS:
        r = resumir_periodo([h for h in horas if ini <= h[0] < fim])
        if r:
            out[chave] = r
    return out


def predominante(lista_de_periodos: list[dict], chave: str) -> str | None:
    """Condição mais comum entre os pontos, para um período; empate → mais severa."""
    vals = [p.get(chave) for p in lista_de_periodos if p.get(chave)]
    if not vals:
        return None
    contagem = Counter(vals)
    return max(contagem, key=lambda c: (contagem[c], GRAVIDADE[c]))


def frase_falada(resumo: dict) -> str | None:
    """'De manhã, sol; à tarde, chuva; à noite, nublado.'"""
    partes = []
    rot = {"manha": "de manhã", "tarde": "à tarde", "noite": "à noite"}
    falado = {"sol": "sol", "poucas nuvens": "sol entre nuvens", "nublado": "céu nublado",
              "neblina": "neblina", "chuva": "chuva", "trovoadas": "chuva com trovoadas"}
    for chave, _, _, _ in PERIODOS:
        if resumo.get(chave):
            texto = falado[resumo[chave]]
            if chave == "noite":
                texto = {"sol": "céu limpo", "sol entre nuvens": "poucas nuvens"}.get(texto, texto)
            partes.append(f"{rot[chave]}, {texto}")
    if not partes:
        return None
    texto = "; ".join(partes) + "."
    return texto[0].upper() + texto[1:]


def linha_legenda(resumo: dict) -> str | None:
    """'☀️ manhã: sol · 🌧️ tarde: chuva · ☁️ noite: nublado'"""
    def nome(c):
        v = resumo[c]
        if c == "noite" and v == "sol":
            return "🌙", "céu limpo"
        return ("🌙" if c == "noite" and v == "poucas nuvens" else EMOJI[v]), v
    partes = [f"{nome(c)[0]} {rot}: {nome(c)[1]}" for c, rot, _, _ in PERIODOS if resumo.get(c)]
    return " · ".join(partes) if partes else None

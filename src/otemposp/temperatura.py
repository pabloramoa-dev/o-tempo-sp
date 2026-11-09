"""Temperaturas inteiras para locução e telas; dados meteorológicos seguem exatos."""


def graus_inteiros(valor: float) -> int:
    """Descarta a fração sem arredondar: 17,6 °C é narrado como 17 graus."""
    return int(float(valor))

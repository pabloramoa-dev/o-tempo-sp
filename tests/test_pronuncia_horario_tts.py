"""A pronúncia expande horários somente na entrada do TTS."""

import pytest
from src.otemposp.characters.kokoro import normalizar_horario_para_voz


@pytest.mark.parametrize("entrada, esperado", [
    ("A chuva começa às 17H.", "A chuva começa às 17 horas."),
    ("Às 17h, pancadas de chuva.", "Às 17 horas, pancadas de chuva."),
    ("Depois das 17:00, atenção.", "Depois das 17 horas, atenção."),
    ("Às 17h30 terá vento.", "Às 17 horas e 30 minutos terá vento."),
    ("Às 18:05, atualização.", "Às 18 horas e 5 minutos, atualização."),
    ("À 1H começa o plantão.", "À 1 hora começa o plantão."),
    ("Hoje às 17 h, no Rio.", "Hoje às 17 horas, no Rio."),
    ("Ventos de 40 km/h.", "Ventos de 40 km/h."),
    ("Chuva a partir de 17 horas.", "Chuva a partir de 17 horas."),
])
def test_horario_falado(entrada, esperado):
    assert normalizar_horario_para_voz(entrada) == esperado

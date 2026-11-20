"""Verifica a normalização do próprio motor TTS, sem importar bibliotecas de áudio."""

import ast
from pathlib import Path
import re
import pytest


_CODIGO = (Path(__file__).resolve().parents[1] / "src/otemposp/characters/kokoro.py").read_text(encoding="utf-8")
_ARVORE = ast.parse(_CODIGO)
_PONTOS = [
    n for n in _ARVORE.body
    if (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_HORA_TTS_RE" for t in n.targets))
    or (isinstance(n, ast.FunctionDef) and n.name == "normalizar_horario_para_voz")
]
assert len(_PONTOS) == 2, "A normalização precisa existir no motor de voz"
_ESCOPO = {"re": re}
exec(compile(ast.Module(body=_PONTOS, type_ignores=[]), "<normalizacao_horas>", "exec"), _ESCOPO)
normalizar_horario_para_voz = _ESCOPO["normalizar_horario_para_voz"]


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

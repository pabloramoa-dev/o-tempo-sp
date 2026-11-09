"""Boletim com previsão real: coleta → brief editorial → vídeo.

Usa o MESMO motor (weather.py) e o MESMO brief (editorial.py) cobertos pelos
testes — antes este arquivo tinha uma cópia própria da lógica.
"""
import json
import sys
from pathlib import Path
from scripts.met_forecast import collect
from scripts.produce import render_brief, pauta as pauta_de_producao
from src.otemposp.editorial import summarise


def pauta(brief):
    """Usa a mesma pauta do renderizador para evitar narrações divergentes."""
    return pauta_de_producao(brief)


def preparar(when, session=None):
    snap = collect(int(when == "amanhã"), session=session)
    brief = summarise(snap, when)
    out = Path("output")
    out.mkdir(exist_ok=True)
    for name, value in (("snapshot", snap), ("brief", brief)):
        (out / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False, indent=1))
    (out / "legenda.txt").write_text(brief["caption"], encoding="utf-8")
    return snap, brief


def run(when):
    _, brief = preparar(when)
    print(brief["caption"])
    render_brief(brief, Path("output") / ("bira.mp4" if when == "hoje" else "bia.mp4"))


if __name__ == "__main__":
    run(sys.argv[1])

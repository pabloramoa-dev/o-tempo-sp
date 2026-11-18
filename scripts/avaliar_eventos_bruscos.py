"""Avalia dados meteorológicos normalizados e salva candidatos a alertas.

Uso: python -m scripts.avaliar_eventos_bruscos --entrada hourly.json
Formato: {"cidades":[{"nome":"Cidade","hourly":[{"time":"...-03:00",
"precipitation_mm":20,"temperature_c":30,"wind_gust_kmh":55,
"weather_code":95}]}]}
Não publica, não altera credenciais nem interpreta avisos oficiais não verificados.
"""
import argparse
import json
from pathlib import Path
from src.eventos_bruscos import detectar_eventos


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entrada", type=Path, required=True)
    p.add_argument("--saida", type=Path, default=Path("output/eventos_bruscos.json"))
    a = p.parse_args()
    entrada = json.loads(a.entrada.read_text(encoding="utf-8"))
    cidades = entrada.get("cidades")
    if not isinstance(cidades, list):
        raise ValueError("Campo cidades obrigatório; precisa ser uma lista")
    eventos = detectar_eventos(cidades)
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    a.saida.write_text(json.dumps({"eventos": eventos, "quantidade": len(eventos),
                         "autopublicacao": False}, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print(f"{len(eventos)} candidatos gravados em {a.saida}")


if __name__ == "__main__":
    main()

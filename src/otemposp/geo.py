"""Divisão editorial de São Paulo (32 subprefeituras / 8 setores)."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]

@lru_cache(maxsize=1)
def config() -> dict:
    return yaml.safe_load((ROOT / 'config/locais_sp.yaml').read_text(encoding='utf-8'))


def locations(tier: int = 1) -> list[dict]:
    return [p for p in config()['locations'] if p['tier'] <= tier]


def sectors() -> dict:
    return config()['sectors']


def validate() -> None:
    c = config()
    expected = len(c['sectors'])
    assert expected == 8, f'esperados 8 setores, encontrado {expected}'
    subpref = [name.casefold() for s in c['sectors'].values() for name in s['subprefeituras']]
    assert len(subpref) == 32 and len(set(subpref)) == 32, '32 subprefeituras únicas obrigatórias'
    pts = c['locations']
    assert len({x['id'] for x in pts}) == len(pts), 'IDs de locais duplicados'
    for key in c['sectors']:
        assert len([p for p in pts if p['sector'] == key and p['tier'] == 1]) == 1, f'âncora ausente/duplicada: {key}'
    for p in pts:
        assert p['sector'] in c['sectors'], p
        assert -24.0 < p['latitude'] < -23.3 and -47.0 < p['longitude'] < -46.2, f'coordenada suspeita: {p}'


if __name__ == '__main__':
    validate()
    print(f'OK: {len(sectors())} setores, 32 subprefeituras, {len(locations(2))} pontos de coleta')

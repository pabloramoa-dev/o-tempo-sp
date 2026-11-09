"""8 setores da capital (32 subprefeituras) e 3 setores costeiros."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
GRUPOS = ('norte', 'centro', 'oeste', 'leste', 'sul', 'litoral')

@lru_cache(maxsize=1)
def config() -> dict:
    return yaml.safe_load((ROOT / 'config/locais_sp.yaml').read_text(encoding='utf-8'))


def locations(tier: int = 1) -> list[dict]:
    return [p for p in config()['locations'] if p['tier'] <= tier]


def sectors() -> dict:
    return config()['sectors']


def validate() -> None:
    c = config()
    setores = c['sectors']
    capital = [s for s in setores.values() if s['group'] != 'litoral']
    litoral = [s for s in setores.values() if s['group'] == 'litoral']
    assert len(capital) == 8 and len(litoral) == 3, 'esperados 8 setores da capital e 3 do litoral'
    assert {s['group'] for s in setores.values()} == set(GRUPOS), 'região ausente'
    subpref = [name.casefold() for s in capital for name in s['subprefeituras']]
    assert len(subpref) == 32 and len(set(subpref)) == 32, '32 subprefeituras únicas obrigatórias'
    assert all(not s['subprefeituras'] for s in litoral), 'litoral não possui subprefeitura da capital'
    pts = c['locations']
    assert len({x['id'] for x in pts}) == len(pts), 'IDs de locais duplicados'
    for key in setores:
        assert len([p for p in pts if p['sector'] == key and p['tier'] == 1]) == 1, f'âncora ausente/duplicada: {key}'
    for p in pts:
        assert p['sector'] in setores, p
        lat, lon = float(p['latitude']), float(p['longitude'])
        if setores[p['sector']]['group'] == 'litoral':
            assert -25.5 < lat < -23.0 and -48.4 < lon < -44.0, f'coordenada costeira suspeita: {p}'
        else:
            assert -24.0 < lat < -23.3 and -47.0 < lon < -46.2, f'coordenada da capital suspeita: {p}'


if __name__ == '__main__':
    validate()
    print(f'OK: {len(sectors())} setores, 32 subprefeituras da capital, {len(locations(2))} pontos cadastrados')

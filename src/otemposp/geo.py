"""Geografia editorial: oito setores da capital e três do litoral paulista.

O rodízio é reprodutível e depende somente da data local da PUBLICAÇÃO
e do turno. Reexecuções do mesmo Reel usam os mesmos locais.
"""
from __future__ import annotations
from datetime import date
from functools import lru_cache
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
GRUPOS = ('norte', 'centro', 'oeste', 'leste', 'sul', 'litoral')

@lru_cache(maxsize=1)
def config() -> dict:
    return yaml.safe_load((ROOT / 'config/locais_sp.yaml').read_text(encoding='utf-8'))


def locations(tier: int = 1) -> list[dict]:
    """Catálogo até o tier selecionado; tier 1 mantém âncoras para fixtures."""
    return [p for p in config()['locations'] if p['tier'] <= tier]


def sectors() -> dict:
    return config()['sectors']


def daily_locations(published_on: date, when: str = 'hoje') -> list[dict]:
    """Uma localidade diferente por setor a cada dia, em cada edição.

    - 06h (hoje) e 18h (amanhã) usam opções diferentes no mesmo dia.
    - A edição do dia seguinte não repete a localidade do dia anterior.
    - As 11 regiões são obrigatórias e não dependem de sorteio ou estado remoto.
    - O dia é a data LOCAL de publicação, não a data da previsão da Bia.
    """
    if not isinstance(published_on, date):
        raise TypeError('published_on deve ser datetime.date local')
    if when not in ('hoje', 'amanhã'):
        raise ValueError('turno inválido para rodízio')
    shift = 0 if when == 'hoje' else 2
    chosen = []
    for position, key in enumerate(sectors()):
        options = [p for p in locations(2) if p['sector'] == key]
        if len(options) < 3:
            raise ValueError(f'Faltam opções para rodízio no setor {key}')
        index = (published_on.toordinal() + shift + position * 3) % len(options)
        chosen.append(dict(options[index]))
    if len(chosen) != 11 or len({p['sector'] for p in chosen}) != 11:
        raise ValueError('Rodízio sem cobertura integral de capital e litoral')
    return chosen


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
    assert len({x['name'].casefold() for x in pts}) == len(pts), 'Nomes de locais duplicados'
    for key in setores:
        subset = [p for p in pts if p['sector'] == key]
        assert len(subset) >= 3, f'Rodízio com poucas opções: {key}'
        assert len([p for p in subset if p['tier'] == 1]) == 1, f'âncora ausente/duplicada: {key}'
    for p in pts:
        assert p['sector'] in setores, p
        lat, lon = float(p['latitude']), float(p['longitude'])
        if setores[p['sector']]['group'] == 'litoral':
            assert -25.5 < lat < -23.0 and -48.4 < lon < -44.0, f'coordenada costeira suspeita: {p}'
        else:
            assert -24.0 < lat < -23.3 and -47.0 < lon < -46.2, f'coordenada da capital suspeita: {p}'


if __name__ == '__main__':
    validate()
    print(f'OK: {len(sectors())} setores, 32 subprefeituras, {len(locations(2))} locais no rodízio')

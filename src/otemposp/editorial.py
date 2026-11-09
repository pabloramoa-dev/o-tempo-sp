"""Roteiros factuais: não converter estimativa de modelo em alerta oficial."""
from __future__ import annotations
from datetime import datetime, timezone
from .geo import sectors
from .temperatura import graus_inteiros


def _mm(value) -> str:
    return f'{float(value):g}'.replace('.', ',')


def summarise(snapshot: dict, when: str = 'hoje') -> dict:
    if when not in {'hoje', 'amanhã'}:
        raise ValueError('turno inválido')
    pts = snapshot['points']
    anchors = {}
    for p in pts:
        anchors.setdefault(p['sector'], p)
    if set(anchors) != set(sectors()) or len(pts) != len(sectors()):
        raise ValueError('É obrigatória previsão de cada setor da capital e do litoral')
    cards = []
    for key, sector in sectors().items():
        p = anchors[key]
        cards.append({'sector': key, 'short': sector['short'], 'point': p['name'],
                      'max_c': p['max_c'], 'min_c': p['min_c'],
                      'rain_pct': p.get('rain_probability_pct'),
                      'rain_mm': p.get('rain_mm')})
    # Fonte com probabilidade (Open-Meteo) usa %; fonte sem ela (MET Norway) usa mm.
    use_pct = all(c['rain_pct'] is not None for c in cards)
    if not use_pct and any(c['rain_mm'] is None for c in cards):
        raise ValueError('Sem probabilidade nem volume de chuva em todos os setores')
    hottest = max(cards, key=lambda p: p['max_c'])
    wettest = max(cards, key=lambda p: p['rain_pct'] if use_pct else p['rain_mm'])
    coldest = min(cards, key=lambda p: p['min_c'])
    subject = 'hoje' if when == 'hoje' else 'amanhã'
    opening = f'O tempo em São Paulo {subject}, região por região!'
    commentary = (
        f'Entre os pontos acompanhados, a maior máxima prevista é em {hottest["point"]}, '
        f'com {graus_inteiros(hottest["max_c"])} graus. '
        f'A menor mínima aparece em {coldest["point"]}, com {graus_inteiros(coldest["min_c"])} graus. '
        'Confira todas as regiões da capital e do litoral na tela e compartilhe. '
        'A previsão é estimativa por ponto, não previsão por rua.'
    )
    script = opening + ' ' + commentary
    if use_pct:
        rows = '\n'.join(f'{p["short"]} ({p["point"]}): {p["min_c"]:g}° a {p["max_c"]:g}°C · '
                         f'chuva {p["rain_pct"]:g}%' for p in cards)
        note = 'Probabilidade diária de chuva não é chance por hora. '
    else:
        rows = '\n'.join(f'{p["short"]} ({p["point"]}): {p["min_c"]:g}° a {p["max_c"]:g}°C · '
                         f'chuva {_mm(p["rain_mm"])} mm' for p in cards)
        note = 'Chuva = volume previsto no dia, em milímetros. '
    caption = (
        f'☀️ O TEMPO SP — São Paulo {subject} ({snapshot["forecast_date"]})\n\n'
        + rows
        + '\n\nPrevisão por pontos representativos, sujeita a mudanças. '
        + note
        + f'Dados: {snapshot["source"]}. #OTempoSP #PrevisaoSP #SaoPaulo'
    )
    return {'when': when, 'date': snapshot['forecast_date'], 'script': script,
            'cards': cards, 'caption': caption, 'hottest': hottest, 'wettest': wettest,
            'rain_metric': 'pct' if use_pct else 'mm',
            'is_fixture': snapshot.get('is_fixture', False)}

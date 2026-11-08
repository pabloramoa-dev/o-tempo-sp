"""Roteiros factuais: não converter estimativa de modelo em alerta oficial."""
from __future__ import annotations
from datetime import datetime, timezone
from .geo import sectors


def summarise(snapshot: dict, when: str = 'hoje') -> dict:
    if when not in {'hoje', 'amanhã'}:
        raise ValueError('turno inválido')
    pts = snapshot['points']
    anchors = {}
    for p in pts:
        anchors.setdefault(p['sector'], p)
    if len(anchors) != 8:
        raise ValueError('É obrigatória previsão de todos os 8 setores')
    cards = []
    for key, sector in sectors().items():
        p = anchors[key]
        cards.append({'sector': key, 'short': sector['short'], 'point': p['name'],
                      'max_c': p['max_c'], 'min_c': p['min_c'],
                      'rain_pct': p['rain_probability_pct']})
    hottest = max(cards, key=lambda p: p['max_c'])
    wettest = max(cards, key=lambda p: p['rain_pct'])
    coldest = min(cards, key=lambda p: p['min_c'])
    subject = 'hoje' if when == 'hoje' else 'amanhã'
    opening = f'O tempo em São Paulo {subject}, região por região!'
    commentary = (
        f'Entre os pontos acompanhados, a maior máxima prevista é em {hottest["point"]}, '
        f'com {hottest["max_c"]:g} graus. '
        f'A menor mínima aparece em {coldest["point"]}, com {coldest["min_c"]:g} graus. '
        f'A maior probabilidade diária de chuva na amostra é em {wettest["point"]}, '
        f'com {wettest["rain_pct"]:g} por cento. '
        'Confira os oito setores na tela e compartilhe com alguém do seu bairro. '
        'A previsão é estimativa por ponto, não previsão por rua.'
    )
    script = opening + ' ' + commentary
    caption = (
        f'☀️ O TEMPO SP — São Paulo {subject} ({snapshot["forecast_date"]})\n\n'
        + '\n'.join(f'{p["short"]} ({p["point"]}): {p["min_c"]:g}° a {p["max_c"]:g}°C · '
                    f'chuva {p["rain_pct"]:g}%' for p in cards)
        + '\n\nPrevisão por pontos representativos, sujeita a mudanças. '
          'Probabilidade diária de chuva não é chance por hora. '
          f'Fonte: {snapshot["source"]}. #OTempoSP #PrevisaoSP #SaoPaulo'
    )
    return {'when': when, 'date': snapshot['forecast_date'], 'script': script,
            'cards': cards, 'caption': caption, 'hottest': hottest, 'wettest': wettest,
            'is_fixture': snapshot.get('is_fixture', False)}

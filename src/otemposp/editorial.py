"""Brief editorial ÚNICO do boletim (vídeo + legenda).

Regras: não converter estimativa de modelo em alerta oficial; o mesmo número
(arredondado do mesmo jeito) no vídeo, no quadro e na legenda; chuva só vira
destaque quando é chuva de verdade.
"""
from __future__ import annotations
from datetime import date
from .geo import sectors
from .temperatura import graus_inteiros
from .chuva import maior_chuva, classificar, texto_janela, ORDEM
from . import ceu as CEU
from . import alertas as ALERTAS

DIAS = ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo']
LIMIAR_CALOR = 32
LIMIAR_FRIO = 18
LIMIAR_UV = 8
LIMIAR_RAJADA = 60
LIMIAR_AMPLITUDE = 10


def _mm(value) -> str:
    return f'{float(value):g}'.replace('.', ',')


def _card(p: dict, short: str) -> dict:
    return {'sector': p['sector'], 'short': short, 'point': p['name'],
            'tier': p.get('tier', 1),
            'max_c': p['max_c'], 'min_c': p['min_c'],
            'rain_pct': p.get('rain_probability_pct'),
            'rain_mm': p.get('rain_mm'),
            'rain_window': p.get('rain_window'),
            'periods': p.get('periods') or {},
            'rh_min': p.get('rh_min'), 'uv_max': p.get('uv_max'),
            'gust_kmh': p.get('gust_kmh')}


def ceu_visual(cards: list[dict], resumo: dict, chuva: dict | None, hottest: dict) -> str:
    """Cenário do vídeo: tempestade, chuva, calor, frio, nublado ou sol."""
    classe = chuva['classe'] if chuva else 'seco'
    if classe == 'forte' or any('trovoadas' in c['periods'].values() for c in cards):
        return 'tempestade'
    if classe == 'moderada' or 'chuva' in (resumo.get('manha'), resumo.get('tarde')):
        return 'chuva'
    if graus_inteiros(hottest['max_c']) >= LIMIAR_CALOR:
        return 'calor'
    if max(graus_inteiros(c['max_c']) for c in cards) <= LIMIAR_FRIO:
        return 'frio'
    principal = resumo.get('tarde') or resumo.get('manha') or resumo.get('noite')
    if principal in ('nublado', 'neblina'):
        return 'nublado'
    return 'sol'


def dicas_praticas(cards: list[dict], chuva: dict | None, ceu: str, hottest: dict) -> list[dict]:
    """Até 2 dicas acionáveis, por prioridade. Cada uma tem 'fala' e 'tela' (curta)."""
    dicas = []
    if chuva and ORDEM[chuva['classe']] >= ORDEM['moderada']:
        jt = texto_janela(chuva.get('janela'))
        quando = f', principalmente {jt}' if jt and jt != 'ao longo do dia' else ''
        tela = 'LEVE GUARDA-CHUVA'
        if chuva.get('janela') and jt != 'ao longo do dia':
            tela += ' · ' + texto_janela(chuva['janela'], falado=False).upper()
        dicas.append({'fala': f'Leve o guarda-chuva{quando}.', 'tela': tela})
    minimas = [graus_inteiros(c['min_c']) for c in cards]
    maximas = [graus_inteiros(c['max_c']) for c in cards]
    if max(maximas) - min(minimas) >= LIMIAR_AMPLITUDE and min(minimas) <= LIMIAR_FRIO:
        dicas.append({'fala': f'Começo do dia fresco e tarde mais quente, de {min(minimas)} a '
                              f'{max(maximas)} graus: vale sair com um casaco leve.',
                      'tela': 'CASACO LEVE DE MANHÃ'})
    umidades = [c['rh_min'] for c in cards if c.get('rh_min') is not None]
    if umidades and min(umidades) <= 20:
        dicas.append({'fala': f'Umidade do ar perto de {min(umidades)} por cento à tarde, nível de alerta: '
                              'beba água e evite exercício ao ar livre no meio da tarde.',
                      'tela': 'AR MUITO SECO · BEBA ÁGUA'})
    elif umidades and min(umidades) <= 30:
        dicas.append({'fala': f'Ar seco, com umidade perto de {min(umidades)} por cento à tarde: '
                              'beba bastante água.',
                      'tela': 'AR SECO · BEBA ÁGUA'})
    if graus_inteiros(hottest['max_c']) >= LIMIAR_CALOR:
        dicas.append({'fala': 'Calor forte: beba água e evite o sol do meio-dia.',
                      'tela': 'CALOR FORTE · HIDRATE-SE'})
    uvs = [c['uv_max'] for c in cards if c.get('uv_max') is not None]
    if uvs and max(uvs) >= LIMIAR_UV and ceu not in ('chuva', 'tempestade', 'nublado'):
        dicas.append({'fala': 'Índice ultravioleta muito alto: use protetor solar.',
                      'tela': 'UV MUITO ALTO · PROTETOR'})
    rajadas = [c['gust_kmh'] for c in cards if c.get('gust_kmh') is not None]
    if rajadas and max(rajadas) >= LIMIAR_RAJADA:
        dicas.append({'fala': f'Rajadas de vento podem chegar a {max(rajadas)} quilômetros por hora.',
                      'tela': 'RAJADAS DE VENTO'})
    return dicas[:2]


def _data_curta(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f'{d.day}/{d.month:02d} ({DIAS[d.weekday()]})'


def summarise(snapshot: dict, when: str = 'hoje', alertas: list[dict] | None = None) -> dict:
    if when not in {'hoje', 'amanhã'}:
        raise ValueError('turno inválido')
    setores = sectors()
    pts = snapshot['points']
    anchors = {}
    for p in sorted(pts, key=lambda x: x.get('tier', 1)):
        anchors.setdefault(p['sector'], p)
    if len(anchors) != 8:
        raise ValueError('É obrigatória previsão de todos os 8 setores')
    cards = [_card(anchors[key], s['short']) for key, s in setores.items()]
    todos = [_card(p, setores[p['sector']]['short']) for p in pts]
    use_pct = all(c['rain_pct'] is not None for c in cards)
    if not use_pct and any(c['rain_mm'] is None for c in cards):
        raise ValueError('Sem probabilidade nem volume de chuva em todos os setores')

    # Extremos usam TODOS os pontos coletados (inclui Parelheiros, Marsilac...).
    hottest = max(todos, key=lambda p: p['max_c'])
    coldest = min(todos, key=lambda p: p['min_c'])
    wettest = max(todos, key=lambda p: (p['rain_pct'] or 0) if use_pct else (p['rain_mm'] or 0))
    chuva = None if use_pct else maior_chuva(todos, when)
    resumo_ceu = {k: CEU.predominante([c['periods'] for c in cards], k) for k, _, _, _ in CEU.PERIODOS}
    resumo_ceu = {k: v for k, v in resumo_ceu.items() if v}
    ceu = ceu_visual(cards, resumo_ceu, chuva, hottest)
    dicas = dicas_praticas(cards, chuva, ceu, hottest)
    if alertas is None:
        alertas = ALERTAS.ativos(snapshot['forecast_date'])

    subject = 'hoje' if when == 'hoje' else 'amanhã'
    frase_ceu = CEU.frase_falada(resumo_ceu)
    script = ' '.join(x for x in [
        f'O tempo em São Paulo {subject}, região por região!',
        frase_ceu,
        f'A maior máxima prevista é em {hottest["point"]}, com {graus_inteiros(hottest["max_c"])} graus.',
        f'A menor mínima aparece em {coldest["point"]}, com {graus_inteiros(coldest["min_c"])} graus.',
        chuva['fala'] if chuva else None,
        ' '.join(d['fala'] for d in dicas) or None,
        'A previsão é estimativa por ponto, não previsão por rua.',
    ] if x)

    # ------------------------------------------------------------- legenda
    hora = snapshot.get('start_hour')
    linhas = [f'🌤️ O TEMPO SP — São Paulo {subject}, {_data_curta(snapshot["forecast_date"])}']
    if when == 'hoje' and hora:
        linhas.append(f'Previsão das {hora:02d}h às 24h.')
    for a in alertas:
        linhas.append(f'\n⚠️ ALERTA OFICIAL — {a["orgao"]}: {a["titulo"]}'
                      + (f' ({a["detalhe"]})' if a.get('detalhe') else '') + f'\n{a["url"]}')
    lc = CEU.linha_legenda(resumo_ceu)
    if lc:
        linhas.append('\n' + lc)
    if not use_pct:
        if chuva:
            jt = texto_janela(chuva.get('janela'), falado=False)
            vol = f'até {chuva["mm_fala"]} mm' if chuva['mm_fala'] else 'chuva fraca'
            linhas.append(f'🌧️ Maior chuva: {chuva["point"]}, {vol}' + (f', {jt}' if jt else '')
                          + f' · chuva em {chuva["locais_com_chuva"]} de {chuva["locais_total"]} pontos')
        else:
            linhas.append('🌧️ Sem chuva significativa prevista nos pontos acompanhados.')
    linhas.append(f'🌡️ Maior máxima: {hottest["point"]}, {graus_inteiros(hottest["max_c"])}° · '
                  f'menor mínima: {coldest["point"]}, {graus_inteiros(coldest["min_c"])}°')
    linhas.append('\n📍 Por região (mín. / máx. · chuva):')
    for c in cards:
        if use_pct:
            chuva_txt = f'{c["rain_pct"]:g}%'
        else:
            chuva_txt = f'{_mm(c["rain_mm"])} mm'
            if classificar(c['rain_mm']) != 'seco' and c.get('rain_window'):
                chuva_txt += f' ({texto_janela(c["rain_window"], falado=False)})'
        linhas.append(f'{c["short"]} · {c["point"]}: {graus_inteiros(c["min_c"])}° / '
                      f'{graus_inteiros(c["max_c"])}° · {chuva_txt}')
    if dicas:
        linhas.append('\n💡 ' + ' '.join(d['fala'] for d in dicas))
    nota = ('Probabilidade diária de chuva não é chance por hora. ' if use_pct
            else 'Chuva = volume previsto em milímetros; abaixo de 0,5 mm conta como sem chuva significativa. ')
    linhas.append('\nPrevisão por pontos representativos, sujeita a mudanças. ' + nota
                  + f'Dados: {snapshot["source"]}.')
    linhas.append('Siga @otemposp · boletins às 6h e às 18h.')
    linhas.append('#OTempoSP #PrevisaoSP #SaoPaulo #PrevisaoDoTempo')
    caption = '\n'.join(linhas)

    return {'when': when, 'date': snapshot['forecast_date'], 'script': script,
            'hora_inicio': hora, 'cards': cards, 'todos': todos, 'caption': caption,
            'hottest': hottest, 'coldest': coldest, 'wettest': wettest, 'chuva': chuva,
            'ceu': ceu, 'ceu_periodos': resumo_ceu, 'frase_ceu': frase_ceu,
            'dicas': dicas, 'alertas': alertas,
            'rain_metric': 'pct' if use_pct else 'mm',
            'is_fixture': snapshot.get('is_fixture', False)}

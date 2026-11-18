"""Detector editorial de mudanças bruscas do tempo (sem publicação automática).

Entrada: cidades=[{"nome": "...", "hourly": [{"time": "2026-11-18T15:00:00-03:00",
"precipitation_mm": 0, "temperature_c": 25, "wind_gust_kmh": 0,
"weather_code": 0}, ...]}].
Os dados são PREVISÕES; não representam chuva efetivamente observada.
Granizo só aparece como possibilidade se o código WMO indicar 96/99 ou se
houver aviso oficial verificado e datado no argumento avisos_oficiais.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
LIMITES = {"chuva_1h_mm": 20, "chuva_3h_mm": 30,
           "rajada_kmh": 50, "delta_6h_c": 6, "calor_fds_c": 35}
PRIORIDADE = {"granizo": 5, "chuva_intensa": 4, "vento": 3,
              "virada_temperatura": 2, "calor_fim_semana": 1}


def _data(value):
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=TZ)
    return d.astimezone(TZ)


def _valor(row, key):
    try:
        v = row.get(key)
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def detectar_eventos(cidades, agora=None, avisos_oficiais=()):
    """Retorna apenas eventos com evidência; nunca os publica ou registra como publicados."""
    agora = _data(agora or datetime.now(TZ))
    eventos = []
    for cidade in cidades:
        nome = cidade.get("nome")
        if not nome:
            continue
        linhas = []
        for row in cidade.get("hourly", []):
            try:
                hora = _data(row["time"])
            except (KeyError, ValueError, TypeError):
                continue
            if agora - timedelta(hours=1) <= hora <= agora + timedelta(days=7):
                linhas.append((hora, row))
        linhas.sort(key=lambda x: x[0])
        # Não duplicar uma hora com previsões contraditórias.
        linhas = list({h: (h, row) for h, row in linhas}.values())
        linhas.sort(key=lambda x: x[0])
        for i, (hora, row) in enumerate(linhas):
            if hora < agora.replace(minute=0, second=0, microsecond=0):
                continue
            mm = _valor(row, "precipitation_mm")
            if mm is not None and mm >= LIMITES["chuva_1h_mm"]:
                eventos.append(_evento("chuva_intensa", nome, hora, hora + timedelta(hours=1),
                                       f"{mm:g} mm previstos em 1h", "previsao", mm))
            # Somar apenas três horas consecutivas, completas e com precipitação conhecida.
            janela = linhas[i:i + 3]
            if len(janela) == 3 and all(janela[k][0] == hora + timedelta(hours=k) for k in range(3)):
                valores = [_valor(r, "precipitation_mm") for _, r in janela]
                if all(v is not None for v in valores) and sum(valores) >= LIMITES["chuva_3h_mm"]:
                    total = round(sum(valores), 1)
                    eventos.append(_evento("chuva_intensa", nome, hora, hora + timedelta(hours=3),
                                           f"{total:g} mm previstos em 3h", "previsao", total))
            rajada = _valor(row, "wind_gust_kmh")
            if rajada is not None and rajada >= LIMITES["rajada_kmh"]:
                eventos.append(_evento("vento", nome, hora, hora + timedelta(hours=1),
                                       f"rajadas previstas de {rajada:g} km/h", "previsao", rajada))
            try:
                codigo = int(row.get("weather_code"))
            except (ValueError, TypeError):
                codigo = None
            if codigo in (96, 99):
                eventos.append(_evento("granizo", nome, hora, hora + timedelta(hours=1),
                                       "modelo indica possibilidade de tempestade com granizo",
                                       "previsao_nao_oficial", codigo))
            # Seis horas adiante, somente pontos horários efetivamente alinhados.
            futuro = next((r for h, r in linhas if h == hora + timedelta(hours=6)), None)
            antes, depois = _valor(row, "temperature_c"), _valor(futuro or {}, "temperature_c")
            if antes is not None and depois is not None and abs(depois - antes) >= LIMITES["delta_6h_c"]:
                delta = round(depois - antes, 1)
                eventos.append(_evento("virada_temperatura", nome, hora, hora + timedelta(hours=6),
                                       f"variação prevista de {delta:+g}°C em 6h", "previsao", abs(delta)))
        # Boletim de fim de semana: só quinta/sexta e só sábado/domingo futuros.
        if agora.weekday() in (3, 4):
            for dia in (5, 6):
                pontos = [(h, _valor(r, "temperature_c")) for h, r in linhas
                          if h.weekday() == dia and h.date() > agora.date()]
                validos = [(h, t) for h, t in pontos if t is not None]
                if validos:
                    h, pico = max(validos, key=lambda v: v[1])
                    if pico >= LIMITES["calor_fds_c"]:
                        eventos.append(_evento("calor_fim_semana", nome, h, h + timedelta(hours=1),
                                               f"máxima horária prevista de {pico:g}°C no fim de semana",
                                               "previsao", pico))
    # Só aceitar avisos oficiais externos expressamente verificados e com validade.
    for aviso in avisos_oficiais:
        if not aviso.get("verificado") or not aviso.get("fonte") or not aviso.get("local"):
            continue
        try:
            inicio, fim = _data(aviso["inicio"]), _data(aviso["fim"])
        except (KeyError, ValueError, TypeError):
            continue
        if fim <= agora or inicio > agora + timedelta(days=7):
            continue
        tipo = aviso.get("tipo")
        if tipo not in ("granizo", "chuva_intensa", "vento", "calor_fim_semana"):
            continue
        eventos.append(_evento(tipo, aviso["local"], inicio, fim,
                               str(aviso.get("descricao") or "Aviso meteorológico oficial"),
                               "aviso_oficial:" + str(aviso["fonte"]), None))
    # Reduz manchetes repetidas; mantém intensidade mais alta por tipo/local/data.
    unicos = {}
    for e in eventos:
        chave = (e["tipo"], e["local"], e["inicio"][:10])
        anterior = unicos.get(chave)
        if anterior is None or (e["intensidade"] or 0) > (anterior["intensidade"] or 0):
            unicos[chave] = e
    return sorted(unicos.values(), key=lambda e: (-PRIORIDADE[e["tipo"]], e["inicio"], e["local"]))


def _evento(tipo, local, inicio, fim, descricao, origem, intensidade):
    return {"tipo": tipo, "local": local, "inicio": inicio.isoformat(),
            "fim": fim.isoformat(), "descricao": descricao, "origem": origem,
            "intensidade": intensidade, "status": "candidato_nao_publicado"}

"""Atualiza o catálogo de eventos ANTES de gerar o especial de fim de semana.

Run 46087751428 falhou porque o catálogo era da edição anterior. Este passo:

1. Se o catálogo já é da edição corrente (sexta da semana, America/Sao_Paulo),
   não faz nada.
2. Senão, busca eventos do sábado/domingo em domínios oficiais e de imprensa
   (Tavily, plano grátis) e extrai os campos com um modelo grátis do
   OpenRouter, em JSON.
3. Cada evento extraído só entra se o TEXTO DA PÁGINA de origem contém o nome,
   o dia e o horário informados — o modelo não pode inventar nada que não
   esteja escrito na fonte. Coordenadas via Nominatim, dentro da capital.
4. Com menos de 2 eventos verificados, grava output/.../motivo.json, mantém o
   catálogo antigo e sai com código 3: a pauta não é gerada nem publicada.

Sem TAVILY_API_KEY/OPENROUTER_API_KEY, registra o motivo e sai com código 3.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "eventos_fim_de_semana.json"
OUT = ROOT / "output" / "eventos_fim_de_semana"
SEM_EVENTOS = 3
DOMINIOS = ["prefeitura.sp.gov.br", "capital.sp.gov.br", "visitesaopaulo.com",
            "sescsp.org.br", "cultura.sp.gov.br", "metropoles.com", "g1.globo.com",
            "agendasp.sp.gov.br"]
# Caixa da capital paulista (folga pequena); ponto fora = geocodificação errada.
LAT, LON = (-24.01, -23.35), (-46.83, -46.36)
MODELO = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
UA = "o-tempo-sp/1.0 (github.com/pabloramoa-dev/o-tempo-sp)"


def edicao(agora: datetime) -> date:
    d = agora.astimezone(TZ).date()
    return d if d.weekday() == 4 else d + timedelta(days=(4 - d.weekday()) % 7)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t)


MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]


def _dia_no_texto(texto: str, d: date) -> bool:
    t = _norm(texto)
    formas = [f"{d.day:02d}/{d.month:02d}", f"{d.day}/{d.month}", f"{d.day} de {MESES[d.month - 1]}",
              f"{d.day:02d} de {MESES[d.month - 1]}", f"({d.day})", f"({d.day:02d})"]
    if any(f in t for f in formas):
        return True
    # "28 e 29 de novembro", "dias 28, 29 e 30 de novembro"
    return re.search(rf"(?<![0-9]){d.day}(?![0-9])[^.\n]{{0,30}}de {MESES[d.month - 1]}", t) is not None


def _hora_no_texto(texto: str, hora: int, minuto: int) -> bool:
    t = _norm(texto)
    m = f"{minuto:02d}"
    formas = [f"{hora}h{m if minuto else ''}", f"{hora:02d}h{m if minuto else ''}",
              f"{hora}:{m}", f"{hora:02d}:{m}"]
    return any(re.search(re.escape(f) + r"(?![0-9])", t) for f in formas)


def verificar(evento: dict, texto: str, fim_de_semana: tuple[date, date]) -> list[str]:
    """Problemas do evento frente ao texto da fonte (vazio = verificado)."""
    problemas = []
    nome = _norm(evento.get("name", ""))
    palavras = [p for p in re.findall(r"[a-z0-9]{4,}", nome)]
    if not palavras or sum(p in _norm(texto) for p in palavras) < max(1, len(palavras) * 2 // 3):
        problemas.append("nome não aparece na fonte")
    if not evento.get("venue") or not any(p in _norm(texto) for p in re.findall(r"[a-z]{5,}", _norm(evento["venue"]))):
        problemas.append("local não aparece na fonte")
    sessoes = []
    for s in evento.get("sessions") or []:
        try:
            dt = datetime.fromisoformat(s["starts_at"]).astimezone(TZ)
        except (KeyError, ValueError, TypeError):
            problemas.append("sessão com data inválida")
            continue
        if dt.date() not in fim_de_semana:
            continue
        if not _dia_no_texto(texto, dt.date()):
            problemas.append(f"dia {dt:%d/%m} não aparece na fonte")
            continue
        if not _hora_no_texto(texto, dt.hour, dt.minute):
            problemas.append(f"horário {dt:%H:%M} não aparece na fonte")
            continue
        sessoes.append(s)
    if not sessoes:
        problemas.append("nenhuma sessão do fim de semana confirmada pela fonte")
    evento["sessions"] = sessoes
    return problemas


def _post(url: str, corpo: dict, headers: dict, timeout=40) -> dict:
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def buscar_paginas(sabado: date) -> list[dict]:
    consulta = (f"eventos gratuitos São Paulo capital sábado {sabado.day} e domingo "
                f"{sabado.day + 1} de {MESES[sabado.month - 1]} {sabado.year} horário local")
    r = _post("https://api.tavily.com/search", {
        "api_key": os.environ["TAVILY_API_KEY"], "query": consulta, "max_results": 8,
        "include_domains": DOMINIOS, "include_raw_content": True, "search_depth": "basic"}, {})
    return [{"url": x["url"], "texto": x.get("raw_content") or x.get("content") or ""}
            for x in r.get("results", []) if x.get("url")]


def extrair(pagina: dict, sabado: date) -> list[dict]:
    prompt = (
        "Extraia do texto abaixo no máximo 3 eventos presenciais na cidade de São Paulo "
        f"que acontecem em {sabado:%d/%m/%Y} ou {sabado + timedelta(days=1):%d/%m/%Y}. "
        "Use SOMENTE o que estiver escrito; não complete nada. Responda apenas JSON: "
        '{"eventos":[{"name":"","venue":"","priority":"","sessions":[{"starts_at":"AAAA-MM-DDTHH:MM:00-03:00","headline":""}]}]}'
        "\n\nTEXTO:\n" + pagina["texto"][:12000])
    r = _post("https://openrouter.ai/api/v1/chat/completions", {
        "model": MODELO, "temperature": 0, "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}]},
        {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
    conteudo = r["choices"][0]["message"]["content"]
    conteudo = conteudo[conteudo.find("{"): conteudo.rfind("}") + 1]
    eventos = json.loads(conteudo).get("eventos") or []
    for e in eventos:
        e["source"] = pagina["url"]
        e["fonte_oficial"] = any(d in pagina["url"] for d in ("sp.gov.br", "visitesaopaulo.com"))
    return eventos


def geocodificar(local: str) -> tuple[float, float] | None:
    q = urllib.parse.urlencode({"q": f"{local}, São Paulo, SP, Brasil", "format": "json", "limit": 1})
    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        dados = json.load(r)
    if not dados:
        return None
    la, lo = float(dados[0]["lat"]), float(dados[0]["lon"])
    if not (LAT[0] <= la <= LAT[1] and LON[0] <= lo <= LON[1]):
        return None
    return la, lo


def registrar_motivo(ed: date, motivo: str, rejeitados=None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "motivo.json").write_text(json.dumps(
        {"edicao": ed.isoformat(), "publicar": False, "motivo": motivo,
         "rejeitados": rejeitados or []}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"::warning::Sem pauta de eventos para {ed}: {motivo}")
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        Path(resumo).write_text(f"### Sem especial de eventos ({ed})\n\n{motivo}\n", encoding="utf-8")
    return SEM_EVENTOS


def main(agora: datetime | None = None) -> int:
    agora = agora or datetime.now(TZ)
    ed = edicao(agora)
    atual = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else {}
    if atual.get("edition") == ed.isoformat() and len(atual.get("events") or []) == 2:
        print(f"catálogo já é da edição {ed}: nada a atualizar")
        return 0
    if not (os.environ.get("TAVILY_API_KEY") and os.environ.get("OPENROUTER_API_KEY")):
        return registrar_motivo(ed, "catálogo desatualizado e sem TAVILY_API_KEY/OPENROUTER_API_KEY "
                                    "para a atualização automática; nada antigo será publicado")
    sabado = ed + timedelta(days=1)
    fds = (sabado, sabado + timedelta(days=1))
    aceitos, rejeitados = [], []
    try:
        paginas = buscar_paginas(sabado)
    except Exception as exc:  # noqa: BLE001 - qualquer falha = sem pauta
        return registrar_motivo(ed, f"busca de eventos falhou: {exc}")
    print(f"busca: {len(paginas)} página(s) de fontes permitidas")
    for pagina in paginas:
        try:
            candidatos = extrair(pagina, sabado)
            print(f"  {pagina['url'][:90]} -> {len(candidatos)} candidato(s)")
        except Exception as exc:  # noqa: BLE001
            rejeitados.append({"fonte": pagina["url"], "motivo": f"extração falhou: {exc}"})
            continue
        for e in candidatos:
            problemas = verificar(e, pagina["texto"], fds)
            if not problemas:
                try:
                    coord = geocodificar(e["venue"])
                except Exception:  # noqa: BLE001
                    coord = None
                if coord is None:
                    problemas.append("local não localizado na capital")
                else:
                    e["latitude"], e["longitude"] = coord
            if problemas:
                rejeitados.append({"evento": e.get("name"), "fonte": e.get("source"), "motivo": problemas})
            elif _norm(e["name"]) not in {_norm(a["name"]) for a in aceitos}:
                aceitos.append(e)
    for r in rejeitados:
        print(f"  rejeitado: {str(r.get('evento') or r.get('fonte'))[:60]} — {r.get('motivo')}")
    # Fonte oficial primeiro; depois mais sessões.
    aceitos.sort(key=lambda e: (not e.get("fonte_oficial"), -len(e["sessions"])))
    if len(aceitos) < 2:
        return registrar_motivo(ed, f"só {len(aceitos)} evento(s) confirmado(s) pela fonte; são necessários 2",
                                rejeitados)
    novo = {"edition": ed.isoformat(), "verified_at": agora.date().isoformat(),
            "verificacao": "automática: Tavily + OpenRouter, campos conferidos no texto da fonte",
            "events": aceitos[:2]}
    CATALOG.write_text(json.dumps(novo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"catálogo atualizado para {ed}: " + "; ".join(e["name"] for e in aceitos[:2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

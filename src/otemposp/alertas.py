"""Alertas OFICIAIS (Defesa Civil, CGE, INMET) — nunca gerados a partir do modelo.

Formato de config/alerts_oficiais.json:
{"alerts": [{"orgao": "Defesa Civil de SP", "titulo": "Temporal com raios",
             "detalhe": "Zona Sul e Leste, a partir das 15h",
             "url": "https://...", "issued_at": "2026-11-09T10:00:00-03:00",
             "expires_at": "2026-11-09T23:59:00-03:00"}]}

Só entra no boletim o alerta com órgão, título, URL HTTPS e validade conferidos,
e que ainda esteja valendo no dia da previsão.
"""
from __future__ import annotations
from datetime import datetime, date, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import json

ROOT = Path(__file__).resolve().parents[2]
ARQUIVO = ROOT / "config" / "alerts_oficiais.json"
TZ = ZoneInfo("America/Sao_Paulo")
OBRIGATORIOS = ("orgao", "titulo", "url", "issued_at", "expires_at")


def _quando(texto: str) -> datetime:
    d = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=TZ)


def ativos(dia: date | str, agora: datetime | None = None, caminho: Path | None = None) -> list[dict]:
    """Alertas válidos que cobrem o dia da previsão; inválidos são ignorados."""
    caminho = caminho or ARQUIVO
    if not caminho.exists():
        return []
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    dia = date.fromisoformat(dia) if isinstance(dia, str) else dia
    agora = (agora or datetime.now(timezone.utc)).astimezone(TZ)
    inicio_dia = datetime(dia.year, dia.month, dia.day, tzinfo=TZ)
    validos = []
    for a in dados.get("alerts", []):
        if not all(str(a.get(k) or "").strip() for k in OBRIGATORIOS):
            continue
        if not str(a["url"]).startswith("https://"):
            continue
        try:
            emitido, expira = _quando(a["issued_at"]), _quando(a["expires_at"])
        except ValueError:
            continue
        if expira <= agora or expira <= inicio_dia or emitido > agora:
            continue
        validos.append({k: a.get(k) for k in OBRIGATORIOS + ("detalhe",)})
    return validos

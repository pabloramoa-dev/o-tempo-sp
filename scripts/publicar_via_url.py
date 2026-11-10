"""Publicacao dos dois turnos de SP via video_url publica e recibo idempotente."""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from scripts.distribute import Receipt, result
from scripts.met_forecast import ENDPOINT
from src.otemposp.geo import sectors


def conferir_previsao(snap, brief):
    agora = datetime.now(timezone.utc)
    dia = (agora.astimezone(ZoneInfo("America/Sao_Paulo")).date()
           + timedelta(days=int(brief.get("when") == "amanhã")))
    obtido = datetime.fromisoformat(snap["fetched_at"])
    idade = agora - obtido
    if (brief.get("when") not in ("hoje", "amanhã") or
        brief["date"] != dia.isoformat() or
        snap.get("forecast_date") != brief["date"] or
        snap.get("source_url") != ENDPOINT or
        snap.get("is_fixture") or brief.get("is_fixture") or
        not timedelta(0) <= idade <= timedelta(hours=2) or
        len(snap["points"]) != len(sectors()) or
        {p["sector"] for p in snap["points"]} != set(sectors()) or
        len(brief["cards"]) != len(sectors())):
        raise ValueError("Boletim vencido, ficticio ou incompleto; envio bloqueado")


def publicar():
    brief = json.loads(Path("output/brief.json").read_text(encoding="utf-8"))
    snap = json.loads(Path("output/snapshot.json").read_text(encoding="utf-8"))
    conferir_previsao(snap, brief)
    quando = brief["when"]
    video = Path("output/bira.mp4" if quando == "hoje" else "output/bia.mp4")
    if not video.is_file() or video.stat().st_size < 1000000:
        raise ValueError("MP4 ausente ou incompleto")
    if len(sys.argv) > 1 and sys.argv[1] == "--validar":
        print("Boletim validado localmente:", quando, brief["date"], video)
        return
    url = os.environ["REEL_PUBLIC_URL"].strip()
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or
        not parsed.path.startswith("/pabloramoa-dev/o-tempo-sp/releases/download/") or
        not parsed.path.endswith(".mp4") or parsed.query or parsed.fragment):
        raise ValueError("Somente video publico do Release do repositorio e aceito")
    usuario = os.environ["IG_USER_ID"].strip()
    token = os.environ["IG_ACCESS_TOKEN"].strip()
    if not usuario.isdecimal() or not token:
        raise ValueError("Credenciais ausentes")
    host = "graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com"
    base = f"https://{host}/{os.environ.get('META_GRAPH_VERSION','v26.0')}"
    auth = {"Authorization": "Bearer " + token}

    def get(path, fields):
        return result(requests.get(f"{base}/{path}", headers=auth,
            params={"fields": fields}, timeout=30))

    def post(path, params):
        return result(requests.post(f"{base}/{path}", headers=auth,
            data=params, timeout=60))

    conta = get(usuario, "id,username")
    if conta.get("username", "").lower() != "otemposp":
        raise ValueError("Conta de destino inesperada")

    dia = (datetime.now(ZoneInfo("America/Sao_Paulo")).date()
           + timedelta(days=int(quando == "amanhã")))
    for tipo in (("REELS", "STORIES") if quando == "hoje" else ("REELS",)):
        recibo = Receipt(f"{dia}-{quando}-{tipo}")
        if recibo.data.get("media_id"):
            media_id = str(recibo.data["media_id"])
            detalhes = get(media_id, "id,media_type,permalink" if tipo == "REELS"
                           else "id,media_type")
            if detalhes.get("id") != media_id or (tipo == "REELS" and
                    not detalhes.get("permalink")):
                raise RuntimeError(f"{tipo}: ID anterior nao confirmado")
            print(tipo, "ja publicado e confirmado", media_id,
                  detalhes.get("permalink", ""))
            continue

        pedido = {"media_type": tipo, "video_url": url}
        if tipo == "REELS":
            pedido.update(caption=brief["caption"], share_to_feed="true")
        container = post(usuario + "/media", pedido)["id"]
        recibo.data = {"container": container, "metodo": "video_url"}
        recibo.save()
        for tentativa in range(90):
            estado = get(container, "status_code")["status_code"]
            if estado == "FINISHED":
                break
            if estado in ("ERROR", "EXPIRED", "PUBLISHED"):
                raise RuntimeError(f"{tipo}: estado do container {estado}")
            time.sleep(5)
        else:
            raise RuntimeError(f"{tipo}: processamento excedeu o tempo")

        media_id = str(post(usuario + "/media_publish",
                            {"creation_id": container})["id"])
        recibo.data.update(media_id=media_id)
        recibo.save()
        detalhes = None
        for tentativa in range(8):
            try:
                detalhes = get(media_id, "id,media_type,permalink" if tipo == "REELS"
                              else "id,media_type")
                if detalhes.get("id") == media_id and (tipo != "REELS" or
                        detalhes.get("permalink")):
                    break
            except (requests.RequestException, RuntimeError):
                pass
            time.sleep(3)
        else:
            raise RuntimeError(f"{tipo}: publicado mas ainda sem confirmacao da Meta")
        recibo.data.update(published=True,
                           permalink=detalhes.get("permalink", ""))
        recibo.save()
        print(tipo, "publicado e confirmado na Meta", media_id,
              detalhes.get("permalink", ""))


if __name__ == "__main__":
    publicar()

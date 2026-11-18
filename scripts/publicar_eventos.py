"""Publicacao exclusiva do Reel de eventos. Validacao temporal e anti-duplicacao."""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import requests

TZ = ZoneInfo("America/Sao_Paulo")
BASE = Path("output/eventos_fim_de_semana")

def publish():
    now = datetime.now(TZ)
    meta = json.loads((BASE / "publicacao.json").read_text(encoding="utf-8"))
    edition = meta["edicao"]
    if now.weekday() != 4 or now.date().isoformat() != edition or not (14 <= now.hour < 16):
        raise RuntimeError("Fora da janela da sexta-feira (14h-16h BRT): publicacao bloqueada")
    video = BASE / "especial-eventos-sp.mp4"
    if not video.exists() or video.stat().st_size < 1000000:
        raise RuntimeError("MP4 ausente ou muito pequeno")
    pauta = json.loads((BASE / "pauta.json").read_text(encoding="utf-8"))
    if pauta["edicao"] != edition or len(pauta["eventos"]) != 2:
        raise RuntimeError("Pauta incompleta ou vencida")
    caption = (BASE / "legenda.txt").read_text(encoding="utf-8") + "\nEVENTOS SP | " + edition
    url = os.environ["REEL_PUBLIC_URL"].strip()
    parsed = urlparse(url)
    if not (parsed.scheme == "https" and parsed.netloc == "github.com"
            and parsed.path.startswith("/pabloramoa-dev/o-tempo-sp/releases/download/")
            and parsed.path.endswith(".mp4") and not parsed.query and not parsed.fragment):
        raise RuntimeError("URL publica do GitHub Release invalida")
    user = os.environ["IG_USER_ID"].strip()
    token = os.environ["IG_ACCESS_TOKEN"].strip()
    if not user.isdecimal() or not token:
        raise RuntimeError("Credenciais invalidas")
    host = "graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com"
    base = "https://" + host + "/" + os.getenv("META_GRAPH_VERSION", "v26.0")
    auth = {"Authorization": "Bearer " + token}
    def request(method, path, **kwargs):
        r = requests.request(method, base + "/" + path, headers=auth, timeout=60, **kwargs)
        r.raise_for_status()
        payload = r.json()
        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        return payload
    account = request("GET", user, params={"fields": "id,username"})
    if account.get("username", "").lower() != "otemposp":
        raise RuntimeError("Conta Instagram inesperada")
    posts = request("GET", user + "/media", params={"fields":"id,caption,timestamp","limit":30})
    if any("EVENTOS SP | " + edition in item.get("caption", "") for item in posts.get("data", [])):
        print("Ja existe Reel confirmado para esta edicao; nao duplicar.")
        return
    container = request("POST", user + "/media", data={
        "media_type":"REELS", "video_url":url, "caption":caption, "share_to_feed":"true"
    })["id"]
    for _ in range(90):
        state = request("GET", container, params={"fields": "status_code"})["status_code"]
        if state == "FINISHED":
            break
        if state in ("ERROR","EXPIRED","PUBLISHED"):
            raise RuntimeError("Meta rejeitou container: " + state)
        time.sleep(5)
    else:
        raise RuntimeError("Timeout na Meta")
    media_id = request("POST", user + "/media_publish", data={"creation_id":container})["id"]
    details = request("GET", media_id, params={"fields":"id,media_type,permalink"})
    print("Reel publicado: ", details)
    meta.update(publicado=True, media_id=media_id, url=details.get("permalink"))
    (BASE / "publicacao.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__ == "__main__":
    publish()

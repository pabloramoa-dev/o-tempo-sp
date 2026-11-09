"""Publicação idempotente de cada edição, com registro do container antes de publicar."""
import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests

from scripts.met_forecast import ENDPOINT

def result(response):
    if not response.ok:
        try:
            error=response.json().get("error",{})
            detail=f"{error.get('code','')}/{error.get('error_subcode','')} {error.get('message','')}"
            detail=detail.replace(os.environ["IG_ACCESS_TOKEN"],"[oculto]")
        except ValueError:
            detail=""
        raise RuntimeError(f"HTTP {response.status_code} {detail[:300]}")
    return response.json()

class Receipt:
    def __init__(self, slot):
        repo=os.environ["GITHUB_REPOSITORY"]
        self.url=f"https://api.github.com/repos/{repo}/contents/data/instagram/{slot}.json"
        self.headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"]}
        response=requests.get(self.url,headers=self.headers,params={"ref":"main"},timeout=25)
        self.sha=None
        self.data={}
        if response.status_code != 404:
            file=result(response)
            self.sha=file["sha"]
            self.data=json.loads(base64.b64decode(file["content"]))

    def save(self):
        body={"message":"Registrar publicação @otemposp","branch":"main","content":
              base64.b64encode(json.dumps(self.data).encode()).decode()}
        if self.sha:
            body["sha"]=self.sha
        record=result(requests.put(self.url,headers=self.headers,json=body,timeout=30))
        self.sha=record["content"]["sha"]

def deliver(snap,brief,mp4,kind,live):
    user=os.environ["IG_USER_ID"].strip()
    token=os.environ["IG_ACCESS_TOKEN"].strip()
    if not user.isdecimal() or not token:
        raise ValueError("Credenciais ausentes")
    host="graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com"
    version=os.environ.get("META_GRAPH_VERSION","v26.0")
    base=f"https://{host}/{version}"
    auth={"Authorization":"Bearer "+token}
    def get(path,fields):
        return result(requests.get(base+"/"+path,headers=auth,params={"fields":fields},timeout=30))
    def post(path,body):
        return result(requests.post(base+"/"+path,headers=auth,data=body,timeout=60))
    if get(user,"id,username").get("username","").lower()!="otemposp":
        raise ValueError("Conta de destino inesperada")
    now=datetime.now(timezone.utc)
    tomorrow=brief["when"]=="amanhã"
    day=now.astimezone(ZoneInfo("America/Sao_Paulo")).date()+timedelta(days=int(tomorrow))
    age=now-datetime.fromisoformat(snap["fetched_at"])
    if (snap["is_fixture"] or brief["is_fixture"] or snap["source_url"]!=ENDPOINT
        or not timedelta(0)<=age<=timedelta(hours=2) or
        brief["date"]!=day.isoformat() or snap["forecast_date"]!=brief["date"]
        or len({p["sector"] for p in snap["points"]})!=8):
        raise ValueError("Recusado boletim fictício, vencido ou incompleto")
    if live and kind=="STORIES" and tomorrow:
        raise ValueError("Story reservado ao boletim do Bira")
    # Republicação expressamente solicitada: recibo próprio, sem alterar a edição diária.
    revisao = os.getenv("REEL_REPUBLICACAO", "").strip()
    if revisao and (kind != "REELS" or revisao != "revisao-capa-temp-20261108"):
        raise ValueError("Identificador de republicação não autorizado")
    slot = f"{day}-{brief['when']}-{kind}" + (f"-{revisao}" if revisao else "")
    receipt=Receipt(slot) if live else None
    if receipt and receipt.data.get("published"):
        print(kind,"já publicado",receipt.data.get("media_id",""));return
    cid=receipt.data.get("container") if receipt else None
    if not cid:
        args={"media_type":kind,"upload_type":"resumable"}
        if kind=="REELS":
            caption = brief["caption"]
            if revisao:
                caption = "🌤️ Previsão atualizada do O TEMPO SP — nova capa e narração somente das temperaturas.\n\n" + caption
            args.update(caption=caption,share_to_feed="true",thumb_offset="500")
        container=post(user+"/media",args)
        cid=container["id"]
        uri=container["uri"]
        if urlparse(uri).hostname!="rupload.facebook.com" or urlparse(uri).scheme!="https":
            raise ValueError("Destino de upload inválido")
        with mp4.open("rb") as video:
            result(requests.post(uri,data=video,headers={"Authorization":"OAuth "+token,
                "offset":"0","file_size":str(mp4.stat().st_size),"Content-Type":"application/octet-stream"},
                timeout=180,allow_redirects=False))
        if receipt:
            receipt.data={"container":cid}
            receipt.save()
    for _ in range(90):
        status=get(cid,"status_code")["status_code"]
        if status=="PUBLISHED":
            if receipt:
                receipt.data["published"]=True
                receipt.save()
            print(kind,"já confirmado pela Meta");return
        if status=="FINISHED":break
        if status in ("ERROR","EXPIRED"):
            if receipt:
                receipt.data={}
                receipt.save()
            raise RuntimeError(f"{kind}: container {status}")
        time.sleep(5)
    else: raise RuntimeError("Tempo de processamento excedido")
    if not live:
        print(kind,"upload validado, sem publicação");return
    media=post(user+"/media_publish",{"creation_id":cid})["id"]
    receipt.data.update(published=True,media_id=media)
    receipt.save()
    print(kind,"publicado",media)

def main():
    brief=json.loads(Path("output/brief.json").read_text())
    snap=json.loads(Path("output/snapshot.json").read_text())
    morning=brief["when"]=="hoje"
    video=Path("output/bira.mp4" if morning else "output/bia.mp4")
    for kind in (("REELS","STORIES") if morning or sys.argv[1]!="live" else ("REELS",)):
        deliver(snap,brief,video,kind,sys.argv[1]=="live")

if __name__=="__main__":main()

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
            if not detail.strip(" /"):
                # rupload pode usar debug_info em vez do campo error.
                detail=str(response.json().get("debug_info") or response.json().get("message") or response.json())[:500]
            detail=detail.replace(os.environ.get("IG_ACCESS_TOKEN",""),"[oculto]")
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
    if revisao and (kind != "REELS" or revisao not in ("revisao-capa-temp-20261108", "previa-real-09nov2026", "chuva-final-bira-20261109")):
        raise ValueError("Identificador de republicação não autorizado")
    slot = f"{day}-{brief['when']}-{kind}" + (f"-{revisao}" if revisao else "")
    receipt=Receipt(slot) if live else None
    # Confirma que um ID publicado ainda existe na conta, em vez de confiar
    # apenas no resultado verde do GitHub ou num recibo antigo.
    def verify_publication(media_id):
        fields = "id,media_type,permalink" if kind == "REELS" else "id,media_type"
        error = "A Meta não confirmou a mídia"
        for _ in range(8):
            try:
                details = get(str(media_id), fields)
                if str(details.get("id")) == str(media_id) and (
                    kind != "REELS" or details.get("permalink")
                ):
                    return details
                error = "ID ou permalink ausente na resposta da Meta"
            except (requests.RequestException, RuntimeError) as exc:
                error = str(exc)
            time.sleep(3)
        raise RuntimeError(f"{kind}: mídia {media_id} não verificável na Meta: {error}")

    if receipt and receipt.data.get("media_id"):
        media_id = receipt.data["media_id"]
        verified = verify_publication(media_id)
        receipt.data.update(published=True, permalink=verified.get("permalink", ""))
        receipt.save()
        print(kind, "já publicado e verificado na Meta", media_id, verified.get("permalink", ""))
        return
    cid=receipt.data.get("container") if receipt else None
    if not cid:
        args={"media_type":kind,"upload_type":"resumable"}
        if kind=="REELS":
            caption = brief["caption"]
            if revisao == "previa-real-09nov2026":
                caption = "🌤️ O TEMPO SP — previsão real de amanhã, 9 de novembro! Temperaturas por região e o maior destaque de chuva no final.\n\n" + caption
            elif revisao:
                caption = "🌤️ Previsão atualizada do O TEMPO SP — nova capa e narração somente das temperaturas.\n\n" + caption
            args.update(caption=caption,share_to_feed="true",thumb_offset="500")
        container=post(user+"/media",args)
        cid=container["id"]
        uri=container["uri"]
        if urlparse(uri).hostname!="rupload.facebook.com" or urlparse(uri).scheme!="https":
            raise ValueError("Destino de upload inválido")
        for attempt in range(2):
            with mp4.open("rb") as video:
                uploaded=requests.post(uri,data=video,headers={"Authorization":"OAuth "+token,
                    "offset":"0","file_size":str(mp4.stat().st_size),"Content-Type":"application/octet-stream"},
                    timeout=180,allow_redirects=False)
            if uploaded.ok:
                break
            if attempt == 0 and uploaded.status_code in (400,408,429,500,502,503,504):
                time.sleep(5)
                continue
            result(uploaded)
        if receipt:
            receipt.data={"container":cid}
            receipt.save()
    for _ in range(90):
        status=get(cid,"status_code")["status_code"]
        if status=="PUBLISHED":
            # O container foi publicado, mas não temos o media_id recuperável.
            # Não marcar sucesso de publicação sem confirmar a mídia final.
            raise RuntimeError(f"{kind}: container {cid} está PUBLISHED, mas falta o media_id; requer verificação")
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
    # Salvar primeiro o ID para que uma falha na validação não publique em duplicidade.
    receipt.data.update(media_id=media)
    receipt.save()
    verified = verify_publication(media)
    receipt.data.update(published=True, permalink=verified.get("permalink", ""))
    receipt.save()
    print(kind, "publicado e confirmado na Meta", media, verified.get("permalink", ""))

def main():
    brief=json.loads(Path("output/brief.json").read_text())
    snap=json.loads(Path("output/snapshot.json").read_text())
    morning=brief["when"]=="hoje"
    video=Path("output/bira.mp4" if morning else "output/bia.mp4")
    # Republicação aprovada: apenas novo Reel, sem repetir o Story já publicado.
    revisao = os.getenv("REEL_REPUBLICACAO", "").strip()
    kinds = (("REELS",) if revisao and sys.argv[1] == "live" else
             (("REELS", "STORIES") if morning or sys.argv[1] != "live" else ("REELS",)))
    for kind in kinds:
        deliver(snap, brief, video, kind, sys.argv[1] == "live")

if __name__=="__main__":main()

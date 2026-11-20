"""Publicador de plantão com recibos independentes de Reel e Story.
Para canais privados usa upload resumível, sem exposição do vídeo no GitHub.
"""
import argparse, json, os, re, time
from pathlib import Path
from urllib.parse import urlparse
import requests
from tools.alerta_14h import validar

EXPECTED="otemposp"
STATE=Path("data/alertas_14h_publicados.json")

def main():
    parser=argparse.ArgumentParser()
    m=parser.add_mutually_exclusive_group(required=True)
    m.add_argument("--video-url")
    m.add_argument("--video-file")
    parser.add_argument("--consulta",default="output/alertas/consulta.json")
    parser.add_argument("--legenda",default="output/alertas/LEGENDA.txt")
    args=parser.parse_args()
    rel=validar(json.loads(Path(args.consulta).read_text()))
    caption=Path(args.legenda).read_text().strip()
    if rel["canal"].lower() not in caption.lower(): raise ValueError("Canal não está na legenda")
    if not caption or len(caption)>2200: raise ValueError("Legenda ausente ou extensa")
    uid=os.environ.get("IG_USER_ID","").strip()
    token=os.environ.get("IG_ACCESS_TOKEN","").strip()
    if not uid.isdecimal() or not token: raise ValueError("Meta: credenciais não disponíveis")
    version=os.environ.get("META_GRAPH_VERSION","v26.0")
    if not re.fullmatch(r"v\d+\.\d+",version): raise ValueError("Versão Graph API inválida")
    host="graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com"
    base=f"https://{host}/{version}"
    header={"Authorization":"Bearer "+token}
    if args.video_url:
        u=urlparse(args.video_url)
        if u.scheme!="https" or u.netloc!="github.com" or not u.path.startswith(
            "/"+os.environ["GITHUB_REPOSITORY"]+"/releases/download/"):
            raise ValueError("URL deve ser release temporário do próprio canal")
    if args.video_file:
        f=Path(args.video_file)
        if not f.is_file() or f.stat().st_size<100000: raise ValueError("MP4 ausente ou pequeno")
    def obj(resp):
        try: d=resp.json()
        except ValueError: raise RuntimeError("Meta não retornou JSON")
        if not resp.ok or "error" in d:
            raise RuntimeError("Meta: "+str(d.get("error",{}).get("message",resp.status_code))[:180])
        return d
    def post(path,params):
        return obj(requests.post(f"{base}/{path}",data=params,headers=header,timeout=90))
    def get(path,fields):
        return obj(requests.get(f"{base}/{path}",params={"fields":fields},headers=header,timeout=35))
    conta=get(uid,"id,username")
    if str(conta.get("id"))!=uid or conta.get("username","").lower()!=EXPECTED:
        raise ValueError("Conta de Instagram inesperada: publicação BLOQUEADA")
    estado=json.loads(STATE.read_text()) if STATE.exists() else {}
    rec=estado.setdefault(rel["data"],{})
    def salvar():
        STATE.parent.mkdir(parents=True,exist_ok=True)
        tmp=STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(estado,ensure_ascii=False,indent=2))
        tmp.replace(STATE)
    for tipo in ("REELS","STORIES"):
        if rec.get(tipo):
            print(tipo,"já registrado:",rec[tipo]);continue
        key=tipo+"_container"
        if not rec.get(key):
            pedido={"media_type":tipo}
            if tipo=="REELS": pedido.update(caption=caption,share_to_feed="true")
            if args.video_url: pedido["video_url"]=args.video_url
            else: pedido["upload_type"]="resumable"
            container=str(post(uid+"/media",pedido)["id"])
            if not container.isdecimal():raise ValueError("Container inválido")
            rec[key]=container
            salvar()
            if args.video_file:
                with Path(args.video_file).open("rb") as arquivo:
                    up=requests.post(f"https://rupload.facebook.com/ig-api-upload/{version}/{container}",
                        headers={"Authorization":"OAuth "+token,"offset":"0",
                                 "file_size":str(Path(args.video_file).stat().st_size)},
                        data=arquivo,timeout=(10,180))
                if obj(up).get("success") is not True:
                    raise RuntimeError("Meta não confirmou upload resumível")
        container=rec[key]
        for _ in range(70):
            code=get(container,"status_code").get("status_code")
            if code=="FINISHED":break
            if code=="PUBLISHED":
                rec[tipo]={"container_publicado":container}
                salvar()
                print(tipo,"container já publicado",container)
                break
            if code in ("ERROR","EXPIRED"):
                raise RuntimeError(tipo+": estado "+str(code))
            time.sleep(5)
        else: raise TimeoutError(tipo+": vídeo não processado na Meta")
        if rec.get(tipo): continue
        item=post(uid+"/media_publish",{"creation_id":container})
        if not item.get("id"): raise RuntimeError("Meta não confirmou publicação")
        rec[tipo]=str(item["id"])
        salvar()
        print(tipo,"publicado com ID",rec[tipo])
    print("RECIBOS",json.dumps(rec,ensure_ascii=False))

if __name__=="__main__": main()

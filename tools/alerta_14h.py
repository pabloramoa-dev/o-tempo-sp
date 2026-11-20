"""Alerta regional diário, 14h BRT. ICON+GFS, INMET CAP, Defesa Civil; falha fechada.
Não confundir previsão de tempo severo com ocorrência confirmada.
"""
import json, math, os, re, unicodedata, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

CONFIG = {"uf":"SP","label":"São Paulo","handle":"@otemposp","municipio":"São Paulo","defesa_civil":"https://www.defesacivil.sp.gov.br/","cidades":[["São Paulo",-23.5505,-46.6333],["Santos",-23.9608,-46.3336],["Campinas",-22.9056,-47.0608],["São José dos Campos",-23.1896,-45.8841],["Sorocaba",-23.5015,-47.4526],["Bauru",-22.3145,-49.0587],["Ribeirão Preto",-21.1704,-47.8103],["Presidente Prudente",-22.1256,-51.3889],["Marília",-22.214,-49.9455],["Registro",-24.4871,-47.8435]]}
TZ = ZoneInfo("America/Sao_Paulo")
INMET = "https://apiprevmet3.inmet.gov.br/avisos/ativos"
FORECAST = "https://api.open-meteo.com/v1/forecast"
MODELOS = ("icon_seamless", "gfs_seamless")
HOURLY = ("precipitation", "wind_gusts_10m", "weather_code", "temperature_2m")
NS = {"c":"urn:oasis:names:tc:emergency:cap:1.2"}
PRIORIDADE = {"granizo":4, "temporal":3, "chuva":2, "vento":1}
TIPOS = {"TEMPESTADE":"temporal", "CHUVAS INTENSAS":"chuva",
         "ACUMULADO DE CHUVA":"chuva", "VENDAVAL":"vento", "GRANIZO":"granizo"}

def normal(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c)).upper().strip()

def fetch(url, params=None):
    r=requests.get(url,params=params,timeout=(10,35),
                   headers={"User-Agent":"PrevisaoTempoBrasil/2.0 (avisos meteorologicos publicos)"})
    r.raise_for_status()
    if r.url.split("/")[2] != url.split("/")[2]:
        raise RuntimeError("Redirecionamento para domínio inesperado")
    return r

def ler_cap(content, agora):
    root=ET.fromstring(content)
    def f(k): return root.findtext("c:"+k,"",NS)
    if f("status")!="Actual" or f("msgType") not in ("Alert","Update") or f("scope")!="Public":
        return []
    if not f("sender").lower().endswith("@inmet.gov.br"):
        return []
    sent=datetime.fromisoformat(f("sent"))
    if sent.tzinfo is None or sent>agora+timedelta(minutes=5):
        return []
    avisos=[]
    for info in root.findall("c:info",NS):
        def v(k): return info.findtext("c:"+k,"",NS)
        if v("language") not in ("pt-BR","pt"): continue
        inicio=datetime.fromisoformat(v("onset") or v("effective"))
        fim=datetime.fromisoformat(v("expires"))
        if inicio.tzinfo is None or fim.tzinfo is None or fim<=agora or inicio>=fim: continue
        if inicio>agora+timedelta(hours=24): continue
        params={p.findtext("c:valueName","",NS):p.findtext("c:value","",NS)
                for p in info.findall("c:parameter",NS)}
        locais=set(normal(x) for x in re.findall(
            r"(?:^|,)\s*([^,]+?)\s+-\s+"+CONFIG["uf"]+r"\s+\(\d{7}\)",
            params.get("Municipios","")))
        tipo=TIPOS.get(normal(v("event")))
        if not tipo: continue
        municipios=[n for n,lat,lon in CONFIG["cidades"] if normal(n) in locais]
        if CONFIG["uf"]=="DF" and normal(CONFIG["municipio"]) in locais:
            municipios=[n for n,_,_ in CONFIG["cidades"]]
        if not municipios: continue
        url=v("web")
        if not url.startswith("https://avisos.inmet.gov.br/"): continue
        avisos.append({"id":f("identifier"),"fonte":"INMET","url":url,
                       "tipo":tipo,"evento":v("event"),"severidade":v("severity"),
                       "cidades":municipios,"inicio":inicio.isoformat(),
                       "fim":fim.isoformat(),"emitido_em":sent.isoformat(),
                       "descricao":v("description"),"instrucoes":v("instruction")})
    return avisos

def fontes(agora):
    out={}
    try:
        j=fetch(INMET).json()
        if not isinstance(j.get("hoje"),list) or not isinstance(j.get("futuro"),list):
            raise ValueError("Resposta INMET incompleta")
        ids=set()
        for a in j["hoje"]+j["futuro"]:
            area=a.get("municipios","")
            if re.search(r"\s-\s"+CONFIG["uf"]+r"\s+\(\d{7}\)",area) and any(
                normal(nome) in normal(area) for nome,_,_ in CONFIG["cidades"]):
                ids.add(str(a["id"]))
        avisos=[]
        for identifier in sorted(ids):
            if not identifier.isdigit(): raise ValueError("ID INMET invalido")
            avisos.extend(ler_cap(fetch(
                "https://apiprevmet3.inmet.gov.br/avisos/rss/"+identifier).content,agora))
        # Elimina avisos CAP repetidos na mesma consulta.
        uniq={(a["id"],a["tipo"],a["inicio"]):a for a in avisos}
        out["inmet"]={"status":"ok","url":INMET,"dados":list(uniq.values())}
    except Exception as exc:
        out["inmet"]={"status":"indisponivel","url":INMET,"erro":str(exc)[:200],"dados":[]}
    # Painel estadual é fonte complementar, NÃO um CAP estruturado.
    try:
        r=fetch(CONFIG["defesa_civil"])
        out["defesa_civil"]={"status":"ok","url":CONFIG["defesa_civil"],
                            "observacao":"Fonte contextual, não comprova temporal"}
    except Exception as exc:
        out["defesa_civil"]={"status":"indisponivel","url":CONFIG["defesa_civil"],
                            "erro":str(exc)[:200]}
    return {"fontes":out,"completa":out["inmet"]["status"]=="ok",
            "observacao":"Falha de consulta nao significa ausencia de alerta. Defesa Civil e complementar."}

def por_hora(payload,agora):
    h=payload["hourly"]
    u=payload["hourly_units"]
    if u["precipitation"]!="mm" or u["wind_gusts_10m"]!="km/h":
        raise ValueError("Unidades de previsao inesperadas")
    inicio=agora.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
    arr={}
    for i,st in enumerate(h["time"]):
        t=datetime.fromisoformat(st).replace(tzinfo=TZ)
        if inicio<=t<inicio+timedelta(hours=24):
            row={k:h[k][i] for k in HOURLY}
            if any(v is None or not math.isfinite(float(v)) for v in row.values()):
                raise ValueError("Dados horarios incompletos")
            if any(float(row[k])<0 for k in HOURLY[:3]):
                raise ValueError("Dado meteorologico negativo")
            arr[t]=row
    if len(arr)!=24: raise ValueError("Previsao incompleta nas proximas 24h")
    return arr

def sinais(linhas):
    ev=[]
    for t, row in sorted(linhas.items()):
        def add(tipo,valor,unidade,horas=1):
            ev.append({"tipo":tipo,"inicio":t.isoformat(),
                       "fim":(t+timedelta(hours=horas)).isoformat(),
                       "valor":round(float(valor),1),"unidade":unidade,
                       "temperatura_c":round(float(row["temperature_2m"]),1)})
        code=int(row["weather_code"])
        if code in (95,96,99): add("temporal",code,"WMO")
        if code in (96,99): add("granizo",code,"WMO")
        if row["wind_gusts_10m"]>=60: add("vento",row["wind_gusts_10m"],"km/h")
        if row["precipitation"]>=20: add("chuva",row["precipitation"],"mm em 1h")
        for n,lim in ((3,30),(24,50)):
            win=[linhas.get(t+timedelta(hours=j)) for j in range(n)]
            if all(win) and sum(float(x["precipitation"]) for x in win)>=lim:
                add("chuva",sum(float(x["precipitation"]) for x in win),f"mm em {n}h",n)
    return ev

def verificar(agora=None):
    agora=agora or datetime.now(TZ)
    oficial=fontes(agora)
    respostas=[]
    for model in MODELOS:
        params={"latitude":",".join(str(c[1]) for c in CONFIG["cidades"]),
                "longitude":",".join(str(c[2]) for c in CONFIG["cidades"]),
                "hourly":",".join(HOURLY),"models":model,
                "timezone":"America/Sao_Paulo","forecast_days":3,
                "wind_speed_unit":"kmh","precipitation_unit":"mm"}
        j=fetch(FORECAST,params).json()
        if not isinstance(j,list) or len(j)!=len(CONFIG["cidades"]):
            raise ValueError("Cobertura regional incompleta em "+model)
        respostas.append(j)
    eventos=[]
    base_temperaturas={}
    for i,(nome,lat,lon) in enumerate(CONFIG["cidades"]):
        a,b=[por_hora(respostas[k][i],agora) for k in (0,1)]
        base_temperaturas[nome]=round(float(next(iter(a.values()))["temperature_2m"]),1)
        aa,bb=sinais(a),sinais(b)
        for e in aa:
            pares=[f for f in bb if f["tipo"]==e["tipo"] and f["unidade"]==e["unidade"]
                   and max(e["inicio"],f["inicio"])<min(e["fim"],f["fim"])]
            if pares:
                f=max(pares,key=lambda x:x["valor"])
                eventos.append(dict(e,local=nome,modelos=list(MODELOS),
                                    valor=min(e["valor"],f["valor"]),evidencias=[e,f]))
    eventos.sort(key=lambda x:(-PRIORIDADE[x["tipo"]],-x["valor"],x["inicio"]))
    modo="dois_modelos"
    avisos=oficial["fontes"]["inmet"]["dados"]
    if not eventos:
        candidatos=[a for a in avisos if a["tipo"] in ("temporal","chuva","granizo","vento")
                    and datetime.fromisoformat(a["inicio"])<=agora<datetime.fromisoformat(a["fim"])]
        candidatos.sort(key=lambda a:((a["severidade"] or "")=="Severe",len(a["cidades"])),reverse=True)
        if candidatos:
            a=candidatos[0]
            tipo=a["tipo"]
            eventos=[{"tipo":tipo,"local":a["cidades"][0],
                      "inicio":a["inicio"],"fim":a["fim"],
                      "fonte":"INMET","aviso_id":a["id"],
                      "observacao":"Aviso oficial; nao e concordancia de dois modelos"}]
            modo="aviso_oficial_inmet"
    correspondentes=[a for a in avisos if any(e["local"] in a["cidades"] and e["tipo"]==a["tipo"]
                  for e in eventos)]
    return {"data":agora.date().isoformat(),"emitido_em":agora.isoformat(),
            "local":CONFIG["label"],"canal":CONFIG["handle"],"uf":CONFIG["uf"],
            "modelos":list(MODELOS),"url_modelos":FORECAST,"eventos":eventos,
            "modo":modo,"publicar":bool(eventos) and oficial["completa"],
            "temperaturas_reais":base_temperaturas,
            "avisos_oficiais_correspondentes":correspondentes,
            "oficiais":oficial,"cidades_consultadas":len(CONFIG["cidades"])}

def validar(r,agora=None):
    agora=agora or datetime.now(TZ)
    emitido=datetime.fromisoformat(r["emitido_em"])
    if not timedelta(0)<=agora-emitido<=timedelta(hours=2):
        raise ValueError("Consulta vencida")
    if not r["oficiais"]["completa"] or not r["publicar"] or not r["eventos"]:
        raise ValueError("Sem condicao segura de publicacao")
    if datetime.fromisoformat(r["eventos"][0]["fim"])<=agora:
        raise ValueError("Evento venceu")
    return r

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--saida",default="output/alertas/consulta.json")
    args=p.parse_args()
    saida=Path(args.saida)
    saida.parent.mkdir(parents=True,exist_ok=True)
    rel=verificar()
    saida.write_text(json.dumps(rel,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"publicar":rel["publicar"],"modo":rel["modo"],
                      "eventos":len(rel["eventos"]),
                      "avisos_inmet":len(rel["oficiais"]["fontes"]["inmet"]["dados"]),
                      "oficiais":{k:v["status"] for k,v in rel["oficiais"]["fontes"].items()}}))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as f:
            f.write("publicar="+str(rel["publicar"]).lower()+"\n")
if __name__=="__main__": main()

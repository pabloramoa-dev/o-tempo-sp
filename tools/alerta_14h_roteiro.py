"""Roteiro do plantão com fonte e janela verificadas; jamais afirma ocorrência certa."""
from datetime import datetime
from pathlib import Path
from tools.alerta_14h import validar, TZ

ROTULOS = {"granizo":"possibilidade de granizo", "temporal":"risco de temporal",
           "chuva":"chuva intensa", "vento":"ventos fortes", "ciclone":"risco associado a ciclone"}

def montar(rel):
    validar(rel)
    e=rel["eventos"][0]
    inicio,fim=datetime.fromisoformat(e["inicio"]),datetime.fromisoformat(e["fim"])
    data_alvo=inicio.astimezone(TZ).date()
    quando="hoje" if data_alvo.isoformat()==rel["data"] else "amanhã" if (
        data_alvo-rel_date(rel)).days==1 else data_alvo.strftime("%d/%m")
    local=e["local"]
    tipo=ROTULOS[e["tipo"]]
    oficiais=rel.get("avisos_oficiais_correspondentes") or []
    if rel["modo"]=="aviso_oficial_inmet":
        aviso=next((a for a in oficiais if a["id"]==e.get("aviso_id")),None)
        if aviso is None: raise ValueError("Aviso oficial não corresponde ao relatório")
        nivel={"Moderate":"amarelo", "Severe":"laranja", "Extreme":"vermelho"}.get(
            aviso.get("severidade"),"meteorológico")
        abertura=(f"Atenção, {rel['local']}! O INMET mantém alerta {nivel} de "
                  f"{aviso['evento'].lower()} válido até {fim:%Hh%M} de {fim:%d/%m}.")
        detalhe=(("O aviso oficial menciona um ciclone. Consulte a trajetória e as orientações do órgão emissor. "
                  "A intensidade dos efeitos varia conforme a região.") if e["tipo"]=="ciclone" else
                 ("O aviso indica risco potencial de chuva forte, rajadas de vento e, "
                  "dependendo da área, possibilidade de granizo. "
                  "Isso não significa que a tempestade ocorrerá em todas as cidades."))
        atrib="Fonte: aviso oficial do INMET."
    else:
        abertura=(f"Atenção, {rel['local']}! Dois modelos indicam {tipo} "
                  f"{quando}, com início previsto por volta das {inicio:%Hh}. "
                  f"Destaque para {local}.")
        unidade=e["unidade"]
        if e["tipo"]=="vento":
            detalhe=f"Os dois modelos apontam rajadas de pelo menos {e['valor']:g} quilômetros por hora."
        elif e["tipo"]=="chuva":
            detalhe=f"Os dois modelos apontam acumulado de pelo menos {e['valor']:g} {unidade}."
        else:
            detalhe="ICON e GFS concordam com essa possibilidade, mas ela não é certeza de ocorrência."
        atrib="Fontes: ICON e GFS via Open-Meteo."
    oficial=""
    if oficiais and rel["modo"]!="aviso_oficial_inmet":
        a=oficiais[0]
        oficial=f" O INMET também possui aviso de {a['evento'].lower()} válido para a área."
    orientacao=("É uma previsão de risco, não certeza. Evite ficar debaixo de árvores "
                "durante rajadas e acompanhe os canais da Defesa Civil.")
    encerrar=f"Compartilhe com quem mora em {rel['local']}."
    textos=[abertura,detalhe+oficial,orientacao,encerrar]
    cabecalho=f"PLANTÃO DO TEMPO — {rel['local'].upper()} | {rel['data']}"
    legenda=(cabecalho+"\n\n"+"\n\n".join(textos)+
             "\n\n"+atrib+" Consulta: "+rel["emitido_em"]+
             "\nINMET: https://avisos.inmet.gov.br/ "
             "\nDefesa Civil: 199 | Bombeiros: 193 "
             "\n"+rel["canal"]+" #AlertaDoTempo #Tempestade")
    return textos, legenda

def rel_date(rel):
    from datetime import date
    return date.fromisoformat(rel["data"])

def batidas(rel):
    textos, _=montar(rel)
    return [
      {"tipo":"gancho","fala":textos[0],"legenda":textos[0],
       "dados":{"numero":"!","sub":"ALERTA DO TEMPO","titulo":"PLANTÃO"}},
      {"tipo":"alerta","fala":textos[1],"legenda":textos[1],
       "dados":{"titulo":"PREVISÃO DE RISCO","detalhe":rel["eventos"][0]["local"]}},
      {"tipo":"frase","fala":textos[2],"legenda":textos[2],"dados":{}},
      {"tipo":"cta","fala":textos[3],"legenda":textos[3],
       "dados":{"chamada":"COMPARTILHE","sub":rel["canal"]}},
    ]

def texto_para_arquivo(rel, path):
    _, legenda=montar(rel)
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(legenda,encoding="utf-8")
    return legenda

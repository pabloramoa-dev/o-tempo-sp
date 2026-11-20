"""Plantão SP: preserva o estúdio em dupla, personagens e vozes do canal."""
import json
from pathlib import Path
from tools.alerta_14h import validar
from tools.alerta_14h_roteiro import batidas, texto_para_arquivo

def main():
    rel=validar(json.loads(Path("output/alertas/consulta.json").read_text()))
    out=Path("output/alertas/ALERTA.mp4")
    out.parent.mkdir(parents=True,exist_ok=True)
    legenda=texto_para_arquivo(rel,out.parent/"LEGENDA.txt")
    import hyperframes.gerar_dupla as dupla
    beats=batidas(rel)
    # Bira e Bia alternam falas; o último encerramento fica com Bia.
    falantes=["bira","bia","bira","bia"]
    nome=rel["eventos"][0]["local"]
    temps=rel["temperaturas_reais"].get(nome)
    cidades=[{"nome":nome,"min":temps["min"],"max":temps["max"],
              "chuva_mm":None}] if temps else []
    dupla.roteiro_dupla=lambda _: (beats,falantes,cidades,"bira","bia")
    dupla.C.TITULOS["eventos_fim_de_semana"]="PLANTÃO TEMPO SEVERO"
    brief={"when":"hoje","date":rel["data"],"is_fixture":False,
           "especial_eventos":True,"caption":legenda,
           "wettest":{"rain_pct":None,"rain_mm":None}}
    dupla.render_brief_dupla(brief,out)
    if out.stat().st_size<100000:
        raise RuntimeError("MP4 de alerta pequeno demais")
    print("ALERTA SP:",out, out.stat().st_size)

if __name__=="__main__": main()

"""Reel especial @otemposp: Bira + Bia, pipeline HyperFrames existente.

Pauta com dois eventos verificados e previsao horaria real; nunca renderizar
dados ilustrativos como se reais fossem.
"""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.eventos_fim_de_semana import run as preparar_pauta

TZ = ZoneInfo("America/Sao_Paulo")
ROOT = Path(__file__).resolve().parents[1]

def frase_clima(s):
    t = round(s["temperatura_c"])
    chuva = s["probabilidade_chuva_pct"]
    raj = s["rajadas_kmh"]
    if chuva >= 65:
        clima = f"chance alta de chuva, {chuva} por cento"
    elif chuva >= 40:
        clima = f"possibilidade de chuva, {chuva} por cento"
    else:
        clima = f"chance de chuva de {chuva} por cento"
    dica = ("Leve capa de chuva!" if chuva >= 40 else
            "Leve um agasalho!" if t <= 18 else
            "Leve água!" if t >= 30 else "Confira o tempo antes de sair!")
    if raj >= 50:
        dica = "Atenção às rajadas de vento. Siga as orientações do evento!"
    return t, clima, dica

def pauta_video(data):
    eventos = data["eventos"]
    if len(eventos) != 2:
        raise ValueError("O especial exige exatamente dois eventos")
    beats, falantes, cidades = [], [], []
    def add(personagem, tipo, fala, **campos):
        beats.append({"tipo": tipo, "fala": fala, "legenda": fala, "dados": campos})
        falantes.append(personagem)
    add("bira", "nenhum", "Vai sair neste fim de semana em São Paulo? Atenção ao tempo em dois grandes eventos!")
    for idx, e in enumerate(eventos):
        s = e["sessoes"][0]
        dt = datetime.fromisoformat(s["data_hora"]).astimezone(TZ)
        t, clima, dica = frase_clima(s)
        quem = "bia" if idx == 0 else "bira"
        dia = ("sexta-feira" if dt.weekday() == 4 else
               "sábado" if dt.weekday() == 5 else "domingo")
        lugar_curto = "IBIRAPUERA" if "Ibirapuera" in e["local"] else "CENTRO DE SÃO PAULO"
        hora = f"{dt.hour} horas"
        fala = (f"{s['atracao']}, no {e['evento']}, {dia}, às {hora}, "
                f"com {t} graus e {clima}.")
        add(quem, "gancho", fala, numero=f"{t}°", sub=f"{dia.upper()} {dt:%Hh} • {lugar_curto}",
            local=e["evento"])
        add("bira" if quem == "bia" else "bia", "nenhum", dica)
        cidades.append({"nome": lugar_curto, "min": t, "max": t,
                        "chuva_mm": s["chuva_mm_na_hora"]})
    add("bia", "cta", "Vai a algum desses eventos? Compartilhe com a galera!",
        chamada="COMPARTILHE COM A GALERA", sub="@OTEMPOSP • TODA SEXTA ÀS 14H")
    return beats, falantes, cidades

def render(now=None):
    now = now or datetime.now(TZ)
    pauta = preparar_pauta(now)
    events = pauta["eventos"]
    caption = (ROOT / "output/eventos_fim_de_semana/legenda.txt").read_text(encoding="utf-8")
    brief = {
        "when": "hoje", "date": pauta["edicao"], "is_fixture": False, "especial_eventos": True,
        "caption": caption, "wettest": {"rain_pct": max(e["sessoes"][0]["probabilidade_chuva_pct"] for e in events),
                                      "rain_mm": max(e["sessoes"][0]["chuva_mm_na_hora"] or 0 for e in events)}
    }
    # A mesma cadeia do boletim diario (dupla/HyperFrames/Kokoro);
    # troca-se somente a pauta do especial de eventos.
    import hyperframes.gerar_dupla as dupla
    dupla.roteiro_dupla = lambda _: (*pauta_video(pauta), "bira", "bia")
    output = ROOT / "output/eventos_fim_de_semana/especial-eventos-sp.mp4"
    dupla.render_brief_dupla(brief, output)
    if not output.is_file() or output.stat().st_size < 1000000:
        raise RuntimeError("O renderizador nao produziu MP4 valido")
    (output.parent / "publicacao.json").write_text(
        json.dumps({"edicao": pauta["edicao"], "gerado_em": now.isoformat(),
                    "eventos": [e["evento"] for e in events], "mp4": output.name,
                    "publicado": False}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"MP4: {output} ({output.stat().st_size} bytes)")
    return output

if __name__ == "__main__":
    render()

# QA especial: validacao independente dos boletins diarios.

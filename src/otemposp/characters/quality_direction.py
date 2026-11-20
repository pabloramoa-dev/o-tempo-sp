"""Checagem estrutural adicional (não julga a exatidão da meteorologia)."""
from __future__ import annotations

import json
from pathlib import Path


def verificar(pacote, probe):
    batidas = pacote.get("batidas", [])
    plano = pacote.get("direcao", [])
    erros, avisos = [], []
    if not batidas:
        erros.append("Não há falas no boletim")
    if plano and len(plano) != len(batidas):
        erros.append("Direção diferente do total de falas")
    if pacote.get("personagem") not in {"bira", "bia"}:
        erros.append("Personagem fora do elenco diário")
    if pacote.get("especial_alerta") and not pacote.get("demo"):
        if not pacote.get("dupla") or not pacote.get("cidades"):
            erros.append("O alerta exige dupla Bira/Bia e localidade real")
        if not pacote.get("batidas") or pacote["batidas"][-1].get("tipo") != "cta":
            erros.append("Alerta sem CTA final")
    if pacote.get("especial_eventos") and not pacote.get("especial_alerta") and not pacote.get("demo"):
        if not pacote.get("dupla"):
            erros.append("O especial exige Bira e Bia")
        if len(pacote.get("cidades", [])) != 2:
            erros.append("O especial exige duas localidades dos eventos")
        if sum(b.get("tipo") == "gancho" for b in batidas) != 2:
            erros.append("O especial exige dois eventos meteorologicos")
        if not batidas or batidas[-1].get("tipo") != "cta":
            erros.append("O especial exige CTA no encerramento")
        if sum(b.get("tipo") == "cta" for b in batidas) != 1:
            erros.append("O especial deve ter somente um CTA")
    if not pacote.get("demo") and not pacote.get("especial_eventos"):
        dupla = pacote.get("dupla")
        if dupla:
            # Formato em dupla: saudação curta, o gancho logo na 2ª fala, o CTA
            # com quem apresenta e a despedida de quem acompanha no fim.
            if len(batidas) < 2 or batidas[1].get("tipo") != "gancho":
                erros.append("Dupla sem gancho meteorológico logo após a saudação")
            ctas = [i for i, b in enumerate(batidas) if b.get("tipo") == "cta"]
            if ctas != [len(batidas) - 2, len(batidas) - 1]:
                erros.append("Dupla deve terminar com o CTA e a despedida")
            elif dupla.get("falantes", [None])[ctas[0]] != dupla.get("apresenta"):
                erros.append("CTA da dupla deve ficar com quem apresenta")
        else:
            if batidas and batidas[0].get("tipo") != "gancho":
                erros.append("Reel sem gancho meteorológico no primeiro quadro")
            if batidas and batidas[-1].get("tipo") != "cta":
                erros.append("Convite de compartilhamento não está no encerramento")
            if sum(b.get("tipo") == "cta" for b in batidas) != 1:
                erros.append("Reel deve ter um único CTA")
        if len(pacote.get("cidades", [])) != 11:
            erros.append("Reel deve apresentar as onze localidades verificadas")

    for i, b in enumerate(batidas):
        if not str(b.get("fala", "")).strip():
            erros.append(f"Fala {i} vazia")
        if not str(b.get("legenda", "")).strip():
            erros.append(f"Legenda {i} vazia")
        if float(b.get("fim", 0)) <= float(b.get("ini", 0)):
            erros.append(f"Fala {i} sem duração")
        if i and float(b["ini"]) < float(batidas[i-1]["fim"])-.002:
            erros.append(f"Falas {i-1} e {i} sobrepostas")
    if not pacote.get("cidades"):
        avisos.append("Painel regional sem cidades; revisar conteúdo")
    streams = probe.get("streams", [])
    if not any(s.get("codec_type") == "audio" for s in streams):
        erros.append("MP4 sem áudio")
    if not any(s.get("codec_type") == "video" for s in streams):
        erros.append("MP4 sem vídeo")
    if len({p["gesto"] for p in plano}) <= 1:
        avisos.append("Pouca variação de gestos")
    return {"aprovado_tecnicamente": not erros, "erros": erros, "avisos": avisos,
            "batidas": len(batidas), "gestos": sorted({p["gesto"] for p in plano}),
            "camera_adaptativa": bool(plano),
            "verificacoes": ["timeline", "texto e legenda", "áudio/vídeo no MP4"],
            "limite": "Não substitui checagem meteorológica nem inspeção visual de quadros."}


def salvar(caminho, relatorio):
    Path(caminho).write_text(json.dumps(relatorio, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

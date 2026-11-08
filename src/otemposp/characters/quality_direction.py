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

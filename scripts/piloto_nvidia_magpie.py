"""Piloto ISOLADO NVIDIA Magpie: injeta vozes no renderizador de dupla sem alterar produção.
Dados ilustrativos e bloqueio de publicação são intencionais.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hyperframes"))
import gerar_dupla as D

def magpie_narrar(bat, falante, work):
    cli = Path(os.environ.get("MAGPIE_CLI", "/tmp/magpie-tts.cpp/build/examples/cli/magpie-cli"))
    model = Path(os.environ.get("MAGPIE_MODEL", "/tmp/magpie.gguf"))
    if not cli.is_file() or not model.is_file():
        raise FileNotFoundError("Magpie CLI e modelo NVIDIA são obrigatórios; sem fallback oculto.")
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    blocos, segs, t = [], [], 0.0
    for i, (b, quem) in enumerate(zip(bat, falante)):
        speaker = "Jason" if quem == "bira" else "Sofia"
        caminho = work / f"magpie_{i:02d}_{quem}.wav"
        texto = D.KK.normalizar_horario_para_voz(b["fala"])
        subprocess.run([str(cli), "say", "--model", str(model),
                        "--text", texto, "--lang", "pt-BR", "--speaker", speaker,
                        "--seed", str(2230+i), "--threads", "4",
                        "--output", str(caminho)], check=True)
        pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(caminho),
                                        "-ac", "1", "-ar", str(D.SR), "-f", "f32le", "-"])
        s = np.frombuffer(pcm, np.float32).copy()
        if len(s) < D.SR // 5:
            raise RuntimeError(f"Áudio muito curto no segmento {i}")
        proximo = falante[i + 1] if i + 1 < len(bat) else quem
        gap = D.GAP_TROCA if proximo != quem else D.GAP_MESMO
        n_gap = int(gap * D.SR)
        segs.append(dict(i=i, quem=quem, ini=round(t, 3),
                         fim_fala=round(t + len(s)/D.SR, 3),
                         fim=round(t + (len(s)+n_gap)/D.SR, 3), texto=b["fala"]))
        blocos.extend([(s, quem), (np.zeros(n_gap, np.float32), None)])
        t += (len(s) + n_gap) / D.SR
    voz = np.concatenate([x for x, _ in blocos])
    pico = max(float(np.abs(voz).max()), 1e-6)
    pistas = {q: np.concatenate([x if quem == q else np.zeros_like(x) for x, quem in blocos]) / pico * .97
              for q in ("bia", "bira")}
    raw = work / "raw.wav"
    D.HF.gravar_wav(raw, voz / pico * .97, D.SR)
    return segs, pistas, raw

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--turno", choices=["hoje", "amanhã"], default="amanhã")
    ap.add_argument("--qualidade", choices=["draft", "standard", "high"], default="draft")
    args = ap.parse_args()
    D.narrar_dupla = magpie_narrar
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    D.render_brief_dupla(D.brief_ilustrativo(args.turno, __import__("datetime").date.today().isoformat()),
                         out, args.qualidade)
    if not out.is_file() or out.stat().st_size < 10000:
        raise RuntimeError("MP4 não foi gerado corretamente")
    print(f"Piloto NVIDIA disponível: {out} ({out.stat().st_size} bytes)")

if __name__ == "__main__":
    main()

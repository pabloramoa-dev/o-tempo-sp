#!/usr/bin/env python3
"""
lipsync_amplitude.py — lip sync SEM Rhubarb, direto da energia do áudio.

Por que existe: o Rhubarb dá visemas fonéticos (melhor qualidade), mas exige
compilar do fonte (~3 min) e é uma dependência pesada pra um job que roda TODO
DIA no GitHub Actions. Neste estilo (boneco cartoon, boca pequena, vídeo de 30s
visto no celular), a boca movida pela ENERGIA do áudio lê igualmente bem.

Ele grava exatamente o MESMO formato do Rhubarb:
    {"mouthCues": [{"start": 0.0, "end": 0.12, "value": "X"}, ...]}
Portanto o `dvh_lip.anexar_lipsync()` da skill funciona sem nenhuma alteração —
e se um dia quiser trocar pelo Rhubarb, é só gerar o JSON pelo outro caminho.

Uso:
    python lipsync_amplitude.py narracao.wav lip_full.json [--fps 22]
"""
import argparse, json, sys, wave
import numpy as np


def ler_wav(caminho):
    w = wave.open(caminho, "rb")
    n, sr, canais, larg = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
    raw = w.readframes(n)
    w.close()
    dt = {1: np.int8, 2: np.int16, 4: np.int32}[larg]
    x = np.frombuffer(raw, dtype=dt).astype(np.float32)
    if canais > 1:
        x = x.reshape(-1, canais).mean(axis=1)
    pico = float(np.max(np.abs(x))) or 1.0
    return x / pico, sr


def gerar_cues(x, sr, fps=22, silencio=0.055):
    """Divide em janelas de 1/fps, mede o RMS e mapeia pra visema."""
    passo = max(1, int(sr / fps))
    janelas = int(np.ceil(len(x) / passo))
    rms = np.array([
        float(np.sqrt(np.mean(x[i * passo:(i + 1) * passo] ** 2) + 1e-12))
        for i in range(janelas)])

    # suaviza pra boca não tremer frame a frame
    k = np.array([0.25, 0.5, 0.25])
    rms = np.convolve(rms, k, mode="same")

    falando = rms[rms > silencio]
    if len(falando) < 5:
        ref = rms.max() or 1.0
        cortes = [ref * f for f in (0.25, 0.5, 0.75)]
    else:
        cortes = [np.percentile(falando, p) for p in (30, 60, 85)]

    # zero-crossing rate distingue sons "fechados"/sibilantes de vogais abertas
    zcr = np.array([
        float(np.mean(np.abs(np.diff(np.sign(x[i * passo:(i + 1) * passo]))) > 0) or 0.0)
        for i in range(janelas)])
    zcr_alto = np.percentile(zcr[rms > silencio], 70) if len(falando) >= 5 else 1.0

    cues = []
    for i in range(janelas):
        e = rms[i]
        if e <= silencio:
            v = "X"                      # boca fechada (silêncio)
        elif e < cortes[0]:
            v = "B"                      # entreaberta
        elif e < cortes[1]:
            v = "F" if zcr[i] > zcr_alto else "C"   # sibilante estreita / média
        elif e < cortes[2]:
            v = "E" if zcr[i] > zcr_alto else "C"
        else:
            v = "D"                      # vogal aberta
        cues.append({"start": round(i / fps, 4),
                     "end": round((i + 1) / fps, 4),
                     "value": v})

    # funde janelas vizinhas iguais (JSON menor, updater mais leve)
    fundido = []
    for c in cues:
        if fundido and fundido[-1]["value"] == c["value"]:
            fundido[-1]["end"] = c["end"]
        else:
            fundido.append(dict(c))
    return fundido


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("saida", nargs="?", default="lip_full.json")
    ap.add_argument("--fps", type=int, default=22)
    ap.add_argument("--silencio", type=float, default=0.055)
    a = ap.parse_args()

    x, sr = ler_wav(a.wav)
    cues = gerar_cues(x, sr, a.fps, a.silencio)
    json.dump({"metadata": {"soundFile": a.wav, "duration": round(len(x) / sr, 3)},
               "mouthCues": cues}, open(a.saida, "w"), ensure_ascii=False)
    falando = sum(c["end"] - c["start"] for c in cues if c["value"] != "X")
    print(f"ok: {a.saida} — {len(cues)} cues, {len(x)/sr:.1f}s "
          f"({falando:.1f}s de fala, {100*falando/(len(x)/sr):.0f}%)")


if __name__ == "__main__":
    main()


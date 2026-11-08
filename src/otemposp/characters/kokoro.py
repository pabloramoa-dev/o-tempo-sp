#!/usr/bin/env python3
"""
gerar_voz_kokoro.py — NARRAÇÃO NEURAL em português BR, 100% local no container,
com o Kokoro (Kokoro-82M, Apache-2.0). Voz natural, muito acima do mbrola.

DESCOBERTA que destrava isto (corrige a lição antiga "sem TTS local"): o modelo
mora no GitHub e, embora a *página* de releases dê 403 no proxy, o **download do
ASSET de release passa** (o setup e este script baixam por ali). O fonetizador é
o espeak-ng (já instalado). Vozes BR do v1.0: pm_alex, pm_santa (masc.), pf_dora (fem.).

Isto NÃO substitui o ElevenLabs para publicação premium (voz + lip sync fino),
mas é uma narração de verdade pra fechar episódio inteiro sem depender de MP3
externo.

Uso:
  python gerar_voz_kokoro.py roteiro.txt --voz pm_alex --out narracao.wav \
         --seg-json segs.json [--gap 0.35] [--speed 1.0]

  roteiro.txt = UMA "batida" de narração por linha (cada linha vira um segmento
  da timeline). O script sintetiza cada linha, junta com um pequeno silêncio, e
  grava:
    - narracao.wav  (mono 44100)
    - segs.json     [{"i":0,"texto":..,"ini":0.0,"fim":8.6}, ...]  -> pra montar
      a timeline.json do montar_episodio.py (ini/fim em segundos).

Modelo (cacheado em $OTEMPOSP_KOKORO_DIR ou ~/.cache/otemposp_kokoro):
  kokoro-v1.0.onnx  +  voices-v1.0.bin
"""
import argparse, json, os, subprocess, sys, wave
import numpy as np

SR = 44100
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
ARQS = {"kokoro-v1.0.onnx": f"{BASE}/kokoro-v1.0.onnx",
        "voices-v1.0.bin":  f"{BASE}/voices-v1.0.bin"}


def cache_dir():
    d = os.environ.get("OTEMPOSP_KOKORO_DIR", os.path.expanduser("~/.cache/otemposp_kokoro"))
    os.makedirs(d, exist_ok=True)
    return d


def garantir_modelo():
    d = cache_dir()
    for nome, url in ARQS.items():
        alvo = os.path.join(d, nome)
        if os.path.exists(alvo) and os.path.getsize(alvo) > 1_000_000:
            continue
        print(f"[kokoro] baixando {nome} ...", file=sys.stderr)
        # -f é essencial: sem ele o curl sai com codigo 0 mesmo num 404 e grava a
        # pagina de erro como se fosse o modelo. Em CI isso viraria um erro
        # confuso do onnxruntime la na frente, em vez de falhar aqui.
        subprocess.run(["curl", "-fsSL", "--retry", "3", "--retry-delay", "2",
                        "-o", alvo, url], check=True)
        if os.path.getsize(alvo) < 1_000_000:
            raise SystemExit(f"[kokoro] download de {nome} veio truncado "
                             f"({os.path.getsize(alvo)} bytes). Abortando.")
    return (os.path.join(d, "kokoro-v1.0.onnx"), os.path.join(d, "voices-v1.0.bin"))


def resample_44100(s, sr):
    if sr == SR:
        return s.astype(np.float32)
    n = int(round(len(s) * SR / sr))
    xp = np.linspace(0, 1, len(s), endpoint=False)
    x = np.linspace(0, 1, n, endpoint=False)
    return np.interp(x, xp, s).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roteiro", help="txt: uma batida de narração por linha")
    ap.add_argument("--voz", default="pm_alex", help="pm_alex | pm_santa | pf_dora")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--gap", type=float, default=0.35, help="silêncio entre batidas (s)")
    ap.add_argument("--out", default="narracao.wav")
    ap.add_argument("--seg-json", default=None, help="grava boundaries p/ a timeline")
    a = ap.parse_args()

    try:
        from kokoro_onnx import Kokoro
    except ImportError:
        sys.exit("kokoro-onnx não instalado. Rode: bash scripts/setup_ambiente.sh "
                 "(ou pip install --break-system-packages kokoro-onnx soundfile)")

    onnx, vozes = garantir_modelo()
    k = Kokoro(onnx, vozes)

    linhas = [l.strip() for l in open(a.roteiro, encoding="utf-8") if l.strip()]
    gap = np.zeros(int(a.gap * SR), dtype=np.float32)
    buf = []
    segs = []
    t = 0.0
    for i, txt in enumerate(linhas):
        s, sr = k.create(txt, voice=a.voz, speed=a.speed, lang="pt-br")
        s = resample_44100(np.asarray(s, dtype=np.float32), sr)
        ini = t
        buf.append(s); buf.append(gap)
        t += (len(s) + len(gap)) / SR
        segs.append({"i": i, "texto": txt, "ini": round(ini, 3), "fim": round(t, 3)})
        print(f"[kokoro] linha {i}: {(len(s)/SR):.2f}s", file=sys.stderr)

    voz = np.concatenate(buf) if buf else np.zeros(1, dtype=np.float32)
    pk = float(np.abs(voz).max()) or 1.0
    voz = voz / pk * 0.97
    with wave.open(a.out, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(voz, -1, 1) * 32767).astype(np.int16).tobytes())
    if a.seg_json:
        json.dump(segs, open(a.seg_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"ok: {a.out} ({t:.1f}s, {len(linhas)} batidas, voz={a.voz})", file=sys.stderr)


if __name__ == "__main__":
    main()



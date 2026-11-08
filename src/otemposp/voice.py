"""Locução Kokoro (compatibilidade conceitual com o Previsão RJ).
Instalar requirements-voice.txt nos jobs de render; falha explícita sem voz.
"""
from __future__ import annotations
from pathlib import Path


def generate(text: str, dest: str | Path, voice: str = 'pm_alex', speed: float = 0.94) -> Path:
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
    except ImportError as e:
        raise RuntimeError('Locução Kokoro indisponível. Instale requirements-voice.txt; vídeo não pode ser publicado sem voz.') from e
    pipeline = KPipeline(lang_code='p')  # Português brasileiro (configuração a validar no runner)
    segments = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        if audio is not None:
            segments.append(np.asarray(audio, dtype='float32'))
    if not segments:
        raise RuntimeError('Kokoro não gerou áudio; não usar vídeo mudo na produção')
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.concatenate(segments), 24000)
    return path

"""Renderizador piloto CPU, 9:16, sem distribuir fontes comerciais.
Personagem vetorial animado e 8 cartões simultâneos (texto fica sob a área segura).
A fala é áudio Kokoro real; o movimento labial aqui é estilizado, não fonético.
"""
from __future__ import annotations
from pathlib import Path
import math
import subprocess
import wave
from PIL import Image, ImageDraw, ImageFont

W, H = 540, 960  # renderiza leve no CPU; saída final 1080x1920
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except OSError:
        return ImageFont.load_default()


def draw_reporter(d, t):
    """Repórter estilizado O Tempo SP — separado do elenco RJ."""
    # tronco, pescoço, cabelo, rosto, olhos, boca e mão com animação simples
    d.rounded_rectangle((318, 300, 494, 530), radius=43, fill='#195C78')
    d.rounded_rectangle((390, 279, 424, 345), radius=12, fill='#BD805C')
    d.ellipse((333, 171, 479, 325), fill='#27354B')
    d.rounded_rectangle((344, 195, 465, 324), radius=45, fill='#D79D72')
    d.ellipse((365, 250, 377, 260), fill='#112A40')
    d.ellipse((429, 250, 441, 260), fill='#112A40')
    mouth_open = abs(math.sin(t * 10)) > 0.52
    d.ellipse((390, 292, 417, 307 if mouth_open else 297), fill='#573A37')
    d.line((333, 425, 294 + int(5*math.sin(t*2)), 390), fill='#D79D72', width=18)
    d.rounded_rectangle((373, 356, 434, 378), radius=5, fill='#FFCC4D')
    d.text((380, 359), 'SP', font=font(13), fill='#112A40')


def frame(brief: dict, t: float, demo: bool = False) -> Image.Image:
    im = Image.new('RGB', (W, H), '#E6F4FC')
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 96), fill='#112A40')
    d.text((36, 32), 'O TEMPO SP', font=font(32), fill='white', stroke_width=0)
    d.rounded_rectangle((26, 111, 514, 162), 20, fill='#FFCC4D')
    heading = f'{brief["date"]}  |  {brief["when"].upper()}'
    d.text((42, 121), heading, font=font(21), fill='#112A40')
    d.text((27, 187), 'SÃO PAULO, REGIÃO POR REGIÃO', font=font(17), fill='#123C58')
    d.rounded_rectangle((26, 227, 514, 530), 30, fill='#D0E9F6')
    d.ellipse((54, 279, 164, 389), fill='#FFCC4D')
    d.ellipse((124, 292, 220, 356), fill='white')
    d.ellipse((175, 270, 268, 355), fill='white')
    draw_reporter(d, t)
    d.text((49, 412), 'REPÓRTER SP', font=font(22), fill='#112A40')
    d.text((49, 444), 'Previsão por ponto', font=font(14), fill='#112A40')
    d.text((49, 468), 'sem inventar alertas', font=font(14), fill='#112A40')
    for idx, card in enumerate(brief['cards']):
        col, row = idx % 2, idx // 2
        x, y = (27 + col * 248), 537 + row * 58
        d.rounded_rectangle((x, y, x + 240, y + 55), 11, fill='#FFFFFF', outline='#B4CFE0', width=2)
        d.text((x + 10, y + 8), card['short'], font=font(16), fill='#112A40')
        d.text((x + 10, y + 30), f'{card["min_c"]:g}°-{card["max_c"]:g}°', font=font(17), fill='#1D789F')
        d.text((x + 127, y + 32), f'{card["rain_pct"]:g}% chuva', font=font(11), fill='#425A69')
    if demo:
        d.rounded_rectangle((20, 865, 520, 917), 12, fill='#F05A5A')
        d.text((33, 877), 'TESTE — DADOS FICTÍCIOS — NÃO PUBLICAR', font=font(17), fill='white')
    return im


def audio_length(path):
    with wave.open(str(path), 'rb') as f:
        return f.getnframes() / f.getframerate()


def render(brief: dict, outfile: str | Path, audio: str | Path | None = None,
           demo: bool = False, fps: int = 12) -> Path:
    if not audio and not demo:
        raise ValueError('Vídeo de produção exige locução; use --demo apenas com fixture')
    duration = min(max(audio_length(audio) if audio else 7.0, 5), 90)
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
           '-vcodec', 'rawvideo', '-s', f'{W}x{H}', '-pix_fmt', 'rgb24',
           '-r', str(fps), '-i', '-', '-i', str(audio)] if audio else [
           'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
           '-vcodec', 'rawvideo', '-s', f'{W}x{H}', '-pix_fmt', 'rgb24',
           '-r', str(fps), '-i', '-']
    cmd += ['-vf', 'scale=1080:1920:flags=bicubic', '-c:v', 'libx264',
            '-preset', 'ultrafast', '-crf', '27', '-pix_fmt', 'yuv420p']
    if audio:
        cmd += ['-c:a', 'aac', '-b:a', '128k', '-shortest']
    cmd += ['-t', str(duration), '-movflags', '+faststart', str(outfile)]
    out = Path(outfile)
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(math.ceil(duration * fps)):
            proc.stdin.write(frame(brief, i/fps, demo=demo).tobytes())
    except BrokenPipeError as e:
        raise RuntimeError('FFmpeg interrompeu a renderização') from e
    finally:
        if proc.stdin: proc.stdin.close()
    err = proc.stderr.read().decode('utf-8', errors='replace')
    if proc.wait() != 0:
        raise RuntimeError('FFmpeg: ' + err[-2500:])
    return out

import json
import re
import subprocess
import sys
from pathlib import Path
from src.otemposp.editorial import summarise

def produce(snapshot, when):
    brief=summarise(json.loads(Path(snapshot).read_text()),when)
    out=Path("output")
    out.mkdir(exist_ok=True)
    (out/"brief.json").write_text(json.dumps(brief,ensure_ascii=False))
    (out/"caption.txt").write_text(brief["caption"])
    (out/"speech.txt").write_text(re.sub(r'(?<=[.!?]) +','\n',brief["script"]))
    voice,speed,gap=("pm_alex","1.04","0.22") if when=="hoje" else ("pf_dora","1.02","0.24")
    subprocess.run([sys.executable,"-m","src.otemposp.characters.kokoro",str(out/"speech.txt"),"--voz",voice,"--speed",speed,"--gap",gap,"--out","output/voice.wav","--seg-json","output/segments.json"],check=True)
    subprocess.run([sys.executable,"-m","manim","-r","1080,1920","--fps","24","--disable_caching","scripts/boletim.py","Boletim"],check=True)
    import shutil
    [result]=Path("media/videos/boletim").glob("*/Boletim.mp4")
    shutil.copyfile(result,out/("bira.mp4" if when=="hoje" else "bia.mp4"))

if __name__=="__main__":
    produce(*sys.argv[1:])

from __future__ import annotations
import argparse
import json
from pathlib import Path
from .geo import validate
from .weather import collect
from .editorial import summarise
from .render import render
from .voice import generate
from .publish import publish


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    return p


def main():
    p = argparse.ArgumentParser(description='O Tempo SP — @otemposp')
    sub = p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('validate')
    c = sub.add_parser('collect')
    c.add_argument('--tier',type=int,default=1,choices=[1,2])
    c.add_argument('--day-offset',type=int,default=0,choices=[0,1])
    c.add_argument('--out',default='output/snapshot.json')
    e = sub.add_parser('editorial')
    e.add_argument('snapshot')
    e.add_argument('--when',default='hoje', choices=['hoje','amanhã'])
    e.add_argument('--out',default='output/brief.json')
    v = sub.add_parser('render')
    v.add_argument('brief')
    v.add_argument('--out',default='output/reel.mp4')
    v.add_argument('--demo',action='store_true')
    v.add_argument('--audio',default='output/voice.wav')
    pub = sub.add_parser('publish')
    pub.add_argument('snapshot')
    pub.add_argument('brief')
    pub.add_argument('--video-url',required=True)
    args = p.parse_args()
    if args.cmd == 'validate':
        validate();print('OK: @otemposp, 8 setores, 32 subprefeituras')
    elif args.cmd == 'collect':
        validate();result=collect(tier=args.tier,day_offset=args.day_offset)
        print(write(args.out,result));print('Pontos:',len(result['points']),result['forecast_date'])
    elif args.cmd == 'editorial':
        result=summarise(load(args.snapshot),args.when)
        print(write(args.out,result));print(result['script'])
        Path(args.out).with_suffix('.txt').write_text(result['caption'],encoding='utf-8')
    elif args.cmd == 'render':
        brief=load(args.brief)
        if args.demo:
            if not brief.get('is_fixture'):
                raise SystemExit('--demo somente para briefing fictício')
            audio=None
        else:
            if brief.get('is_fixture'):
                raise SystemExit('Dado fictício não pode gerar vídeo de publicação')
            audio=generate(brief['script'],args.audio)
        print(render(brief,args.out,audio=audio,demo=args.demo))
    elif args.cmd == 'publish':
        print('Publicado media_id:',publish(load(args.snapshot),load(args.brief),args.video_url))

if __name__ == '__main__':main()

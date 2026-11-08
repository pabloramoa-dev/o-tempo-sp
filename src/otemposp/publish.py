"""Publicação de Reels via API da Meta; travas explícitas.
O vídeo precisa estar hospedado em HTTPS numa URL pública, além de ter áudio real.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import time
import requests

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT/'data/published.json'


def guard(snapshot: dict, brief: dict, video_url: str):
    required = ('PUBLISH_ENABLED', 'COMMERCIAL_DATA_LICENSE_OK')
    for key in required:
        if os.environ.get(key, '').lower() != 'true':
            raise RuntimeError(f'Publicação BLOQUEADA: definir {key}=true após validação')
    if snapshot.get('is_fixture') or brief.get('is_fixture'):
        raise RuntimeError('Dado fictício jamais pode ser publicado')
    if snapshot.get('source_url') == 'https://open-meteo.com/':
        if not snapshot.get('api_endpoint', '').startswith('https://customer-api.open-meteo.com/'):
            raise RuntimeError('Fonte Open-Meteo gratuita não autoriza publicação comercial; configurar API licenciada')
    if not video_url.startswith('https://'):
        raise RuntimeError('Vídeo precisa estar hospedado em URL HTTPS pública')
    pts = snapshot.get('points', [])
    if len({p['sector'] for p in pts}) != 8:
        raise RuntimeError('Exigidas oito regiões com dados válidos')
    try:
        fetched = datetime.fromisoformat(snapshot['fetched_at'].replace('Z','+00:00'))
    except (KeyError, ValueError) as e:
        raise RuntimeError('Horário da coleta não verificável') from e
    age = datetime.now(timezone.utc) - fetched.astimezone(timezone.utc)
    if not timedelta(minutes=-5) <= age <= timedelta(minutes=120):
        raise RuntimeError(f'Dados meteorológicos vencidos ou no futuro: {age}')
    today = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    target = today if brief['when'] == 'hoje' else today + timedelta(days=1)
    if brief['date'] != target.isoformat():
        raise RuntimeError(f'Data da previsão não corresponde ao turno: {brief["date"]} != {target}')
    key = f'{brief["date"]}:{brief["when"]}'
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    if key in state:
        raise RuntimeError('Reel já publicado neste turno; duplicação bloqueada')
    return key, state


def publish(snapshot: dict, brief: dict, video_url: str) -> str:
    key, state = guard(snapshot, brief, video_url)
    user = os.getenv('IG_USER_ID')
    token = os.getenv('IG_ACCESS_TOKEN')
    if not user or not token:
        raise RuntimeError('IG_USER_ID e IG_ACCESS_TOKEN não configurados')
    version = os.getenv('META_GRAPH_VERSION', 'v26.0')
    base = f'https://graph.instagram.com/{version}'
    session = requests.Session()
    info = session.get(f'{base}/{user}', params={'fields':'id,username','access_token':token},timeout=30)
    info.raise_for_status()
    if (info.json().get('username') or '').casefold() != 'otemposp':
        raise RuntimeError('Destino Instagram diferente de @otemposp; publicação cancelada')
    # Reconsulta da mídia recente evita repetição mesmo se o estado local perder-se.
    previous = session.get(f'{base}/{user}/media', params={'fields':'id,caption', 'limit':25,
                 'access_token':token},timeout=30)
    previous.raise_for_status()
    if any(' '.join(m.get('caption','').split()) == ' '.join(brief['caption'].split())
           for m in previous.json().get('data', [])):
        raise RuntimeError('Legenda idêntica já publicada no Instagram')
    create = session.post(f'{base}/{user}/media', data={
        'media_type':'REELS','video_url':video_url,'caption':brief['caption'],
        'share_to_feed':'true','access_token':token},timeout=30)
    create.raise_for_status()
    cid = create.json()['id']
    for _ in range(30):
        status = session.get(f'{base}/{cid}', params={'fields':'status_code','access_token':token},timeout=30)
        status.raise_for_status()
        current = status.json().get('status_code')
        if current == 'FINISHED': break
        if current in {'ERROR','EXPIRED'}: raise RuntimeError(f'Erro na mídia Meta: {current}')
        time.sleep(10)
    else:
        raise TimeoutError('A Meta não concluiu o processamento do Reel')
    sent = session.post(f'{base}/{user}/media_publish', data={'creation_id':cid,'access_token':token},timeout=30)
    sent.raise_for_status()
    media_id = sent.json()['id']
    state[key] = {'media_id':media_id,'caption_hash':sha256(brief['caption'].encode()).hexdigest(),
                  'published_at':datetime.now(timezone.utc).isoformat()}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding='utf-8')
    return media_id

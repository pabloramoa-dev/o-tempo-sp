"""Resgate de publicação: escolhe o turno pendente, dispara e CONFERE o resultado.

Antes, o resgate só pedia um `gh workflow run` e terminava verde, sem saber se
o Reel saiu. Agora:

1. decide o turno pela hora de Brasília (America/Sao_Paulo), dentro de janelas
   seguras — nunca publica previsão vencida;
2. lê data/editorial_queue.json da ponta da main: se o turno de hoje já tem
   `media_id`, encerra sem falar com a Meta (a trava do Reel continua valendo);
3. limita as tentativas de resgate por turno e por dia;
4. dispara o workflow do turno, acompanha a execução até o fim e relê a fila;
5. só termina com sucesso se houver `media_id` novo do turno; senão, ::error.

Uso no Actions: python -m scripts.resgate_publicacao [--evento schedule --cron "40 12 * * *"]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, time as hora
from pathlib import Path
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
FILA = Path("data/editorial_queue.json")
WORKFLOW = {"manha": "reel_manha.yml", "noite": "reel_noite.yml"}
# Janelas seguras (hora local), por canal via JANELA_MANHA / JANELA_NOITE
# ("HH:MM-HH:MM"). Padrão do PR (prazos 14:00 e 23:00).
def _janela(env: str, padrao: str) -> tuple[hora, hora]:
    ini, fim = os.environ.get(env, padrao).split("-")
    return (hora(*map(int, ini.split(":"))), hora(*map(int, fim.split(":"))))


JANELA = {"manha": _janela("JANELA_MANHA", "06:00-13:30"),
          "noite": _janela("JANELA_NOITE", "17:50-22:45")}
MAX_TENTATIVAS = 2


def turno_do_cron(cron: str) -> str | None:
    """Turno pelo horário UTC do cron: 09-17 UTC = manhã; 20-23/00-01 UTC = noite."""
    try:
        h = int(cron.split()[1])
    except (IndexError, ValueError):
        return None
    if 9 <= h <= 17:
        return "manha"
    if h >= 20 or h <= 1:
        return "noite"
    return None


def turno_do_item(item: dict) -> str:
    """Mesmo critério da trava 'Já saiu Reel hoje?' dos workflows."""
    if item.get("turno") in ("manha", "noite"):
        return item["turno"]
    return "noite" if item.get("format") == "amanha_no_estado" else "manha"


def publicado(itens: list[dict], turno: str, dia: str) -> dict | None:
    for item in reversed(itens):
        if (item.get("status") == "published" and item.get("media_id")
                and str(item.get("published_at", ""))[:10] == dia
                and turno_do_item(item) == turno):
            return item
    return None


def escolher_turno(agora: datetime, evento: str = "", cron: str = "") -> tuple[str | None, str]:
    """Turno a resgatar e o motivo. O cron que disparou define o turno; a hora
    real precisa estar dentro da janela (cron atrasado não vira outro turno)."""
    agora = agora.astimezone(FUSO)
    if evento == "schedule":
        turno = turno_do_cron(cron)
        if turno is None:
            return None, f"cron de resgate desconhecido: {cron!r}"
        ini, fim = JANELA[turno]
        if not ini <= agora.time() <= fim:
            return None, (f"cron do turno {turno} entregue às {agora:%H:%M}, fora da janela "
                          f"{ini:%H:%M}-{fim:%H:%M}: nada publicado (previsão vencida)")
        return turno, f"cron {cron} → turno {turno}"
    for turno, (ini, fim) in JANELA.items():
        if ini <= agora.time() <= fim:
            return turno, f"{agora:%H:%M} dentro da janela do turno {turno}"
    return None, f"{agora:%H:%M} fora das janelas seguras: nada publicado"


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def _ler_remoto(repo: str, caminho: str):
    """JSON da ponta da main, ou None se o arquivo não existe."""
    try:
        bruto = _gh("api", f"repos/{repo}/contents/{caminho}?ref=main",
                    "-H", "Accept: application/vnd.github.raw")
    except subprocess.CalledProcessError:
        return None
    return json.loads(bruto)


def fila_remota(repo: str) -> list[dict]:
    """Fila da ponta da main (a execução do Reel persiste nela)."""
    return _ler_remoto(repo, FILA.as_posix()) or []


# ---- Adaptadores: cada canal registra a publicação de um jeito -------------
# ADAPTADOR=fila (padrão): data/editorial_queue.json
# ADAPTADOR=turnos_por_data: data/publicacoes.json {"AAAA-MM-DD:turno": {status, media_id}}
# ADAPTADOR=registro_formatos: data/registro_formatos.json [{quando, media_id, publicado_em_utc}]
# ADAPTADOR=arquivo_por_edicao: data/instagram/<data da previsão>-<hoje|amanhã>-REELS.json

def _publicado_turnos_por_data(registro, turno, dia):
    item = (registro or {}).get(f"{dia}:{turno}") or {}
    return item if item.get("status") == "publicado" and item.get("media_id") else None


def _publicado_registro_formatos(registro, turno, dia):
    quando = "hoje" if turno == "manha" else "amanhã"
    for item in reversed(registro or []):
        em = item.get("publicado_em_utc")
        if not (item.get("media_id") and em and item.get("quando") == quando):
            continue
        if datetime.fromisoformat(em.replace("Z", "+00:00")).astimezone(FUSO).date().isoformat() == dia:
            return item
    return None


def _publicado_arquivo_por_edicao(registro, turno, dia):
    item = registro or {}
    return item if item.get("published") and item.get("media_id") else None


def publicado_no_canal(repo: str, turno: str, dia: str) -> dict | None:
    adaptador = os.environ.get("ADAPTADOR", "fila")
    if adaptador == "turnos_por_data":
        return _publicado_turnos_por_data(_ler_remoto(repo, "data/publicacoes.json"), turno, dia)
    if adaptador == "registro_formatos":
        return _publicado_registro_formatos(_ler_remoto(repo, "data/registro_formatos.json"), turno, dia)
    if adaptador == "arquivo_por_edicao":
        from datetime import timedelta
        alvo = date_from(dia) + timedelta(days=0 if turno == "manha" else 1)
        quando = "hoje" if turno == "manha" else "amanhã"
        caminho = urllib_quote(f"data/instagram/{alvo.isoformat()}-{quando}-REELS.json")
        return _publicado_arquivo_por_edicao(_ler_remoto(repo, caminho), turno, dia)
    return publicado(fila_remota(repo), turno, dia)


def date_from(dia: str):
    from datetime import date
    return date.fromisoformat(dia)


def urllib_quote(caminho: str) -> str:
    from urllib.parse import quote
    return quote(caminho)


def workflow_do_turno(turno: str) -> str:
    return os.environ.get("WORKFLOW_MANHA" if turno == "manha" else "WORKFLOW_NOITE") or WORKFLOW[turno]


def campos_extras(turno: str) -> list[str]:
    """Entradas extras do disparo, ex.: DISPATCH_NOITE="turno=amanhã"."""
    bruto = os.environ.get("DISPATCH_MANHA" if turno == "manha" else "DISPATCH_NOITE", "")
    args = []
    for par in filter(None, (x.strip() for x in bruto.split(";"))):
        args += ["-f", par]
    return args


def tentativas_hoje(repo: str, workflow: str, dia: str) -> int:
    saida = _gh("api", f"repos/{repo}/actions/workflows/{workflow}/runs?event=workflow_dispatch&per_page=30",
                "-q", ".workflow_runs[].created_at")
    n = 0
    for linha in saida.split():
        criado = datetime.fromisoformat(linha.replace("Z", "+00:00")).astimezone(FUSO)
        if criado.date().isoformat() == dia:
            n += 1
    return n


def em_andamento(repo: str, workflow: str) -> dict | None:
    for estado in ("in_progress", "queued", "waiting"):
        dados = json.loads(_gh("api", f"repos/{repo}/actions/workflows/{workflow}/runs?status={estado}&per_page=5"))
        if dados.get("workflow_runs"):
            return dados["workflow_runs"][0]
    return None


def acompanhar(repo: str, run: dict, limite_s: int = 70 * 60) -> dict:
    print(f"acompanhando {run['html_url']}")
    prazo = time.monotonic() + limite_s
    while time.monotonic() < prazo:
        r = json.loads(_gh("api", f"repos/{repo}/actions/runs/{run['id']}"))
        if r["status"] == "completed":
            return r
        time.sleep(30)
    raise SystemExit(f"::error::execução {run['html_url']} não terminou em {limite_s // 60} min")


def disparar_e_acompanhar(repo: str, workflow: str, limite_s: int = 70 * 60, extras: list[str] | None = None) -> dict:
    # Já há uma execução do turno rodando: acompanhar essa, nunca abrir outra.
    atual = em_andamento(repo, workflow)
    if atual:
        return acompanhar(repo, atual, limite_s)
    inicio = datetime.now(tz=FUSO)
    _gh("workflow", "run", workflow, "--repo", repo, "--ref", "main", "-f", "publicar=true", *(extras or []))
    run = None
    for _ in range(30):  # até ~5 min para a execução aparecer
        time.sleep(10)
        dados = json.loads(_gh("api", f"repos/{repo}/actions/workflows/{workflow}/runs?event=workflow_dispatch&per_page=5"))
        for r in dados.get("workflow_runs", []):
            if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= inicio.replace(microsecond=0):
                run = r
                break
        if run:
            break
    if not run:
        raise SystemExit("::error::a execução disparada não apareceu no Actions")
    return acompanhar(repo, run, limite_s)


def resumo(texto: str) -> None:
    print(texto)
    caminho = os.environ.get("GITHUB_STEP_SUMMARY")
    if caminho:
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(texto + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--evento", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    ap.add_argument("--cron", default=os.environ.get("SCHEDULE_CRON", ""))
    a = ap.parse_args(argv)

    agora = datetime.now(tz=FUSO)
    dia = agora.date().isoformat()
    turno, motivo = escolher_turno(agora, a.evento, a.cron)
    if turno is None:
        resumo(f"### Resgate sem ação\n\n{motivo}")
        # Cron entregue fora da janela é falha do agendador: avisa em vermelho.
        return 1 if a.evento == "schedule" else 0

    ja = publicado_no_canal(a.repo, turno, dia)
    if ja:
        resumo(f"### Turno {turno} de {dia} já publicado\n\n- media_id: `{ja['media_id']}`\n- formato: `{ja.get('format')}`")
        return 0

    workflow = workflow_do_turno(turno)
    feitas = tentativas_hoje(a.repo, workflow, dia)
    if feitas >= MAX_TENTATIVAS and not em_andamento(a.repo, workflow):
        resumo(f"### Resgate bloqueado\n\n{feitas} tentativas manuais/resgate de `{workflow}` hoje "
               f"(limite {MAX_TENTATIVAS}). Turno {turno} continua SEM publicação: verificar manualmente.")
        print("::error::limite de tentativas de resgate atingido sem publicação confirmada")
        return 1

    resumo(f"### Resgate do turno {turno} ({motivo})\n\nDisparando `{workflow}` com publicar=true.")
    run = disparar_e_acompanhar(a.repo, workflow, extras=campos_extras(turno))
    novo = publicado_no_canal(a.repo, turno, dia)
    if novo:
        resumo(f"- execução: {run['html_url']} ({run['conclusion']})\n- **media_id confirmado:** `{novo['media_id']}`")
        return 0
    resumo(f"- execução: {run['html_url']} ({run['conclusion']})\n- **sem media_id do turno {turno} na fila**")
    print("::error::resgate terminou sem publicação confirmada pela Meta")
    return 1


if __name__ == "__main__":
    sys.exit(main())

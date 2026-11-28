from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from scripts import resgate_publicacao as R

BRT = ZoneInfo("America/Sao_Paulo")


def em(h, m=0, dia=27):
    return datetime(2026, 11, dia, h, m, tzinfo=BRT)


@pytest.mark.parametrize("agora, cron, turno", [
    (em(9, 41), "40 12 * * *", "manha"),
    (em(10, 45), "40 13 * * *", "manha"),
    (em(18, 12), "10 21 * * *", "noite"),
    (em(19, 15), "10 22 * * *", "noite"),
])
def test_cron_no_horario_define_o_turno(agora, cron, turno):
    assert R.escolher_turno(agora, "schedule", cron)[0] == turno


@pytest.mark.parametrize("agora, cron", [
    (em(21, 6), "40 12 * * *"),   # cron da manhã entregue à noite (run 46086100030)
    (em(23, 30), "10 21 * * *"),  # noite depois do prazo
    (em(3, 9, 28), "10 22 * * *"),  # madrugada seguinte: previsão vencida
])
def test_cron_atrasado_nao_vira_outro_turno_nem_publica_vencido(agora, cron):
    turno, motivo = R.escolher_turno(agora, "schedule", cron)
    assert turno is None and "fora da janela" in motivo


def test_cron_desconhecido():
    assert R.escolher_turno(em(9), "schedule", "1 2 * * *")[0] is None


@pytest.mark.parametrize("agora, turno", [
    (em(5, 59), None), (em(6), "manha"), (em(13, 30), "manha"), (em(13, 31), None),
    (em(17, 50), "noite"), (em(22, 45), "noite"), (em(22, 46), None)])
def test_disparo_externo_ou_manual_usa_janela(agora, turno):
    assert R.escolher_turno(agora, "repository_dispatch")[0] == turno


def test_utc_e_convertido_para_brasilia():
    from datetime import timezone
    utc = datetime(2026, 11, 28, 0, 59, tzinfo=timezone.utc)  # 21:59 BRT de 27/11
    assert R.escolher_turno(utc, "workflow_dispatch")[0] == "noite"


FILA = [
    {"status": "published", "published_at": "2026-11-26T08:49:32-03:00", "format": "chove_onde", "media_id": "1"},
    {"status": "published", "published_at": "2026-11-27T21:59:00-03:00", "format": "amanha_no_estado", "media_id": "2"},
    {"status": "published", "published_at": "2026-11-27T06:00:00-03:00", "format": "antes_de_sair", "media_id": None},
    {"status": "ready", "published_at": "2026-11-27T06:00:00-03:00", "format": "antes_de_sair", "media_id": "3"},
]


def test_publicado_exige_media_id_status_dia_e_turno():
    assert R.publicado(FILA, "noite", "2026-11-27")["media_id"] == "2"
    assert R.publicado(FILA, "manha", "2026-11-27") is None  # sem media_id / não publicado
    assert R.publicado(FILA, "manha", "2026-11-26")["media_id"] == "1"
    assert R.publicado(FILA, "noite", "2026-11-26") is None


def test_ja_publicado_nao_dispara(monkeypatch):
    chamadas = []
    monkeypatch.setattr(R, "fila_remota", lambda repo: FILA)
    monkeypatch.setattr(R, "disparar_e_acompanhar", lambda *a, **k: chamadas.append(a))
    monkeypatch.setattr(R, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: em(21, 59))}))
    assert R.main(["--repo", "x/y", "--evento", "workflow_dispatch"]) == 0
    assert chamadas == []


def test_sem_media_id_depois_do_disparo_fica_vermelho(monkeypatch):
    monkeypatch.setattr(R, "fila_remota", lambda repo: FILA[:1])
    monkeypatch.setattr(R, "tentativas_hoje", lambda *a: 0)
    monkeypatch.setattr(R, "disparar_e_acompanhar", lambda *a, **k: {"html_url": "u", "conclusion": "success"})
    monkeypatch.setattr(R, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: em(19, 15))}))
    assert R.main(["--repo", "x/y", "--evento", "workflow_dispatch"]) == 1


def test_limite_de_tentativas(monkeypatch):
    monkeypatch.setattr(R, "fila_remota", lambda repo: [])
    monkeypatch.setattr(R, "tentativas_hoje", lambda *a: R.MAX_TENTATIVAS)
    monkeypatch.setattr(R, "em_andamento", lambda *a: None)
    monkeypatch.setattr(R, "disparar_e_acompanhar", lambda *a, **k: pytest.fail("não deveria disparar"))
    monkeypatch.setattr(R, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: em(19, 15))}))
    assert R.main(["--repo", "x/y", "--evento", "workflow_dispatch"]) == 1


def test_janela_configuravel_por_canal(monkeypatch):
    import importlib
    monkeypatch.setenv("JANELA_MANHA", "06:00-09:30")
    monkeypatch.setenv("JANELA_NOITE", "17:50-20:30")
    mod = importlib.reload(R)
    try:
        assert mod.escolher_turno(em(9, 20), "repository_dispatch")[0] == "manha"
        assert mod.escolher_turno(em(9, 45), "repository_dispatch")[0] is None
        assert mod.escolher_turno(em(20, 45), "repository_dispatch")[0] is None
        assert mod.escolher_turno(em(10, 41), "schedule", "40 13 * * *")[0] is None  # depois do prazo
    finally:
        monkeypatch.delenv("JANELA_MANHA")
        monkeypatch.delenv("JANELA_NOITE")
        importlib.reload(R)


# ---- adaptadores de outros canais -----------------------------------------

def test_adaptador_turnos_por_data():
    reg = {"2026-11-27:noite": {"status": "publicado", "media_id": "9"},
           "2026-11-27:manha": {"status": "erro", "media_id": None}}
    assert R._publicado_turnos_por_data(reg, "noite", "2026-11-27")["media_id"] == "9"
    assert R._publicado_turnos_por_data(reg, "manha", "2026-11-27") is None
    assert R._publicado_turnos_por_data(None, "manha", "2026-11-27") is None


def test_adaptador_registro_formatos_converte_utc_para_brasilia():
    reg = [{"quando": "amanhã", "media_id": "7", "publicado_em_utc": "2026-11-27T21:01:30+00:00"},
           {"quando": "hoje", "media_id": "6", "publicado_em_utc": "2026-11-28T02:30:00+00:00"}]
    assert R._publicado_registro_formatos(reg, "noite", "2026-11-27")["media_id"] == "7"
    # 02:30 UTC de 28/11 = 23:30 BRT de 27/11: conta para o dia 27.
    assert R._publicado_registro_formatos(reg, "manha", "2026-11-27")["media_id"] == "6"
    assert R._publicado_registro_formatos(reg, "manha", "2026-11-28") is None


def test_adaptador_arquivo_por_edicao_usa_data_da_previsao(monkeypatch):
    lidos = []
    monkeypatch.setenv("ADAPTADOR", "arquivo_por_edicao")
    monkeypatch.setattr(R, "_ler_remoto", lambda repo, c: lidos.append(c) or {"published": True, "media_id": "5"})
    assert R.publicado_no_canal("x/y", "noite", "2026-11-27")["media_id"] == "5"
    assert R.publicado_no_canal("x/y", "manha", "2026-11-27")["media_id"] == "5"
    assert "2026-11-28-amanh%C3%A3-REELS.json" in lidos[0]
    assert lidos[1].endswith("2026-11-27-hoje-REELS.json")


def test_workflow_e_campos_por_canal(monkeypatch):
    monkeypatch.setenv("WORKFLOW_NOITE", "reels.yml")
    monkeypatch.setenv("DISPATCH_NOITE", "turno=amanhã")
    assert R.workflow_do_turno("noite") == "reels.yml"
    assert R.workflow_do_turno("manha") == "reel_manha.yml"
    assert R.campos_extras("noite") == ["-f", "turno=amanhã"]
    assert R.campos_extras("manha") == []

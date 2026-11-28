import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from scripts import atualizar_catalogo_eventos as A

BRT = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 11, 27, 9, 0, tzinfo=BRT)
FDS = (date(2026, 11, 28), date(2026, 11, 29))
TEXTO = ("A Feira do Livro do VI Festival Mário de Andrade acontecerá nos dias 28 e 29 de novembro, "
         "das 10h às 19h, na Praça Dom José Gaspar, Centro.")


def ev(nome="VI Festival Mário de Andrade", local="Praça Dom José Gaspar", inicio="2026-11-28T10:00:00-03:00"):
    return {"name": nome, "venue": local, "sessions": [{"starts_at": inicio, "headline": "Feira"}]}


def test_edicao_e_a_sexta_da_semana():
    assert A.edicao(AGORA) == date(2026, 11, 27)
    assert A.edicao(datetime(2026, 11, 24, 8, tzinfo=BRT)) == date(2026, 11, 27)


def test_evento_conferido_no_texto_da_fonte():
    assert A.verificar(ev(), TEXTO, FDS) == []


@pytest.mark.parametrize("evento, motivo", [
    (ev(nome="Show Inventado da Banda X"), "nome"),
    (ev(local="Allianz Parque"), "local"),
    (ev(inicio="2026-11-28T21:00:00-03:00"), "horário"),
    (ev(inicio="2026-11-21T10:00:00-03:00"), "nenhuma sessão"),
])
def test_o_que_nao_esta_na_fonte_e_rejeitado(evento, motivo):
    assert any(motivo in p for p in A.verificar(evento, TEXTO, FDS))


@pytest.fixture
def catalogo(tmp_path, monkeypatch):
    c = tmp_path / "cat.json"
    c.write_text(json.dumps({"edition": "2026-11-20", "events": [{}, {}]}), encoding="utf-8")
    monkeypatch.setattr(A, "CATALOG", c)
    monkeypatch.setattr(A, "OUT", tmp_path / "out")
    return c


def test_sem_chaves_nao_publica_e_registra_motivo(catalogo, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert A.main(AGORA) == A.SEM_EVENTOS
    assert json.loads((A.OUT / "motivo.json").read_text())["publicar"] is False
    assert json.loads(catalogo.read_text())["edition"] == "2026-11-20"  # antigo intacto


def test_atualiza_com_dois_eventos_verificados(catalogo, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "y")
    texto2 = TEXTO + " No sábado (28), às 17h, Mauricio Gasperini no Palco São Bento, Largo São Bento."
    monkeypatch.setattr(A, "buscar_paginas", lambda s: [{"url": "https://prefeitura.sp.gov.br/a", "texto": texto2}])
    monkeypatch.setattr(A, "extrair", lambda p, s: [
        dict(ev(), source=p["url"], fonte_oficial=True),
        dict(ev("Mauricio Gasperini Palco São Bento", "Largo São Bento", "2026-11-28T17:00:00-03:00"),
             source=p["url"], fonte_oficial=True),
        dict(ev("Evento Alucinado Gigante", "Lugar Nenhum", "2026-11-28T20:00:00-03:00"),
             source=p["url"], fonte_oficial=True)])
    monkeypatch.setattr(A, "geocodificar", lambda local: (-23.545, -46.64))
    assert A.main(AGORA) == 0
    novo = json.loads(catalogo.read_text())
    assert novo["edition"] == "2026-11-27" and len(novo["events"]) == 2
    assert "Alucinado" not in json.dumps(novo)


def test_menos_de_dois_eventos_nao_atualiza(catalogo, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "y")
    monkeypatch.setattr(A, "buscar_paginas", lambda s: [{"url": "u", "texto": TEXTO}])
    monkeypatch.setattr(A, "extrair", lambda p, s: [dict(ev(), source="u")])
    monkeypatch.setattr(A, "geocodificar", lambda local: (-23.545, -46.64))
    assert A.main(AGORA) == A.SEM_EVENTOS
    assert json.loads(catalogo.read_text())["edition"] == "2026-11-20"


def test_catalogo_atual_nao_e_tocado(catalogo, monkeypatch):
    catalogo.write_text(json.dumps({"edition": "2026-11-27", "events": [{}, {}]}))
    assert A.main(AGORA) == 0


def test_so_modelos_gratuitos_com_preco_zero(monkeypatch):
    import io
    dados = {"data": [
        {"id": "x/pago", "pricing": {"prompt": "0.001", "completion": "0.002"}, "context_length": 100000},
        {"id": "x/falso:free", "pricing": {"prompt": "0.1", "completion": "0"}, "context_length": 100000},
        {"id": "x/curto:free", "pricing": {"prompt": "0", "completion": "0"}, "context_length": 4000},
        {"id": "x/gemma-bom:free", "pricing": {"prompt": "0", "completion": "0"}, "context_length": 32000},
        {"id": "x/qwen-bom:free", "pricing": {"prompt": "0", "completion": "0", "request": "0"}, "context_length": 32000}]}
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setattr(A, "_MODELOS", None)
    monkeypatch.setattr(A.urllib.request, "urlopen", lambda req, timeout: io.BytesIO(json.dumps(dados).encode()))
    assert A.modelos_gratuitos() == ["x/qwen-bom:free", "x/gemma-bom:free"]

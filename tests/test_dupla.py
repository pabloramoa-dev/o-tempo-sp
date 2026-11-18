"""Boletim em dupla (Bira + Bia): roteiro, papéis e recursos versionados."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "hyperframes"))

import gerar_dupla as G  # noqa: E402


def _roteiro(when):
    brief = G.brief_ilustrativo(when, "2026-11-18")
    return brief, G.roteiro_dupla(brief)


def test_papeis_por_turno():
    assert G.papeis("hoje") == ("bira", "bia")
    assert G.papeis("amanhã") == ("bia", "bira")


def test_falas_alternadas_e_cta_de_quem_apresenta():
    for when in ("hoje", "amanhã"):
        _, (bat, falante, _, lider, outro) = _roteiro(when)
        assert len(bat) == len(falante)
        assert set(falante) == {"bira", "bia"}
        assert falante[0] == lider                      # abre quem apresenta
        assert falante[1] == outro                      # responde quem acompanha
        assert bat[-2]["tipo"] == "cta" and falante[-2] == lider
        assert falante[-1] == outro                     # despedida
        resumos = [f for b, f in zip(bat, falante) if b["tipo"] == "resumo"]
        assert len(set(resumos)) == 2                   # regiões divididas entre os dois


def test_abertura_sem_anunciar_dupla():
    for when in ("hoje", "amanhã"):
        _, (bat, *_rest) = _roteiro(when)
        assert "dupla" not in bat[0]["fala"].lower()


def test_quadro_mantem_as_onze_localidades():
    brief, (bat, *_rest) = _roteiro("amanhã")
    nomes = [c["nome"] for b in bat if b["tipo"] == "resumo" for c in b["dados"]["cidades"]]
    assert sorted(nomes) == sorted(c["point"] for c in brief["cards"])


def test_recursos_gratuitos_versionados():
    sfx = json.loads((G.DUPLA / "sfx.json").read_text(encoding="utf-8"))
    for som in sfx["sons"].values():
        assert (G.DUPLA / som["arquivo"]).is_file()
    assert G.MUSICA.is_file()
    fig = json.loads((G.DUPLA / "figurantes.json").read_text(encoding="utf-8"))
    assert len(fig["peeps"]) >= 5 and fig["geo"].startswith("data:image/svg")


def test_qa_aceita_dupla_de_producao():
    from src.otemposp.characters import quality_direction as QA
    brief = G.brief_ilustrativo("amanhã", "2026-11-18")
    bat, falante, cidades, lider, outro = G.roteiro_dupla(brief)
    batidas = [dict(b, ini=k * 2.3, fim=k * 2.3 + 2.0) for k, b in enumerate(bat)]
    dur = len(bat) * 2.3
    pacote = {"demo": False, "personagem": lider, "cidades": cidades, "batidas": batidas,
              "direcao": [], "dur": dur,
              "dupla": {"apresenta": lider, "acompanha": outro, "falantes": falante}}
    probe = {"streams": [{"codec_type": "video", "width": 1080, "height": 1920, "avg_frame_rate": "30/1"},
                         {"codec_type": "audio"}], "format": {"duration": str(dur)}}
    erros = QA.verificar(pacote, probe)["erros"]
    assert not [e for e in erros if "gancho" in e or "CTA" in e or "Dupla" in e], erros

"""Presets de Bira/Bia em SP sincronizados com os do Previsão RJ."""
import pytest

from hyperframes.gerar_hf import PRESETS, FILTRO_VOZ
from src.otemposp.characters.kokoro import estilo


class _EstilosFalsos:
    def __init__(self):
        self.valores = {"pm_alex": 1.0, "pm_santa": 2.0,
                        "pf_dora": 3.0, "af_heart": 5.0}

    def get_voice_style(self, nome):
        return self.valores[nome]


def test_presets_bira_e_bia_identicos_aos_do_rj():
    assert PRESETS["bira"] == {
        "voice": "pm_alex:0.82+pm_santa:0.18",
        "pitch": 1.0,
        "speed": 1.04,
        "gap": 0.22,
    }
    assert PRESETS["bia"] == {
        "voice": "pf_dora:0.85+af_heart:0.15",
        "pitch": 1.0,
        "speed": 1.02,
        "gap": 0.24,
    }


def test_combinacao_de_estilos_produz_mistura_ponderada():
    modelo = _EstilosFalsos()
    assert estilo(modelo, PRESETS["bira"]["voice"]) == pytest.approx(1.18)
    assert estilo(modelo, PRESETS["bia"]["voice"]) == pytest.approx(3.3)
    assert estilo(modelo, "pm_alex") == "pm_alex"


def test_tratamento_da_voz_mantido_igual_ao_rj():
    assert FILTRO_VOZ == (
        "highpass=f=80,acompressor=threshold=-18dB:ratio=2:"
        "attack=8:release=180,volume=1.1"
    )

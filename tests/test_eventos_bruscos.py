"""Testes sem rede, garantindo que o detector não inventa alertas."""
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.eventos_bruscos import detectar_eventos

TZ = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 11, 18, 14, tzinfo=TZ)

def serie(chuva=None, rajada=None, codigo=None, temps=None):
    linhas = []
    for i in range(8):
        linhas.append({"time": (AGORA + timedelta(hours=i)).isoformat(),
                       "precipitation_mm": (chuva or [0]*8)[i],
                       "wind_gust_kmh": (rajada or [10]*8)[i],
                       "weather_code": (codigo or [1]*8)[i],
                       "temperature_c": (temps or [25]*8)[i]})
    return [{"nome": "Cidade Teste", "hourly": linhas}]

class EventosTest(unittest.TestCase):
    def tipos(self, data, **kwargs):
        return {v["tipo"] for v in detectar_eventos(data, AGORA, **kwargs)}
    def test_chuva_com_horario(self):
        e = detectar_eventos(serie(chuva=[0, 12, 10, 12, 0, 0, 0, 0]), AGORA)
        self.assertTrue(any(v["tipo"] == "chuva_intensa" and v["inicio"].endswith("15:00:00-03:00") for v in e))
    def test_sem_alerta_com_dado_ausente(self):
        self.assertEqual([], detectar_eventos([{"nome":"Cidade Teste", "hourly": []}], AGORA))
    def test_sem_inventar_granizo(self):
        self.assertNotIn("granizo", self.tipos(serie(chuva=[30]*8)))
        self.assertIn("granizo", self.tipos(serie(codigo=[1,96,1,1,1,1,1,1])))
    def test_rajada_nao_e_vento_medio(self):
        self.assertNotIn("vento", self.tipos(serie()))
        self.assertIn("vento", self.tipos(serie(rajada=[55]+[10]*7)))
    def test_variacao_temperatura(self):
        self.assertIn("virada_temperatura", self.tipos(serie(temps=[30,30,30,30,30,30,22,22])))
    def test_aviso_nao_verificado_rejeitado(self):
        aviso = {"tipo":"granizo","local":"Teste","fonte":"INMET","verificado":False,
                 "inicio":AGORA.isoformat(),"fim":(AGORA+timedelta(hours=3)).isoformat()}
        self.assertEqual([], detectar_eventos([], AGORA, [aviso]))
if __name__ == "__main__":
    unittest.main()

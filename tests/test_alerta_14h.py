"""Testes da trava do monitor: risco real exige evidência, relógio e unidades."""
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from tools.alerta_14h import CONFIG, sinais, validar, por_hora

TZ=ZoneInfo("America/Sao_Paulo")

class Alertas14h(unittest.TestCase):
    def test_cobertura_regional(self):
        self.assertEqual(len(CONFIG["cidades"]),10)
        self.assertEqual(len({r[0] for r in CONFIG["cidades"]}),10)

    def test_chuva_e_rajadas(self):
        t=datetime(2026,11,20,15,tzinfo=TZ)
        linhas={t+timedelta(hours=i):{"precipitation":12 if i<3 else 0,
             "wind_gusts_10m":65 if i==0 else 10,
             "weather_code":3,"temperature_2m":26} for i in range(24)}
        eventos=sinais(linhas)
        self.assertTrue(any(e["tipo"]=="vento" for e in eventos))
        self.assertTrue(any(e["tipo"]=="chuva" and e["unidade"]=="mm em 3h" for e in eventos))
        self.assertFalse(any(e["tipo"]=="granizo" for e in eventos))

    def test_granizo_codigo_explicito(self):
        t=datetime(2026,11,20,15,tzinfo=TZ)
        base={"precipitation":0,"wind_gusts_10m":10,"weather_code":95,"temperature_2m":26}
        self.assertFalse(any(e["tipo"]=="granizo" for e in sinais({t:base})))
        self.assertTrue(any(e["tipo"]=="granizo" for e in sinais({t:dict(base,weather_code=96)})))

    def test_acumulado_24h_somente_com_janela_completa(self):
        t=datetime(2026,11,20,15,tzinfo=TZ)
        linhas={t+timedelta(hours=i):{"precipitation":3,"wind_gusts_10m":8,
            "weather_code":3,"temperature_2m":24} for i in range(24)}
        self.assertTrue(any(e["unidade"]=="mm em 24h" for e in sinais(linhas)))

    def test_previsao_incompleta_bloqueia(self):
        agora=datetime(2026,11,20,14,tzinfo=TZ)
        p={"hourly":{"time":[],"precipitation":[],"wind_gusts_10m":[],
                       "weather_code":[],"temperature_2m":[]},
           "hourly_units":{"precipitation":"mm","wind_gusts_10m":"km/h"}}
        with self.assertRaises(ValueError):por_hora(p,agora)

    def test_relatorio_vencido_bloqueia(self):
        agora=datetime(2026,11,20,18,tzinfo=TZ)
        r={"emitido_em":(agora-timedelta(hours=3)).isoformat(),"publicar":True,
           "oficiais":{"completa":True},
           "eventos":[{"fim":(agora+timedelta(hours=1)).isoformat()}]}
        with self.assertRaises(ValueError):validar(r,agora)

    def test_sem_risco_bloqueia(self):
        agora=datetime(2026,11,20,18,tzinfo=TZ)
        r={"emitido_em":agora.isoformat(),"publicar":False,
           "oficiais":{"completa":True},"eventos":[]}
        with self.assertRaises(ValueError):validar(r,agora)

if __name__=="__main__": unittest.main()

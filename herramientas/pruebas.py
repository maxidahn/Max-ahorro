#!/usr/bin/env python3
"""Tests de las herramientas. Correr: python3 herramientas/pruebas.py"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cartera  # noqa: E402
import plan  # noqa: E402
import registrar  # noqa: E402
import resumen  # noqa: E402
from comun import Cambio, ErrorDatos, a_numero, cuentas_por_id, leer_json  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLO = RAIZ / "datos" / "ejemplo"
HOY = date(2026, 8, 30)


class TestConversiones(unittest.TestCase):
    def test_numeros_en_formato_argentino(self):
        self.assertEqual(a_numero("1.234,56"), 1234.56)
        self.assertEqual(a_numero("1234.56"), 1234.56)
        self.assertEqual(a_numero("4.200"), 4200.0)
        self.assertEqual(a_numero("$ 300"), 300.0)
        self.assertEqual(a_numero("1.234.567"), 1234567.0)
        self.assertEqual(a_numero("0,5"), 0.5)
        self.assertEqual(a_numero("0.035"), 0.035)
        self.assertEqual(a_numero("-120,50"), -120.5)

    def test_monto_vacio_falla(self):
        with self.assertRaises(ErrorDatos):
            a_numero("")

    def test_cambio_a_base(self):
        c = Cambio({"moneda_base": "USD", "tipo_cambio": {"USD": 1, "ARS": 1450}})
        self.assertAlmostEqual(c.a_base(145000, "ARS"), 100.0)
        self.assertAlmostEqual(c.a_base(50, "USD"), 50.0)

    def test_moneda_desconocida_se_reporta(self):
        c = Cambio({"moneda_base": "USD", "tipo_cambio": {"USD": 1}})
        self.assertEqual(c.a_base(100, "EUR"), 0.0)
        self.assertIn("EUR", c.faltantes)


class TestResumen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = resumen.calcular(EJEMPLO, 6, HOY)

    def test_patrimonio_suma_las_posiciones(self):
        self.assertAlmostEqual(
            self.r["patrimonio"], sum(p["monto_base"] for p in self.r["posiciones"]), places=2
        )
        self.assertGreater(self.r["patrimonio"], 0)

    def test_excluye_el_mes_en_curso_del_promedio(self):
        self.assertNotIn("2026-08", self.r["meses_analizados"])
        self.assertIn("2026-07", self.r["meses_analizados"])

    def test_tasa_de_ahorro(self):
        esperada = self.r["excedente_mensual"] / self.r["ingreso_mensual_promedio"]
        self.assertAlmostEqual(self.r["tasa_ahorro"], esperada)
        self.assertTrue(0 < self.r["tasa_ahorro"] < 1)

    def test_liquido_excluye_riesgo_alto(self):
        arq = next(p for p in self.r["posiciones"] if p["cuenta_id"] == "arq")
        self.assertGreater(arq["monto_base"], 0)
        self.assertLess(self.r["liquido_bajo_riesgo"], self.r["patrimonio"] - arq["monto_base"] + 1)

    def test_pesos_convertidos_a_base(self):
        pesos = next(p for p in self.r["posiciones"] if p["cuenta_id"] == "pesos")
        self.assertLess(pesos["monto_base"], 2000)  # ~993k ARS a 1450

    def test_ejemplo_no_tiene_datos_faltantes(self):
        self.assertEqual(self.r["pendientes"], [])


class TestPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = resumen.calcular(EJEMPLO, 6, HOY)
        cls.perfil = leer_json("perfil", EJEMPLO)
        cls.cuentas = cuentas_por_id(leer_json("cuentas", EJEMPLO))
        cls.metas = leer_json("metas", EJEMPLO)
        cls.cambio = Cambio(cls.perfil)
        cls.ops = plan.oportunidades(cls.r, cls.perfil, cls.cuentas, cls.cambio)
        cls.pasos = plan.cascada(cls.r, cls.perfil, cls.cuentas, cls.cambio, cls.metas)

    def claves(self):
        return {o["clave"] for o in self.ops}

    def test_detecta_efectivo_ocioso(self):
        self.assertIn("efectivo_ocioso", self.claves())

    def test_detecta_deuda_cara(self):
        self.assertIn("deuda_cara", self.claves())

    def test_detecta_excedente_sin_colocar(self):
        self.assertIn("excedente_sin_colocar", self.claves())

    def test_no_marca_tasa_de_ahorro_si_supera_la_meta(self):
        self.assertGreater(self.r["tasa_ahorro"], self.perfil["meta_tasa_ahorro"])
        self.assertNotIn("tasa_ahorro", self.claves())

    def test_ordenadas_por_prioridad(self):
        prioridades = [o["prioridad"] for o in self.ops]
        self.assertEqual(prioridades, sorted(prioridades))

    def test_la_cascada_no_reparte_mas_que_el_excedente(self):
        total = sum(p["monto_mensual"] for p in self.pasos)
        self.assertLessEqual(total, self.r["excedente_mensual"] + 0.01)

    def test_la_deuda_cara_va_primero(self):
        self.assertEqual(self.pasos[0]["paso"], "Cancelar deuda cara")

    def test_proyeccion_compone(self):
        sin_aporte = plan.proyectar(1000, 0, 0.12, 12)
        self.assertGreater(sin_aporte, 1120)  # 12% nominal compuesto mensual
        self.assertGreater(plan.proyectar(1000, 100, 0.05, 12), 2200)

    def test_sin_excedente_no_hay_plan(self):
        r = dict(self.r, excedente_mensual=-50.0)
        self.assertEqual(plan.cascada(r, self.perfil, self.cuentas, self.cambio, self.metas), [])


class TestRegistrar(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.datos = self.tmp / "datos"
        shutil.copytree(EJEMPLO, self.datos)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def correr(self, *args):
        return registrar.main(["--datos", str(self.datos), *args])

    def test_registra_saldo_y_lo_toma_el_resumen(self):
        antes = resumen.calcular(self.datos, 6, HOY)["patrimonio"]
        self.assertEqual(self.correr("saldo", "--cuenta", "ontop", "--monto", "9000"), 0)
        despues = resumen.calcular(self.datos, 6, HOY)["patrimonio"]
        self.assertGreater(despues, antes)

    def test_rechaza_cuenta_inexistente(self):
        self.assertEqual(self.correr("saldo", "--cuenta", "fantasma", "--monto", "10"), 1)

    def test_alta_de_cuenta_con_tasa_queda_verificada(self):
        self.assertEqual(
            self.correr(
                "cuenta", "--id", "nueva", "--nombre", "Nueva", "--moneda", "USD",
                "--tasa", "0.04", "--riesgo", "1", "--liquidez", "0",
                "--proposito", "liquidez", "--fuente", "prueba",
            ),
            0,
        )
        cta = cuentas_por_id(json.loads((self.datos / "cuentas.json").read_text()))["nueva"]
        self.assertEqual(cta["tasa_anual_estimada"], 0.04)
        self.assertTrue(cta["verificado"])

    def test_gasto_en_pesos_se_convierte(self):
        antes = resumen.calcular(self.datos, 6, HOY)["gasto_por_categoria"]["salidas"]
        self.assertEqual(
            self.correr("gasto", "--categoria", "salidas", "--monto", "145.000", "--moneda", "ARS"),
            0,
        )
        despues = resumen.calcular(self.datos, 6, HOY)["gasto_por_categoria"]["salidas"]
        self.assertAlmostEqual(despues - antes, 100.0, places=2)  # 145.000 ARS a 1450


class TestCartera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = cartera.analizar(RAIZ / "datos")

    def test_los_pesos_suman_uno(self):
        self.assertAlmostEqual(sum(p["peso"] for p in self.a["posiciones"]), 1.0, places=6)

    def test_las_posiciones_cuadran_con_el_total_declarado(self):
        self.assertAlmostEqual(sum(p["valor"] for p in self.a["posiciones"]), self.a["total"], 2)

    def test_calcula_el_resultado_implicito_de_lo_no_cargado(self):
        # La app declara +997,42 y lo cargado suma más: la diferencia es de las posiciones que faltan.
        self.assertIsNotNone(self.a["pl_implicito_no_cargado"])
        self.assertAlmostEqual(
            self.a["pl_total"] + self.a["pl_implicito_no_cargado"], self.a["pl_declarado"], 2
        )

    def test_el_nucleo_esta_exento_del_techo_por_posicion(self):
        textos = " ".join(al["texto"] for al in self.a["alertas"])
        self.assertNotIn("SPY pesa", textos)
        self.assertIn("GOOGL", textos)

    def test_marca_las_posiciones_por_debajo_del_minimo(self):
        chicas = {
            al["texto"].split()[0]
            for al in self.a["alertas"]
            if al["regla"] == "min_por_posicion_pct"
        }
        self.assertIn("SLV", chicas)
        self.assertNotIn("GOOGL", chicas)

    def test_bloquea_mientras_falten_datos(self):
        bloqueantes = {al["regla"] for al in self.a["alertas"] if al["nivel"] == "bloqueante"}
        self.assertIn("costos", bloqueantes)      # falta la comisión
        self.assertIn("politica", bloqueantes)    # objetivo.json sin confirmar
        self.assertIn("datos", bloqueantes)       # posiciones sin identificar

    def test_el_aporte_se_reparte_entero_entre_las_clases_flojas(self):
        ordenes = cartera.ordenes_de_aporte(self.a, 1000)
        self.assertAlmostEqual(sum(o["importe"] for o in ordenes), 1000, places=2)
        self.assertEqual(ordenes[0]["clase"], "nucleo")  # es la clase más por debajo

    def test_el_aporte_avisa_de_ordenes_muy_chicas(self):
        ordenes = cartera.ordenes_de_aporte(self.a, 1000)
        chicas = [o for o in ordenes if o["importe"] < 250]
        self.assertTrue(chicas)
        self.assertTrue(all(o["problemas"] for o in chicas))

    def test_una_compra_grande_rompe_el_techo_de_accion(self):
        ev = cartera.evaluar_orden(self.a, "compra", "MU", 3000, "accion")
        self.assertEqual(ev["veredicto"], "revisar")
        self.assertTrue(any("techo" in p for p in ev["problemas"]))

    def test_una_compra_chica_queda_bajo_el_minimo(self):
        ev = cartera.evaluar_orden(self.a, "compra", "NVDA", 200, "accion")
        self.assertTrue(any("mínimo" in p for p in ev["problemas"]))

    def test_no_se_puede_vender_mas_de_lo_que_hay(self):
        ev = cartera.evaluar_orden(self.a, "venta", "SLV", 5000, None)
        self.assertTrue(any("vendiendo" in p for p in ev["problemas"]))

    def test_la_comision_se_calcula_fija_mas_variable(self):
        self.assertEqual(cartera.costo_orden(1000, {"comision_por_operacion": 3}), 3)
        self.assertEqual(cartera.costo_orden(1000, {"comision_pct": 0.002}), 2)
        self.assertEqual(
            cartera.costo_orden(1000, {"comision_por_operacion": 1, "comision_pct": 0.002}), 3
        )

    def test_una_compra_con_comision_cara_se_rechaza(self):
        a = dict(self.a, reglas=dict(self.a["reglas"], comision_por_operacion=10, orden_minima=100))
        ev = cartera.evaluar_orden(a, "compra", "SPY", 300, "nucleo")
        self.assertTrue(any("comisión" in p.lower() for p in ev["problemas"]))


class TestPlantillas(unittest.TestCase):
    def test_los_datos_reales_son_json_valido(self):
        base = EJEMPLO.parent
        for archivo in ("perfil.json", "cuentas.json", "metas.json"):
            json.loads((base / archivo).read_text(encoding="utf-8"))

    def test_la_plantilla_pide_los_datos_que_faltan(self):
        cuentas = cuentas_por_id(leer_json("cuentas", EJEMPLO.parent))
        self.assertEqual({"arq", "ontop", "openbank"}, set(cuentas))
        self.assertTrue(all(c["tasa_anual_estimada"] is None for c in cuentas.values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)

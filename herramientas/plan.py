#!/usr/bin/env python3
"""Detecta oportunidades de ahorro y propone un plan mensual concreto.

Uso:
    python3 herramientas/plan.py
    python3 herramientas/plan.py --datos datos/ejemplo --json
    python3 herramientas/plan.py --aporte 900   # proyecta con otro aporte mensual
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

import resumen as mod_resumen
from comun import (
    Cambio,
    ErrorDatos,
    a_fecha,
    cuentas_por_id,
    dir_datos,
    leer_json,
    money,
    pct,
    subtitulo,
    titulo,
)

# Umbrales del motor de reglas. Cambialos acá si tu criterio es otro.
UMBRAL_CONCENTRACION = 0.40  # % máximo del patrimonio en una sola cuenta
UMBRAL_COSTOS = 0.01  # comisiones anuales sobre patrimonio
RECORTE_DISCRECIONAL = 0.15  # recorte objetivo sobre gasto discrecional
CATEGORIAS_DISCRECIONALES = {
    "salidas",
    "suscripciones",
    "delivery",
    "ocio",
    "compras",
    "restaurantes",
    "viajes",
}
TOPE_RIESGO = {"conservador": 0.25, "moderado": 0.55, "agresivo": 0.80}


def _tasa(cta: dict) -> float | None:
    t = cta.get("tasa_anual_estimada")
    return None if t is None else float(t)


def mejor_tasa_segura(cuentas: dict) -> tuple[float, str | None]:
    """Mejor rendimiento entre cuentas líquidas y de bajo riesgo (el piso razonable)."""
    mejor, cual = 0.0, None
    for cta in cuentas.values():
        t = _tasa(cta)
        if t is None or cta.get("activa") is False:
            continue
        if (cta.get("riesgo") or 5) <= 2 and (cta.get("liquidez_dias") or 99) <= 7 and t > mejor:
            mejor, cual = t, cta.get("nombre", cta["id"])
    return mejor, cual


def mejor_tasa_crecimiento(cuentas: dict) -> tuple[float, str | None]:
    mejor, cual = 0.0, None
    for cta in cuentas.values():
        t = _tasa(cta)
        if t is None or cta.get("activa") is False:
            continue
        if cta.get("proposito") == "crecimiento" and t > mejor:
            mejor, cual = t, cta.get("nombre", cta["id"])
    return mejor, cual


def oportunidades(r: dict, perfil: dict, cuentas: dict, cambio: Cambio) -> list[dict]:
    base = r["moneda_base"]
    ops: list[dict] = []
    patrimonio = r["patrimonio"]
    tasa_segura, nombre_segura = mejor_tasa_segura(cuentas)
    tasa_crec, nombre_crec = mejor_tasa_crecimiento(cuentas)

    colchon_cfg = perfil.get("colchon_operativo") or {}
    colchon = (
        cambio.a_base(float(colchon_cfg["monto"]), colchon_cfg.get("moneda", base))
        if colchon_cfg.get("monto") is not None
        else None
    )

    def add(clave, titulo_, impacto, detalle, accion, prioridad):
        ops.append(
            {
                "clave": clave,
                "titulo": titulo_,
                "impacto_anual": round(impacto, 2),
                "detalle": detalle,
                "accion": accion,
                "prioridad": prioridad,
            }
        )

    # 1. Plata quieta en cuentas que no rinden.
    ociosas = [
        p for p in r["posiciones"] if p["tasa_anual"] is not None and float(p["tasa_anual"]) <= 0.005
    ]
    ocioso = sum(p["monto_base"] for p in ociosas)
    exceso_ocioso = ocioso - colchon if colchon is not None else ocioso
    if exceso_ocioso > 100 and tasa_segura > 0:
        nombres = ", ".join(p["nombre"] for p in ociosas)
        add(
            "efectivo_ocioso",
            "Hay plata parada que no rinde nada",
            exceso_ocioso * tasa_segura,
            f"{money(ocioso, base)} en {nombres} a ~0%. "
            + (
                f"Descontando el colchón operativo de {money(colchon, base)}, "
                f"sobran {money(exceso_ocioso, base)}."
                if colchon is not None
                else "No hay colchón operativo definido en perfil.json, así que se cuenta todo."
            ),
            f"Mover {money(exceso_ocioso, base)} a {nombre_segura or 'una opción remunerada de bajo riesgo'} "
            f"({pct(tasa_segura)} anual).",
            1,
        )

    # 2. Fondo de emergencia.
    gasto = r["gasto_mensual_promedio"]
    objetivo_fe = gasto * r["meses_emergencia_objetivo"]
    falta_fe = objetivo_fe - r["liquido_bajo_riesgo"]
    if gasto and falta_fe > 0:
        meses = falta_fe / r["excedente_mensual"] if r["excedente_mensual"] > 0 else None
        add(
            "fondo_emergencia",
            "El fondo de emergencia todavía no está completo",
            0.0,
            f"Cubrís {r['meses_emergencia_cubiertos']:.1f} de {r['meses_emergencia_objetivo']} meses. "
            f"Faltan {money(falta_fe, base)}.",
            (
                f"Destinar {money(min(falta_fe, max(r['excedente_mensual'], 0)), base)} por mes hasta completarlo"
                + (f" (~{meses:.0f} meses)." if meses else ".")
            ),
            1,
        )
    elif gasto and falta_fe < -gasto:
        exceso_fe = -falta_fe
        if tasa_crec > tasa_segura:
            add(
                "colchon_excedido",
                "Sobra colchón de bajo riesgo",
                exceso_fe * (tasa_crec - tasa_segura),
                f"Tenés {r['meses_emergencia_cubiertos']:.1f} meses cubiertos contra un objetivo de "
                f"{r['meses_emergencia_objetivo']}: {money(exceso_fe, base)} de más.",
                f"Pasar ese excedente a {nombre_crec or 'la cuenta de crecimiento'} "
                f"({pct(tasa_crec)} vs {pct(tasa_segura)}).",
                3,
            )

    # 3. Tasa de ahorro contra la meta.
    meta = perfil.get("meta_tasa_ahorro")
    ingreso = r["ingreso_mensual_promedio"]
    if meta and ingreso and r["tasa_ahorro"] < meta:
        brecha = (meta - r["tasa_ahorro"]) * ingreso
        add(
            "tasa_ahorro",
            "Estás ahorrando por debajo de tu meta",
            brecha * 12,
            f"Ahorrás {pct(r['tasa_ahorro'])} de tus ingresos; tu meta es {pct(meta)}. "
            f"Son {money(brecha, base)} por mes.",
            f"Recortar {money(brecha, base)} de gasto mensual o subir ingresos en ese monto.",
            1,
        )

    # 4. Excedente que se queda en la caja en vez de ir a una cuenta que rinde.
    sin_colocar = r["excedente_mensual"] - r["aporte_mensual_promedio"]
    if r["excedente_mensual"] > 0 and sin_colocar > 0.15 * r["excedente_mensual"]:
        add(
            "excedente_sin_colocar",
            "Ahorrás, pero el excedente no llega a ninguna cuenta que rinda",
            sin_colocar * 12 * max(tasa_crec, tasa_segura),
            f"Excedente mensual {money(r['excedente_mensual'], base)} contra aportes registrados por "
            f"{money(r['aporte_mensual_promedio'], base)}: quedan {money(sin_colocar, base)} por mes sin destino.",
            f"Programar una transferencia automática de {money(sin_colocar, base)} el día que cobrás.",
            1,
        )

    # 5. Aportes que dependen de acordarse.
    manuales = [
        c
        for c in cuentas.values()
        if c.get("activa") is not False
        and (c.get("aporte_mensual_objetivo") or 0) > 0
        and not c.get("aporte_automatico")
    ]
    if manuales:
        total_manual = sum(float(c["aporte_mensual_objetivo"]) for c in manuales)
        add(
            "aporte_manual",
            "Hay aportes que dependen de que te acuerdes",
            0.0,
            "Aporte manual en: " + ", ".join(c.get("nombre", c["id"]) for c in manuales)
            + f" ({money(total_manual, base)} por mes en total).",
            "Automatizar el débito o la transferencia programada para el día de cobro.",
            2,
        )

    # 6. Concentración.
    for p in r["posiciones"]:
        share = p["monto_base"] / patrimonio if patrimonio else 0
        if share > UMBRAL_CONCENTRACION:
            add(
                "concentracion",
                f"Concentración en {p['nombre']}",
                0.0,
                f"{pct(share)} del patrimonio en una sola cuenta.",
                "Repartir aportes nuevos hacia las otras cuentas hasta bajar del "
                f"{pct(UMBRAL_CONCENTRACION)}.",
                3,
            )

    tope = TOPE_RIESGO.get((perfil.get("perfil_riesgo") or "moderado").lower(), 0.55)
    riesgoso = sum(p["monto_base"] for p in r["posiciones"] if (p["riesgo"] or 0) >= 4)
    if patrimonio and riesgoso / patrimonio > tope:
        add(
            "riesgo",
            "Exposición a riesgo alto por encima de tu perfil",
            0.0,
            f"{pct(riesgoso / patrimonio)} en cuentas de riesgo alto contra un tope de {pct(tope)} "
            f"para perfil {perfil.get('perfil_riesgo')}.",
            "Dirigir los próximos aportes a las cuentas de menor riesgo hasta volver al tope.",
            2,
        )

    # 7. Deuda más cara que cualquier rendimiento.
    for deuda in perfil.get("deudas") or []:
        tasa_d = float(deuda.get("tasa_anual") or 0)
        saldo_d = cambio.a_base(float(deuda.get("saldo") or 0), deuda.get("moneda", base))
        if saldo_d and tasa_d > max(tasa_segura, tasa_crec):
            add(
                "deuda_cara",
                f"Deuda cara: {deuda.get('nombre', deuda.get('id'))}",
                saldo_d * (tasa_d - max(tasa_segura, tasa_crec)),
                f"{money(saldo_d, base)} al {pct(tasa_d)} anual, contra un rendimiento máximo de "
                f"{pct(max(tasa_segura, tasa_crec))}.",
                "Cancelarla antes de sumar plata a inversiones: pagarla rinde más que cualquier cuenta.",
                1,
            )

    # 8. Costos.
    comisiones_anuales = r["comisiones_mensuales_promedio"] * 12
    costo_mantenimiento = sum(
        cambio.a_base(
            float((c.get("costos") or {}).get("mantenimiento_mensual") or 0) * 12,
            (c.get("costos") or {}).get("moneda_costos", base),
        )
        for c in cuentas.values()
    )
    costos = comisiones_anuales + costo_mantenimiento
    if patrimonio and costos / patrimonio > UMBRAL_COSTOS:
        add(
            "costos",
            "Los costos se están comiendo el rendimiento",
            costos * 0.5,
            f"{money(costos, base)} por año en comisiones y mantenimiento = "
            f"{pct(costos / patrimonio)} del patrimonio.",
            "Bajar la frecuencia de operación y comparar comisiones antes de la próxima orden. "
            "La mitad de esto suele ser evitable.",
            2,
        )

    # 9. Gasto discrecional.
    n_meses = max(len(r["meses_analizados"]), 1)
    discrecional = sum(
        monto for cat, monto in r["gasto_por_categoria"].items() if cat in CATEGORIAS_DISCRECIONALES
    )
    if discrecional:
        mensual = discrecional / n_meses
        add(
            "gasto_discrecional",
            "Gasto discrecional recortable",
            mensual * RECORTE_DISCRECIONAL * 12,
            f"{money(mensual, base)} por mes en categorías discrecionales "
            f"({', '.join(c for c in r['gasto_por_categoria'] if c in CATEGORIAS_DISCRECIONALES)}).",
            f"Un recorte del {pct(RECORTE_DISCRECIONAL)} son "
            f"{money(mensual * RECORTE_DISCRECIONAL, base)} por mes sin tocar lo fijo.",
            2,
        )

    # 10. Cuentas sin tasa verificada: no se puede comparar lo que no se mide.
    sin_tasa = [p["nombre"] for p in r["posiciones"] if p["tasa_anual"] is None]
    if sin_tasa:
        add(
            "tasa_desconocida",
            "Hay cuentas sin rendimiento declarado",
            0.0,
            "Sin tasa cargada: " + ", ".join(sin_tasa) + ".",
            "Verificar el rendimiento real de los últimos 12 meses y cargarlo en cuentas.json "
            "con fuente y fecha.",
            1,
        )

    ops.sort(key=lambda o: (o["prioridad"], -o["impacto_anual"]))
    return ops


def cascada(r: dict, perfil: dict, cuentas: dict, cambio: Cambio, metas: dict) -> list[dict]:
    """Reparte el excedente mensual en orden de prioridad."""
    base = r["moneda_base"]
    disponible = max(r["excedente_mensual"], 0.0)
    pasos: list[dict] = []
    tasa_segura, nombre_segura = mejor_tasa_segura(cuentas)
    tasa_crec, nombre_crec = mejor_tasa_crecimiento(cuentas)

    def asignar(nombre, monto, destino, motivo):
        nonlocal disponible
        monto = max(0.0, min(monto, disponible))
        if monto <= 0:
            return
        disponible -= monto
        pasos.append(
            {
                "paso": nombre,
                "monto_mensual": round(monto, 2),
                "destino": destino,
                "motivo": motivo,
            }
        )

    # 1) Deuda cara.
    for deuda in perfil.get("deudas") or []:
        tasa_d = float(deuda.get("tasa_anual") or 0)
        saldo_d = cambio.a_base(float(deuda.get("saldo") or 0), deuda.get("moneda", base))
        if saldo_d and tasa_d > max(tasa_segura, tasa_crec):
            asignar(
                "Cancelar deuda cara",
                min(saldo_d / 6, disponible),
                deuda.get("nombre", deuda.get("id")),
                f"Al {pct(tasa_d)} anual, pagarla rinde más que invertir.",
            )

    # 2) Fondo de emergencia.
    falta_fe = (
        r["gasto_mensual_promedio"] * r["meses_emergencia_objetivo"] - r["liquido_bajo_riesgo"]
    )
    if falta_fe > 0:
        asignar(
            "Completar fondo de emergencia",
            min(falta_fe, disponible * 0.6),
            nombre_segura or "cuenta remunerada de bajo riesgo",
            f"Faltan {money(falta_fe, base)} para {r['meses_emergencia_objetivo']} meses de gastos.",
        )

    # 3) Metas con fecha.
    hoy = a_fecha(r["fecha"])
    for meta in sorted(metas.get("metas", []), key=lambda m: m.get("prioridad", 99)):
        if meta.get("id") == "emergencia" or not meta.get("fecha_objetivo"):
            continue
        meses_restantes = max(
            1.0, (a_fecha(meta["fecha_objetivo"]).toordinal() - hoy.toordinal()) / 30.44
        )
        objetivo = cambio.a_base(float(meta.get("objetivo") or 0), meta.get("moneda", base))
        asignado = cambio.a_base(float(meta.get("asignado") or 0), meta.get("moneda", base))
        falta = max(objetivo - asignado, 0.0)
        asignar(
            f"Meta: {meta.get('nombre')}",
            falta / meses_restantes,
            meta.get("cuenta_id") or "cuenta a definir",
            f"Faltan {money(falta, base)} de {money(objetivo, base)} en {meses_restantes:.0f} meses.",
        )

    # 4) El resto, a crecimiento.
    if disponible > 0:
        asignar(
            "Inversión de largo plazo",
            disponible,
            nombre_crec or "cuenta de crecimiento",
            f"Excedente restante al mejor rendimiento disponible ({pct(tasa_crec)}).",
        )

    return pasos


def proyectar(patrimonio: float, aporte_mensual: float, tasa_anual: float, meses: int) -> float:
    r = tasa_anual / 12
    valor = patrimonio
    for _ in range(meses):
        valor = valor * (1 + r) + aporte_mensual
    return valor


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Plan de ahorro y oportunidades")
    ap.add_argument("--datos", help="directorio de datos")
    ap.add_argument("--meses", type=int, default=6)
    ap.add_argument("--hoy", help="fecha de corte AAAA-MM-DD")
    ap.add_argument(
        "--aporte", type=float, help="aporte mensual a proyectar (por defecto, el del plan)"
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        datos = dir_datos(args.datos)
        hoy = a_fecha(args.hoy) if args.hoy else date.today()
        r = mod_resumen.calcular(datos, args.meses, hoy)
        perfil = leer_json("perfil", datos)
        cuentas = cuentas_por_id(leer_json("cuentas", datos))
        metas = leer_json("metas", datos)
        cambio = Cambio(perfil)
        ops = oportunidades(r, perfil, cuentas, cambio)
        pasos = cascada(r, perfil, cuentas, cambio, metas)
    except ErrorDatos as exc:
        print(f"Error en los datos: {exc}", file=sys.stderr)
        return 1

    base = r["moneda_base"]
    aporte_plan = sum(p["monto_mensual"] for p in pasos if p["paso"] != "Cancelar deuda cara")
    aporte = args.aporte if args.aporte is not None else aporte_plan
    tasa = r["rendimiento_ponderado"]
    proyeccion = {
        str(m): {
            "actual": round(proyectar(r["patrimonio"], r["aporte_mensual_promedio"], tasa, m), 2),
            "con_plan": round(proyectar(r["patrimonio"], aporte, tasa, m), 2),
        }
        for m in (12, 36, 60)
    }

    salida = {
        "fecha": r["fecha"],
        "moneda_base": base,
        "patrimonio": r["patrimonio"],
        "excedente_mensual": r["excedente_mensual"],
        "oportunidades": ops,
        "impacto_anual_total": round(sum(o["impacto_anual"] for o in ops), 2),
        "plan_mensual": pasos,
        "aporte_mensual_plan": round(aporte, 2),
        "proyeccion": proyeccion,
        "pendientes": r["pendientes"],
    }

    if args.json:
        print(json.dumps(salida, ensure_ascii=False, indent=2))
        return 0

    print(titulo(f"Plan de ahorro — {r['fecha']}"))
    print(
        f"Patrimonio {money(r['patrimonio'], base)} · excedente mensual "
        f"{money(r['excedente_mensual'], base)}"
    )

    print(subtitulo("Oportunidades (ordenadas por prioridad e impacto)"))
    for i, o in enumerate(ops, 1):
        impacto = f"  →  hasta {money(o['impacto_anual'], base)}/año" if o["impacto_anual"] else ""
        print(f"\n{i}. [P{o['prioridad']}] {o['titulo']}{impacto}")
        print(f"   {o['detalle']}")
        print(f"   Acción: {o['accion']}")
    if salida["impacto_anual_total"]:
        print(
            f"\nImpacto anual estimado si hacés todo: {money(salida['impacto_anual_total'], base)}"
        )

    print(subtitulo("Adónde va el excedente cada mes"))
    for p in pasos:
        print(f"  {money(p['monto_mensual'], base):>14}  →  {p['paso']} ({p['destino']})")
        print(f"                    {p['motivo']}")
    if not pasos:
        print("  Sin excedente mensual asignable con los datos cargados.")

    print(subtitulo(f"Proyección (rendimiento ponderado {pct(tasa)})"))
    print(f"  {'plazo':<8}{'sin cambios':>18}{'con el plan':>18}{'diferencia':>18}")
    for m, v in proyeccion.items():
        print(
            f"  {m + ' m':<8}{money(v['actual'], base):>18}{money(v['con_plan'], base):>18}"
            f"{money(v['con_plan'] - v['actual'], base):>18}"
        )

    if r["pendientes"]:
        print(subtitulo("Antes de decidir, completá"))
        for p in dict.fromkeys(r["pendientes"]):
            print(f"  • {p}")
    print(
        "\nEsto es una herramienta personal de cálculo, no asesoramiento financiero. "
        "Verificá tasas y condiciones antes de mover plata."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

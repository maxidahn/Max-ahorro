#!/usr/bin/env python3
"""Foto del estado de ahorro: patrimonio, flujo, tasa de ahorro y fondo de emergencia.

Uso:
    python3 herramientas/resumen.py
    python3 herramientas/resumen.py --datos datos/ejemplo --meses 6
    python3 herramientas/resumen.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from comun import (
    Cambio,
    ErrorDatos,
    a_fecha,
    a_numero,
    barra,
    cuentas_por_id,
    dir_datos,
    flujo_mensual,
    leer_csv,
    leer_json,
    mes_de,
    meses_hacia_atras,
    money,
    pct,
    promedio,
    saldos_actuales,
    subtitulo,
    titulo,
)


def calcular(datos_dir, n_meses: int, hoy: date) -> dict:
    perfil = leer_json("perfil", datos_dir)
    cuentas_raw = leer_json("cuentas", datos_dir)
    saldos = leer_csv("saldos", datos_dir)
    movimientos = leer_csv("movimientos", datos_dir)

    cambio = Cambio(perfil)
    base = cambio.base
    cuentas = cuentas_por_id(cuentas_raw)
    pendientes: list[str] = []

    if not saldos:
        pendientes.append("No hay saldos cargados (datos/saldos.csv).")
    if not movimientos:
        pendientes.append("No hay movimientos cargados (datos/movimientos.csv).")
    if (perfil.get("ingreso_mensual") or {}).get("monto") is None:
        pendientes.append("Falta ingreso_mensual.monto en perfil.json.")
    if (perfil.get("colchon_operativo") or {}).get("monto") is None:
        pendientes.append(
            "Falta colchon_operativo.monto en perfil.json: sin eso no se sabe cuánta plata "
            "líquida sobra."
        )
    for cta in cuentas.values():
        if cta.get("activa") is not False and cta.get("tasa_anual_estimada") is None:
            pendientes.append(
                f"Falta tasa_anual_estimada de '{cta.get('nombre', cta['id'])}' en cuentas.json."
            )

    # --- patrimonio -------------------------------------------------------
    ultimos = saldos_actuales(saldos, hoy)
    posiciones = []
    for cid, fila in ultimos.items():
        cta = cuentas.get(cid, {})
        if cta.get("activa") is False:
            continue
        moneda = (fila.get("moneda") or cta.get("moneda") or base).upper()
        monto = cambio.a_base(a_numero(fila["saldo"], f"saldo de {cid}"), moneda)
        tasa = cta.get("tasa_anual_estimada")
        posiciones.append(
            {
                "cuenta_id": cid,
                "nombre": cta.get("nombre", cid),
                "fecha": fila["fecha"],
                "monto_base": monto,
                "moneda": moneda,
                "tasa_anual": tasa,
                "liquidez_dias": cta.get("liquidez_dias"),
                "riesgo": cta.get("riesgo"),
                "proposito": cta.get("proposito"),
                "desconocida": cid not in cuentas,
            }
        )
        if cid not in cuentas:
            pendientes.append(f"El saldo de '{cid}' no tiene cuenta declarada en cuentas.json.")
        elif tasa is None:
            pendientes.append(f"Falta tasa_anual_estimada de '{cid}' en cuentas.json.")

    posiciones.sort(key=lambda p: p["monto_base"], reverse=True)
    patrimonio = sum(p["monto_base"] for p in posiciones)

    # Patrimonio a fin del mes anterior, para ver la variación real.
    primer_dia = hoy.replace(day=1)
    corte_previo = primer_dia.fromordinal(primer_dia.toordinal() - 1)
    previos = saldos_actuales(saldos, corte_previo)
    patrimonio_previo = sum(
        cambio.a_base(
            a_numero(f["saldo"], "saldo"),
            (f.get("moneda") or cuentas.get(cid, {}).get("moneda") or base),
        )
        for cid, f in previos.items()
        if cuentas.get(cid, {}).get("activa") is not False
    )

    for moneda in sorted(cambio.faltantes):
        pendientes.append(f"Falta el tipo de cambio de {moneda} en perfil.json.")

    dias_fx = cambio.dias_desde_actualizacion(hoy)
    if dias_fx is None:
        pendientes.append("Falta tipo_cambio_actualizado en perfil.json.")
    elif dias_fx > 30:
        pendientes.append(f"El tipo de cambio tiene {dias_fx} días. Actualizalo antes de decidir.")

    # --- flujo ------------------------------------------------------------
    meses = meses_hacia_atras(n_meses, hoy)
    flujo = flujo_mensual(movimientos, cambio, meses)
    por_mes = flujo["por_mes"]
    mes_actual = mes_de(hoy)
    # El mes en curso está incompleto: no ensucia los promedios.
    meses_cerrados = [m for m in meses if m != mes_actual and any(por_mes[m].values())]

    ingresos = [por_mes[m]["ingreso"] for m in meses_cerrados]
    gastos = [por_mes[m]["gasto"] + por_mes[m]["comision"] for m in meses_cerrados]
    aportes = [por_mes[m]["aporte"] for m in meses_cerrados]
    comisiones = [por_mes[m]["comision"] for m in meses_cerrados]

    ingreso_prom = promedio(ingresos)
    if not ingreso_prom:
        declarado = (perfil.get("ingreso_mensual") or {}).get("monto")
        if declarado:
            ingreso_prom = cambio.a_base(
                float(declarado), (perfil.get("ingreso_mensual") or {}).get("moneda", base)
            )
    gasto_prom = promedio(gastos)
    aporte_prom = promedio(aportes)
    excedente = ingreso_prom - gasto_prom
    tasa_ahorro = excedente / ingreso_prom if ingreso_prom else 0.0

    # --- fondo de emergencia ----------------------------------------------
    liquido = sum(
        p["monto_base"]
        for p in posiciones
        if (p["liquidez_dias"] is not None and p["liquidez_dias"] <= 7)
        and (p["riesgo"] is not None and p["riesgo"] <= 2)
    )
    meses_cubiertos = liquido / gasto_prom if gasto_prom else 0.0
    objetivo_meses = perfil.get("fondo_emergencia_meses_objetivo") or 6

    # --- rendimiento ponderado --------------------------------------------
    con_tasa = [p for p in posiciones if p["tasa_anual"] is not None]
    base_tasa = sum(p["monto_base"] for p in con_tasa)
    rend_ponderado = (
        sum(p["monto_base"] * float(p["tasa_anual"]) for p in con_tasa) / base_tasa
        if base_tasa
        else 0.0
    )

    return {
        "fecha": hoy.isoformat(),
        "moneda_base": base,
        "patrimonio": patrimonio,
        "patrimonio_mes_anterior": patrimonio_previo,
        "variacion_mes": patrimonio - patrimonio_previo,
        "posiciones": posiciones,
        "meses_analizados": meses_cerrados,
        "flujo_por_mes": por_mes,
        "gasto_por_categoria": dict(
            sorted(flujo["por_categoria"].items(), key=lambda kv: kv[1], reverse=True)
        ),
        "ingreso_mensual_promedio": ingreso_prom,
        "gasto_mensual_promedio": gasto_prom,
        "aporte_mensual_promedio": aporte_prom,
        "comisiones_mensuales_promedio": promedio(comisiones),
        "excedente_mensual": excedente,
        "tasa_ahorro": tasa_ahorro,
        "meta_tasa_ahorro": perfil.get("meta_tasa_ahorro"),
        "liquido_bajo_riesgo": liquido,
        "meses_emergencia_cubiertos": meses_cubiertos,
        "meses_emergencia_objetivo": objetivo_meses,
        "rendimiento_ponderado": rend_ponderado,
        "pendientes": pendientes,
    }


def imprimir(r: dict) -> None:
    b = r["moneda_base"]
    print(titulo(f"Resumen de ahorro — {r['fecha']}"))
    print(f"Patrimonio total: {money(r['patrimonio'], b)}")
    if r["patrimonio_mes_anterior"]:
        delta = r["variacion_mes"]
        signo = "+" if delta >= 0 else "−"
        print(f"Variación desde fin del mes anterior: {signo}{money(abs(delta), b)}")
    else:
        print("Variación mensual: sin saldos del mes anterior para comparar.")

    print(subtitulo("Dónde está la plata"))
    total = r["patrimonio"] or 1
    for p in r["posiciones"]:
        share = p["monto_base"] / total
        tasa = pct(float(p["tasa_anual"])) if p["tasa_anual"] is not None else "tasa ?"
        print(
            f"  {p['nombre'][:34]:<34} {money(p['monto_base'], b):>16}  "
            f"{barra(share, 12)} {share * 100:>5.1f}%  {tasa:>7}  (al {p['fecha']})"
        )

    print(subtitulo("Flujo mensual promedio"))
    if r["meses_analizados"]:
        print(f"  Meses considerados: {', '.join(r['meses_analizados'])}")
    print(f"  Ingresos:  {money(r['ingreso_mensual_promedio'], b):>14}")
    print(f"  Gastos:    {money(r['gasto_mensual_promedio'], b):>14}")
    print(f"  Excedente: {money(r['excedente_mensual'], b):>14}")
    print(f"  Aportes registrados: {money(r['aporte_mensual_promedio'], b)}")
    if r["comisiones_mensuales_promedio"]:
        print(f"  Comisiones: {money(r['comisiones_mensuales_promedio'], b)} por mes")
    meta = r["meta_tasa_ahorro"]
    linea_meta = f" (meta {pct(meta)})" if meta else ""
    print(f"  Tasa de ahorro: {pct(r['tasa_ahorro'])}{linea_meta}  {barra(r['tasa_ahorro'])}")

    if r["gasto_por_categoria"]:
        print(subtitulo("Gasto por categoría (total del período)"))
        for cat, monto in list(r["gasto_por_categoria"].items())[:10]:
            print(f"  {cat[:24]:<24} {money(monto, b):>14}")

    print(subtitulo("Colchón"))
    print(
        f"  Líquido y de bajo riesgo: {money(r['liquido_bajo_riesgo'], b)} "
        f"= {r['meses_emergencia_cubiertos']:.1f} meses de gasto "
        f"(objetivo {r['meses_emergencia_objetivo']})"
    )
    print(f"  Rendimiento anual ponderado del portafolio: {pct(r['rendimiento_ponderado'])}")

    if r["pendientes"]:
        print(subtitulo("Datos que faltan"))
        for p in dict.fromkeys(r["pendientes"]):
            print(f"  • {p}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Resumen del estado de ahorro")
    ap.add_argument("--datos", help="directorio de datos (por defecto datos/)")
    ap.add_argument("--meses", type=int, default=6, help="meses de flujo a analizar")
    ap.add_argument("--hoy", help="fecha de corte AAAA-MM-DD (para pruebas)")
    ap.add_argument("--json", action="store_true", help="salida JSON")
    args = ap.parse_args(argv)

    try:
        hoy = a_fecha(args.hoy) if args.hoy else date.today()
        r = calcular(dir_datos(args.datos), args.meses, hoy)
    except ErrorDatos as exc:
        print(f"Error en los datos: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        imprimir(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

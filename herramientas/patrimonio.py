#!/usr/bin/env python3
"""Patrimonio completo: qué es capital invertible, qué es bien de uso y qué es
una promesa de cobro. Los tres suman, pero no sirven para lo mismo.

Uso:
    python3 herramientas/patrimonio.py
    python3 herramientas/patrimonio.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from datetime import date

from comun import Cambio, ErrorDatos, dir_datos, leer_json, money, pct, subtitulo, titulo


def analizar(datos: Path) -> dict:
    perfil = leer_json("perfil", datos)
    cambio = Cambio(perfil)
    base = cambio.base

    archivo = datos / "patrimonio.json"
    extra = json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {}

    # El capital invertible sale de TODAS las cuentas, no sólo del broker.
    import resumen as mod_resumen

    foto = mod_resumen.calcular(datos, 6, date.today())
    invertible = foto["patrimonio"]
    liquido = foto["liquido_bajo_riesgo"]

    uso = [
        {
            "nombre": a["nombre"],
            "valor_base": cambio.a_base(float(a["valor"]), a.get("moneda", base)),
            "notas": a.get("notas", ""),
        }
        for a in extra.get("activos_de_uso", [])
    ]
    cobrar = [
        {
            "nombre": c["nombre"],
            "nominal_base": cambio.a_base(float(c["valor_nominal"]), c.get("moneda", base)),
            "recuperable_base": cambio.a_base(
                float(c["valor_nominal"]) - float(c.get("incobrable_estimado") or 0),
                c.get("moneda", base),
            ),
            "notas": c.get("notas", ""),
        }
        for c in extra.get("por_cobrar", [])
    ]
    deudas = sum(
        cambio.a_base(float(d.get("saldo") or 0), d.get("moneda", base))
        for d in (perfil.get("deudas") or [])
    )

    total_uso = sum(a["valor_base"] for a in uso)
    total_cobrar = sum(c["recuperable_base"] for c in cobrar)
    quita = sum(c["nominal_base"] - c["recuperable_base"] for c in cobrar)
    neto = invertible + total_uso + total_cobrar - deudas

    gasto = perfil.get("gasto_mensual") or {}
    gasto_base = (
        cambio.a_base(float(gasto["monto"]), gasto.get("moneda", base))
        if gasto.get("monto")
        else None
    )

    return {
        "moneda_base": base,
        "capital_invertible": invertible,
        "liquido_bajo_riesgo": liquido,
        "activos_de_uso": uso,
        "total_activos_de_uso": total_uso,
        "por_cobrar": cobrar,
        "total_por_cobrar_recuperable": total_cobrar,
        "quita_por_incobrable": quita,
        "deudas": deudas,
        "patrimonio_neto": neto,
        "gasto_mensual": gasto_base,
        "meses_de_gasto_en_capital": invertible / gasto_base if gasto_base else None,
        "meses_de_gasto_liquidos": liquido / gasto_base if gasto_base else None,
        "faltan": extra.get("faltan", []),
    }


def imprimir(r: dict) -> None:
    b = r["moneda_base"]
    neto = r["patrimonio_neto"] or 1
    print(titulo("Patrimonio completo"))
    print(f"  Patrimonio neto: {money(r['patrimonio_neto'], b)}\n")
    print(f"  {'concepto':<34}{'valor':>15}{'del total':>12}   sirve para")
    filas = [
        ("Capital invertible (cartera)", r["capital_invertible"], "invertir y, vendiendo, cubrir imprevistos"),
        ("Bienes de uso", r["total_activos_de_uso"], "usarlo; no rinde y se deprecia"),
        ("Por cobrar (recuperable)", r["total_por_cobrar_recuperable"], "nada hasta que entre"),
    ]
    for nombre, valor, para in filas:
        print(f"  {nombre:<34}{money(valor, b):>15}{pct(valor / neto):>12}   {para}")
    if r["deudas"]:
        print(f"  {'Deudas':<34}{money(-r['deudas'], b):>15}")

    if r["quita_por_incobrable"]:
        print(subtitulo("Por cobrar"))
        for c in r["por_cobrar"]:
            print(f"  {c['nombre']}: nominal {money(c['nominal_base'], b)}, "
                  f"se cuenta {money(c['recuperable_base'], b)}")
        print(f"  Quita por incobrable: {money(r['quita_por_incobrable'], b)}. "
              "Contar lo que no vas a cobrar es engañarte con tu propio balance.")

    if r["meses_de_gasto_en_capital"] is not None:
        print(subtitulo("Lo que esto significa para tu colchón"))
        print(f"  Gasto mensual: {money(r['gasto_mensual'], b)}")
        print(
            f"  Capital invertible: {r['meses_de_gasto_en_capital']:.1f} meses de gasto."
        )
        print(
            f"  De eso, líquido y de bajo riesgo (disponible en menos de una semana): "
            f"{money(r['liquido_bajo_riesgo'], b)} = {r['meses_de_gasto_liquidos']:.1f} meses."
        )
        print(
            "  El resto está a precio de mercado o con plazo: si necesitás venderlo en un mal mes,\n"
            "  vendés perdiendo, y lo que tiene plazo no está el día que lo pedís."
        )
        print("  Los bienes de uso y lo por cobrar no cubren una emergencia: no se venden por partes\n"
              "  ni entran cuando los necesitás.")

    if r["faltan"]:
        print(subtitulo("Datos que faltan"))
        for f in r["faltan"]:
            print(f"  • {f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Patrimonio completo")
    ap.add_argument("--datos")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        r = analizar(dir_datos(args.datos))
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

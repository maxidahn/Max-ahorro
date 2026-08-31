#!/usr/bin/env python3
"""Cobrás en una moneda y gastás en otra: cuánto cuesta convertir, y qué haría
falta para que endeudarse en la moneda local salga mejor que convertir.

No pronostica el tipo de cambio. Calcula a qué tipo de cambio EMPATÁS, para que
la decisión se tome contra un número y no contra una sensación.

Uso:
    python3 herramientas/cambio.py --sueldo 1600 --tasa-hoy 17.04 --tasa-referencia 18.50
    python3 herramientas/cambio.py --sueldo 1600 --tasa-hoy 17.04 --tasa-referencia 18.50 \
        --prestamo 80000 --cuota 4841.29 --meses 24
"""

from __future__ import annotations

import argparse
import json

from comun import money, pct, subtitulo, titulo


def analizar(
    sueldo: float,
    tasa_hoy: float,
    tasa_ref: float | None,
    prestamo: float | None,
    cuota: float | None,
    meses: int | None,
    moneda_local: str,
    moneda_sueldo: str,
) -> dict:
    pesos_hoy = sueldo * tasa_hoy
    r = {
        "sueldo": sueldo,
        "tasa_hoy": tasa_hoy,
        "pesos_por_mes_hoy": pesos_hoy,
        "moneda_local": moneda_local,
        "moneda_sueldo": moneda_sueldo,
    }

    if tasa_ref:
        pesos_ref = sueldo * tasa_ref
        r["referencia"] = {
            "tasa": tasa_ref,
            "pesos_por_mes": pesos_ref,
            "diferencia_mensual": pesos_ref - pesos_hoy,
            "diferencia_anual": (pesos_ref - pesos_hoy) * 12,
            "diferencia_pct": (pesos_ref - pesos_hoy) / pesos_ref,
        }

    if prestamo and cuota and meses:
        total = cuota * meses
        recibido_en_sueldo = prestamo / tasa_hoy  # los dólares que NO tenés que vender hoy
        empate = total / recibido_en_sueldo  # tipo de cambio que deja la operación en cero
        meses_cubiertos = prestamo / pesos_hoy
        r["prestamo"] = {
            "monto": prestamo,
            "meses": meses,
            "cuota": cuota,
            "total_a_pagar": total,
            "costo": total - prestamo,
            "dolares_que_no_vendes_hoy": recibido_en_sueldo,
            "tipo_de_cambio_de_empate": empate,
            "suba_necesaria_pct": empate / tasa_hoy - 1,
            "meses_de_sueldo_que_reemplaza": meses_cubiertos,
        }
        if tasa_ref:
            costo_en_sueldo = total / tasa_ref
            r["prestamo"]["si_vuelve_a_la_referencia"] = {
                "tasa": tasa_ref,
                "costo_en_moneda_sueldo": costo_en_sueldo,
                "resultado": recibido_en_sueldo - costo_en_sueldo,
            }
            evitado = r["referencia"]["diferencia_mensual"] * meses_cubiertos
            r["prestamo"]["diferencia_de_cambio_evitada"] = evitado
            r["prestamo"]["neto_contra_la_diferencia"] = evitado - (total - prestamo)
    return r


def imprimir(r: dict) -> None:
    ml, ms = r["moneda_local"], r["moneda_sueldo"]
    print(titulo(f"Cobrar en {ms} y gastar en {ml}"))
    print(
        f"  {money(r['sueldo'], ms)} por mes a {r['tasa_hoy']:.4f} = "
        f"{money(r['pesos_por_mes_hoy'], ml)} por mes"
    )

    if "referencia" in r:
        ref = r["referencia"]
        print(subtitulo(f"Contra un tipo de cambio de {ref['tasa']:.4f}"))
        print(f"  Recibirías {money(ref['pesos_por_mes'], ml)} por mes")
        print(
            f"  Diferencia: {money(ref['diferencia_mensual'], ml)} por mes · "
            f"{money(ref['diferencia_anual'], ml)} por año ({pct(ref['diferencia_pct'])} menos)"
        )
        print(
            "  Ojo con leer esto como una pérdida: un tipo de cambio pasado no es una opción\n"
            "  disponible. No se puede vender al precio del año pasado."
        )

    if "prestamo" in r:
        p = r["prestamo"]
        print(subtitulo("Endeudarse en vez de convertir"))
        print(
            f"  Pedís {money(p['monto'], ml)} y devolvés {money(p['total_a_pagar'], ml)} "
            f"({money(p['costo'], ml)} de costo)."
        )
        print(
            f"  Eso te evita vender {money(p['dolares_que_no_vendes_hoy'], ms)} hoy, y te cubre "
            f"{p['meses_de_sueldo_que_reemplaza']:.1f} meses de sueldo."
        )
        print(
            f"\n  Tipo de cambio de EMPATE: {p['tipo_de_cambio_de_empate']:.2f} "
            f"(hoy {r['tasa_hoy']:.2f}, es decir {pct(p['suba_necesaria_pct'])} de suba)"
        )
        print("  Por debajo de ese número, endeudarse cuesta más que convertir hoy.")

        if "si_vuelve_a_la_referencia" in p:
            v = p["si_vuelve_a_la_referencia"]
            print(
                f"\n  Si el tipo de cambio vuelve a {v['tasa']:.2f}: pagar el préstamo te costaría "
                f"{money(v['costo_en_moneda_sueldo'], ms)}"
            )
            print(
                f"  contra los {money(p['dolares_que_no_vendes_hoy'], ms)} que te ahorraste vender "
                f"→ resultado {money(v['resultado'], ms)}"
            )
        if "neto_contra_la_diferencia" in p:
            print(
                f"\n  Diferencia de cambio que evitás: {money(p['diferencia_de_cambio_evitada'], ml)}"
            )
            print(f"  Costo del préstamo:                {money(p['costo'], ml)}")
            print(f"  Neto:                              {money(p['neto_contra_la_diferencia'], ml)}")

    print(
        "\n  Nada de esto pronostica el tipo de cambio. Guardar la moneda en la que cobrás no "
        "cuesta nada;\n  endeudarse para poder guardarla sí. El número de empate es lo que separa "
        "una cosa de la otra."
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Costo de convertir vs endeudarse en moneda local")
    ap.add_argument("--sueldo", type=float, required=True, help="sueldo mensual en la moneda que cobrás")
    ap.add_argument("--tasa-hoy", type=float, required=True, help="unidades de moneda local por 1 de sueldo")
    ap.add_argument("--tasa-referencia", type=float, help="tipo de cambio con el que lo comparás")
    ap.add_argument("--prestamo", type=float)
    ap.add_argument("--cuota", type=float)
    ap.add_argument("--meses", type=int)
    ap.add_argument("--moneda-local", default="MXN")
    ap.add_argument("--moneda-sueldo", default="USD")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    r = analizar(
        args.sueldo, args.tasa_hoy, args.tasa_referencia, args.prestamo, args.cuota,
        args.meses, args.moneda_local, args.moneda_sueldo,
    )
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        imprimir(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Evalúa pedir prestado para invertir: cuánto cuesta la deuda y qué tiene que
rendir la inversión para que valga la pena.

No predice rendimientos. Muestra el costo, que es cierto, contra un abanico de
resultados posibles, que no lo son.

Uso:
    python3 herramientas/apalancamiento.py --monto 500000 --meses 60 --tasa-mensual 0.0243
    python3 herramientas/apalancamiento.py --monto 80000 --meses 24 --cuota 4841.29
    python3 herramientas/apalancamiento.py --monto 500000 --meses 60 --cuota 18963 --isr 0.30
"""

from __future__ import annotations

import argparse
import json
import sys

from comun import money, pct, subtitulo, titulo

ESCENARIOS = [-0.60, -0.40, -0.20, 0.0, 0.10, 0.20, 0.40, 0.60, 1.00]


def cuota_de(principal: float, i: float, n: int) -> float:
    if i == 0:
        return principal / n
    return principal * i / (1 - (1 + i) ** -n)


def tasa_implicita(principal: float, cuota: float, n: int) -> float:
    """Tasa mensual que iguala el flujo real de pagos (incluye IVA y comisiones)."""
    lo, hi = 0.0, 2.0
    for _ in range(300):
        mid = (lo + hi) / 2
        if cuota_de(principal, mid, n) > cuota:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def analizar(
    principal: float,
    meses: int,
    tasa_mensual: float | None,
    cuota: float | None,
    iva: float,
    isr: float,
) -> dict:
    if cuota is None:
        if tasa_mensual is None:
            raise ValueError("Hace falta --tasa-mensual o --cuota.")
        # El IVA en México se cobra sobre el interés, no sobre el capital.
        cuota_sin_iva = cuota_de(principal, tasa_mensual, meses)
        interes_total = cuota_sin_iva * meses - principal
        cuota = cuota_sin_iva + (interes_total * iva) / meses

    i = tasa_implicita(principal, cuota, meses)
    anual = (1 + i) ** 12 - 1
    total = cuota * meses
    costo = total - principal
    bruto_necesario = anual / (1 - isr) if isr < 1 else None
    anios = meses / 12
    # Dos empates distintos, según de dónde salgan las cuotas.
    empate_simple = (total / principal) ** (1 / anios) - 1

    escenarios = []
    for r in ESCENARIOS:
        valor = principal * (1 + r) ** anios
        escenarios.append(
            {
                "rendimiento_anual": r,
                "valor_final": valor,
                "neto": valor - total,
                "cubre_la_deuda": valor >= total,
            }
        )

    return {
        "principal": principal,
        "meses": meses,
        "cuota": cuota,
        "total_a_pagar": total,
        "costo": costo,
        "costo_sobre_capital": costo / principal,
        "tasa_mensual_efectiva": i,
        "tasa_anual_efectiva": anual,
        "empate_si_las_cuotas_salen_del_gasto": empate_simple,
        "empate_si_las_cuotas_salen_del_ahorro": anual,
        "rendimiento_bruto_necesario": bruto_necesario,
        "escenarios": escenarios,
    }


def imprimir(a: dict, moneda: str, isr: float) -> None:
    print(titulo(f"Pedir {money(a['principal'], moneda)} a {a['meses']} meses para invertir"))
    print(f"  Cuota mensual:        {money(a['cuota'], moneda)}")
    print(f"  Total a devolver:     {money(a['total_a_pagar'], moneda)}")
    print(
        f"  Costo del préstamo:   {money(a['costo'], moneda)} "
        f"= {pct(a['costo_sobre_capital'])} del capital"
    )
    print(f"  Tasa efectiva anual:  {pct(a['tasa_anual_efectiva'])} (según el flujo real de pagos)")

    print(subtitulo("Cuánto tiene que rendir la inversión para empatar"))
    print(
        f"  Si las cuotas salen de plata que igual ibas a gastar:   "
        f"{pct(a['empate_si_las_cuotas_salen_del_gasto'])} anual"
    )
    print(
        f"  Si las cuotas salen de plata que ibas a invertir igual: "
        f"{pct(a['empate_si_las_cuotas_salen_del_ahorro'])} anual"
    )
    print(
        "  El segundo es el caso real cuando pedís prestado para liberar tu sueldo hacia la "
        "inversión:\n  ahí el préstamo compite contra tu propio ahorro, no contra cero."
    )
    if a["rendimiento_bruto_necesario"]:
        print(
            f"  Con un impuesto del {pct(isr)} sobre la ganancia, ese segundo número sube a "
            f"{pct(a['rendimiento_bruto_necesario'])} anual."
        )
    print("  Todos los años, sin un solo año malo. El costo es contractual; el rendimiento no.")

    print(
        subtitulo(
            f"Si invertís el capital y lo dejás {a['meses'] / 12:.0f} años "
            "(cuotas pagadas aparte)"
        )
    )
    print(f"  {'rendimiento':>12}{'valor final':>18}{'resultado neto':>18}")
    for e in a["escenarios"]:
        marca = "" if e["cubre_la_deuda"] else "  ←  no alcanza a pagar la deuda"
        print(
            f"  {e['rendimiento_anual'] * 100:>11.0f}%{money(e['valor_final'], moneda):>18}"
            f"{money(e['neto'], moneda):>18}{marca}"
        )

    peor = a["escenarios"][0]
    print(subtitulo("Lo que no cambia en ningún escenario"))
    print(f"  • La cuota de {money(a['cuota'], moneda)} se paga igual, todos los meses.")
    print(
        f"  • En el peor escenario de la tabla quedás debiendo "
        f"{money(-peor['neto'], moneda)} con la inversión ya contada."
    )
    print("  • La deuda no cae con el activo: si el activo baja 60%, la deuda sigue entera.")
    print(
        "\nEsto es aritmética del préstamo, no una opinión sobre ningún activo ni una "
        "recomendación. Verificá la cuota y el total a pagar en el contrato antes de firmar."
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Costo de endeudarse para invertir")
    ap.add_argument("--monto", type=float, required=True)
    ap.add_argument("--meses", type=int, required=True)
    ap.add_argument("--tasa-mensual", type=float, help="tasa mensual en decimal (0.0243 = 2,43%%)")
    ap.add_argument("--cuota", type=float, help="cuota mensual real, si ya la conocés")
    ap.add_argument("--iva", type=float, default=0.16, help="IVA sobre el interés (México: 0.16)")
    ap.add_argument("--isr", type=float, default=0.0, help="impuesto sobre la ganancia")
    ap.add_argument("--moneda", default="MXN")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        a = analizar(args.monto, args.meses, args.tasa_mensual, args.cuota, args.iva, args.isr)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(a, ensure_ascii=False, indent=2))
    else:
        imprimir(a, args.moneda, args.isr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

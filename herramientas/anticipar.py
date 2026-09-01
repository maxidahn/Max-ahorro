#!/usr/bin/env python3
"""¿Conviene endeudarse para invertir hoy, en vez de aportar mes a mes?

Compara dos caminos con el mismo dinero y el mismo activo:
  A) sin deuda: aportás lo que podés cada mes;
  B) con deuda: invertís todo hoy y después aportás menos, porque pagás la cuota.

La diferencia entre los dos no es cuánto invertís: es CUÁNDO. El préstamo compra
tiempo, y este script dice cuánto cuesta ese tiempo y cuánto tiene que rendir el
activo para que haya valido la pena.

Uso:
    python3 herramientas/anticipar.py --prestamo 180000 --cuota 10892.91 --meses 24 \
        --aporte 1000 --aporte-luego 2000 --cambio-mes 4 --tc 17.0427
"""

from __future__ import annotations

import argparse
import json

from comun import money, pct, subtitulo, titulo

ESCENARIOS = [-0.50, -0.25, 0.0, 0.15, 0.30, 0.46, 0.60, 1.00]


def aportes(aporte: float, aporte_luego: float | None, cambio_mes: int, meses: int) -> list[float]:
    luego = aporte if aporte_luego is None else aporte_luego
    return [aporte if m < cambio_mes else luego for m in range(meses)]


def futuro(inicial: float, flujos: list[float], r_anual: float) -> float:
    """Valor final aportando al principio de cada mes, con rendimiento constante."""
    i = (1 + r_anual) ** (1 / 12) - 1
    valor = inicial
    for f in flujos:
        valor = (valor + f) * (1 + i)
    return valor


def comparar(
    prestamo_usd: float,
    cuota_usd: float,
    meses: int,
    plan: list[float],
    r_anual: float,
) -> dict:
    sin_deuda = futuro(0.0, plan, r_anual)
    plan_con_deuda = [a - cuota_usd for a in plan]
    con_deuda = futuro(prestamo_usd, plan_con_deuda, r_anual)
    return {
        "rendimiento_anual": r_anual,
        "sin_deuda": sin_deuda,
        "con_deuda": con_deuda,
        "diferencia": con_deuda - sin_deuda,
        "meses_en_rojo": sum(1 for a in plan_con_deuda if a < 0),
    }


def empate(prestamo_usd: float, cuota_usd: float, meses: int, plan: list[float]) -> float | None:
    """Rendimiento anual donde los dos caminos terminan iguales."""
    lo, hi = -0.95, 10.0
    f = lambda r: comparar(prestamo_usd, cuota_usd, meses, plan, r)["diferencia"]
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Endeudarse para invertir hoy vs aportar mes a mes")
    ap.add_argument("--prestamo", type=float, required=True, help="monto en moneda local")
    ap.add_argument("--cuota", type=float, required=True, help="cuota mensual en moneda local")
    ap.add_argument("--meses", type=int, required=True)
    ap.add_argument("--aporte", type=float, required=True, help="capacidad de ahorro mensual, en USD")
    ap.add_argument("--aporte-luego", type=float, help="capacidad de ahorro a partir de --cambio-mes")
    ap.add_argument("--cambio-mes", type=int, default=0)
    ap.add_argument("--gastos-del-prestamo", type=float, default=0.0,
                    help="parte del préstamo que NO se invierte (por ejemplo, un viaje)")
    ap.add_argument("--tc", type=float, default=1.0, help="moneda local por 1 USD")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    invertible = (args.prestamo - args.gastos_del_prestamo) / args.tc
    cuota_usd = args.cuota / args.tc
    plan = aportes(args.aporte, args.aporte_luego, args.cambio_mes, args.meses)

    filas = [comparar(invertible, cuota_usd, args.meses, plan, r) for r in ESCENARIOS]
    r_empate = empate(invertible, cuota_usd, args.meses, plan)
    total_sin = sum(plan)
    total_con = invertible + sum(a - cuota_usd for a in plan)

    if args.json:
        print(json.dumps(
            {"invertible": invertible, "cuota_usd": cuota_usd, "empate": r_empate,
             "total_aportado_sin_deuda": total_sin, "total_aportado_con_deuda": total_con,
             "escenarios": filas}, ensure_ascii=False, indent=2))
        return 0

    print(titulo(f"Adelantar {money(invertible, 'USD')} con deuda, o aportar mes a mes"))
    print(f"  Cuota: {money(cuota_usd, 'USD')} por mes durante {args.meses} meses")
    print(f"  Tu capacidad de ahorro: {money(args.aporte, 'USD')}/mes"
          + (f", {money(args.aporte_luego, 'USD')}/mes desde el mes {args.cambio_mes}"
             if args.aporte_luego else ""))
    if args.gastos_del_prestamo:
        print(f"  Del préstamo NO se invierte: {money(args.gastos_del_prestamo / args.tc, 'USD')}")

    print(subtitulo("Cuánto termina invertido en total"))
    print(f"  Sin deuda: {money(total_sin, 'USD')}")
    print(f"  Con deuda: {money(total_con, 'USD')}  "
          f"({money(total_sin - total_con, 'USD')} menos: eso son los intereses)")
    rojo = filas[0]["meses_en_rojo"]
    if rojo:
        print(f"  Atención: en {rojo} de los {args.meses} meses la cuota supera tu capacidad de "
              "ahorro. Esos meses no aportás nada y encima ponés plata de tu bolsillo.")

    print(subtitulo(f"Valor a los {args.meses} meses, según cómo rinda el activo"))
    print(f"  {'rendimiento':>12}{'sin deuda':>16}{'con deuda':>16}{'diferencia':>16}")
    for f in filas:
        print(f"  {f['rendimiento_anual'] * 100:>11.0f}%{money(f['sin_deuda'], 'USD'):>16}"
              f"{money(f['con_deuda'], 'USD'):>16}{money(f['diferencia'], 'USD'):>16}")

    print(subtitulo("El número que decide"))
    if r_empate is None:
        print("  Ningún rendimiento hace que endeudarse empate. Aportar mes a mes gana siempre.")
    else:
        print(f"  El activo tiene que rendir {pct(r_empate)} anual para que endeudarse empate "
              "con aportar mes a mes.")
        print("  Por encima de eso ganás por haber entrado antes. Por debajo, perdiste los "
              "intereses.")
    print("\n  Los dos caminos corren el mismo riesgo de mercado. La deuda no lo reduce: lo "
          "amplifica,\n  porque la cuota se paga aunque el activo caiga.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

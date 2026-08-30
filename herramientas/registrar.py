#!/usr/bin/env python3
"""Carga datos sin editar CSV a mano (valida antes de escribir).

Ejemplos:
    python3 herramientas/registrar.py saldo --cuenta openbank-remunerada --monto 3200
    python3 herramientas/registrar.py gasto --categoria supermercado --monto 480
    python3 herramientas/registrar.py ingreso --categoria sueldo --monto 4200
    python3 herramientas/registrar.py aporte --cuenta ontop --monto 300 --fecha 2026-08-15
    python3 herramientas/registrar.py cuenta --id openbank-remunerada \
        --nombre "Openbank saldo remunerado" --moneda USD --tasa 0.035 \
        --riesgo 1 --liquidez 1 --proposito liquidez --fuente "app, 2026-08-30"
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from comun import (
    COLUMNAS_MOVIMIENTOS,
    COLUMNAS_SALDOS,
    ErrorDatos,
    a_fecha,
    a_numero,
    agregar_csv,
    cuentas_por_id,
    dir_datos,
    escribir_json,
    leer_json,
)


def moneda_de_cuenta(cuenta_id: str, datos, por_defecto: str) -> str:
    cuentas = cuentas_por_id(leer_json("cuentas", datos))
    cta = cuentas.get(cuenta_id)
    if cta is None:
        raise ErrorDatos(
            f"La cuenta '{cuenta_id}' no existe en cuentas.json. "
            f"Creála primero con: registrar.py cuenta --id {cuenta_id} ..."
        )
    return (cta.get("moneda") or por_defecto).upper()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Registrar saldos, movimientos y cuentas")
    ap.add_argument("--datos", help="directorio de datos")
    sub = ap.add_subparsers(dest="comando", required=True)

    p_saldo = sub.add_parser("saldo", help="foto del saldo de una cuenta")
    p_saldo.add_argument("--cuenta", required=True)
    p_saldo.add_argument("--monto", required=True)
    p_saldo.add_argument("--moneda")
    p_saldo.add_argument("--fecha")
    p_saldo.add_argument("--nota", default="")

    for tipo in ("ingreso", "gasto", "aporte", "retiro", "rendimiento", "comision"):
        p = sub.add_parser(tipo, help=f"registrar un {tipo}")
        p.add_argument("--monto", required=True)
        p.add_argument("--categoria", default=tipo)
        p.add_argument("--cuenta", default="")
        p.add_argument("--moneda")
        p.add_argument("--fecha")
        p.add_argument("--descripcion", default="")

    p_cta = sub.add_parser("cuenta", help="alta o actualización de una cuenta")
    p_cta.add_argument("--id", required=True)
    p_cta.add_argument("--nombre")
    p_cta.add_argument("--tipo", choices=["banco", "broker", "fondo", "efectivo", "otro"])
    p_cta.add_argument("--moneda")
    p_cta.add_argument("--tasa", type=float, help="tasa anual en decimal (0.04 = 4%%)")
    p_cta.add_argument("--riesgo", type=int, choices=range(1, 6))
    p_cta.add_argument("--liquidez", type=int, help="días para disponer del dinero")
    p_cta.add_argument("--proposito", choices=["liquidez", "emergencia", "crecimiento", "meta"])
    p_cta.add_argument("--fuente", help="de dónde salió la tasa")
    p_cta.add_argument("--aporte-objetivo", type=float)
    p_cta.add_argument("--automatico", choices=["si", "no"])
    p_cta.add_argument("--baja", action="store_true", help="marcar la cuenta como inactiva")

    args = ap.parse_args(argv)
    datos = dir_datos(args.datos)
    hoy = date.today().isoformat()

    try:
        perfil = leer_json("perfil", datos)
        base = perfil.get("moneda_base", "USD")

        if args.comando == "saldo":
            fecha = a_fecha(args.fecha).isoformat() if args.fecha else hoy
            moneda = (args.moneda or moneda_de_cuenta(args.cuenta, datos, base)).upper()
            fila = {
                "fecha": fecha,
                "cuenta_id": args.cuenta,
                "saldo": f"{a_numero(args.monto, 'saldo'):.2f}",
                "moneda": moneda,
                "nota": args.nota,
            }
            agregar_csv("saldos", datos, fila, COLUMNAS_SALDOS)
            print(f"Saldo registrado: {args.cuenta} = {fila['saldo']} {moneda} ({fecha})")
            return 0

        if args.comando == "cuenta":
            doc = leer_json("cuentas", datos)
            cuentas = doc.setdefault("cuentas", [])
            cta = next((c for c in cuentas if c["id"] == args.id), None)
            nueva = cta is None
            if nueva:
                cta = {"id": args.id, "activa": True, "costos": {}, "notas": ""}
                cuentas.append(cta)
            campos = {
                "nombre": args.nombre,
                "tipo": args.tipo,
                "moneda": (args.moneda or "").upper() or None,
                "tasa_anual_estimada": args.tasa,
                "riesgo": args.riesgo,
                "liquidez_dias": args.liquidez,
                "proposito": args.proposito,
                "fuente_tasa": args.fuente,
                "aporte_mensual_objetivo": args.aporte_objetivo,
            }
            for k, v in campos.items():
                if v is not None:
                    cta[k] = v
            if args.automatico:
                cta["aporte_automatico"] = args.automatico == "si"
            if args.baja:
                cta["activa"] = False
            if args.tasa is not None:
                cta["verificado"] = hoy
            cta.setdefault("nombre", args.id)
            doc["actualizado"] = hoy
            escribir_json("cuentas", datos, doc)
            print(f"Cuenta {'creada' if nueva else 'actualizada'}: {cta['nombre']} ({args.id})")
            if args.tasa is not None and not cta.get("fuente_tasa"):
                print("Aviso: cargaste una tasa sin fuente. Usá --fuente para poder auditarla.")
            return 0

        # movimientos
        fecha = a_fecha(args.fecha).isoformat() if args.fecha else hoy
        moneda = args.moneda.upper() if args.moneda else (
            moneda_de_cuenta(args.cuenta, datos, base) if args.cuenta else base
        )
        fila = {
            "fecha": fecha,
            "tipo": args.comando,
            "categoria": args.categoria.strip().lower(),
            "monto": f"{a_numero(args.monto):.2f}",
            "moneda": moneda,
            "cuenta_id": args.cuenta,
            "descripcion": args.descripcion,
        }
        agregar_csv("movimientos", datos, fila, COLUMNAS_MOVIMIENTOS)
        print(
            f"{args.comando.capitalize()} registrado: {fila['monto']} {moneda} "
            f"({fila['categoria']}, {fecha})"
        )
        return 0
    except ErrorDatos as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

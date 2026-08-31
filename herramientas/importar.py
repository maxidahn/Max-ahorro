#!/usr/bin/env python3
"""Actualiza datos/cartera.json desde un CSV exportado (TradingView, ARQ, planilla).

Por defecto sólo muestra qué cambiaría. Para escribir, agregá --aplicar.

Uso:
    python3 herramientas/importar.py posiciones --archivo cartera.csv
    python3 herramientas/importar.py precios --archivo watchlist.csv --aplicar
    cat cartera.csv | python3 herramientas/importar.py posiciones

Modo 'posiciones': el archivo trae el valor de cada tenencia.
Modo 'precios':    el archivo trae el precio; el valor sale de precio x cantidad,
                   así que cada posición necesita 'cantidad' en cartera.json.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

from comun import ErrorDatos, a_numero, dir_datos, money, subtitulo, titulo

# Nombres de columna aceptados, en minúscula y sin acentos raros.
COLUMNAS = {
    "ticker": {"ticker", "symbol", "simbolo", "símbolo", "activo", "instrumento", "especie"},
    "valor": {"valor", "value", "market value", "importe", "total", "posicion", "posición"},
    "precio": {"precio", "price", "last", "ultimo", "último", "close", "cierre", "last price"},
    "cantidad": {"cantidad", "qty", "quantity", "shares", "nominales", "units", "acciones"},
    "pl": {"pl", "p/l", "p&l", "resultado", "gain", "profit", "unrealized", "ganancia"},
}


def normalizar_ticker(bruto: str) -> str:
    """'NASDAQ:GOOGL' -> 'GOOGL'. TradingView exporta el mercado como prefijo."""
    t = (bruto or "").strip().upper()
    if ":" in t:
        t = t.split(":")[-1]
    return t.strip()


def mapear_columnas(cabeceras: list[str]) -> dict[str, str]:
    mapa = {}
    for h in cabeceras:
        clave = (h or "").strip().lower()
        for campo, alias in COLUMNAS.items():
            if clave in alias and campo not in mapa:
                mapa[campo] = h
    return mapa


def leer_filas(texto: str) -> tuple[list[dict], dict[str, str]]:
    # csv.Sniffer se confunde con una sola columna; probamos separadores comunes.
    muestra = texto[:2000]
    delimitador = max([",", ";", "\t"], key=muestra.count)
    lector = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    if not lector.fieldnames:
        raise ErrorDatos("El archivo no tiene encabezados.")
    mapa = mapear_columnas(lector.fieldnames)
    if "ticker" not in mapa:
        raise ErrorDatos(
            "No encontré una columna de ticker. Encabezados leídos: "
            + ", ".join(lector.fieldnames)
        )
    filas = [f for f in lector if (f.get(mapa["ticker"]) or "").strip()]
    return filas, mapa


def calcular_cambios(cartera: dict, filas: list[dict], mapa: dict, modo: str) -> dict:
    posiciones = {p["ticker"].upper(): p for p in cartera.get("posiciones", [])}
    cambios, nuevos, sin_cantidad, ignorados = [], [], [], []
    vistos: set[str] = set()

    for fila in filas:
        ticker = normalizar_ticker(fila[mapa["ticker"]])
        if not ticker:
            continue
        vistos.add(ticker)
        pos = posiciones.get(ticker)

        if modo == "posiciones":
            if "valor" not in mapa:
                raise ErrorDatos(
                    "El archivo no tiene columna de valor. Para un archivo de precios usá el modo "
                    "'precios'."
                )
            bruto = fila[mapa["valor"]]
            if not (bruto or "").strip():
                continue
            valor_nuevo = a_numero(bruto, f"valor de {ticker}")
        else:
            if "precio" not in mapa:
                raise ErrorDatos("El archivo no tiene columna de precio.")
            precio = a_numero(fila[mapa["precio"]], f"precio de {ticker}")
            cantidad = None
            if "cantidad" in mapa and (fila[mapa["cantidad"]] or "").strip():
                cantidad = a_numero(fila[mapa["cantidad"]], f"cantidad de {ticker}")
            elif pos and pos.get("cantidad") is not None:
                cantidad = float(pos["cantidad"])
            if cantidad is None:
                if pos:
                    sin_cantidad.append(ticker)
                else:
                    ignorados.append(ticker)
                continue
            valor_nuevo = precio * cantidad

        pl_nuevo = None
        if "pl" in mapa and (fila[mapa["pl"]] or "").strip():
            pl_nuevo = a_numero(fila[mapa["pl"]], f"resultado de {ticker}")

        if pos is None:
            nuevos.append({"ticker": ticker, "valor": round(valor_nuevo, 2), "pl": pl_nuevo})
            continue
        cambios.append(
            {
                "ticker": ticker,
                "anterior": float(pos["valor"]),
                "nuevo": round(valor_nuevo, 2),
                "delta": round(valor_nuevo - float(pos["valor"]), 2),
                "pl": pl_nuevo,
            }
        )

    ausentes = [t for t in posiciones if t not in vistos and t != "POR_CONFIRMAR"]
    return {
        "cambios": cambios,
        "nuevos": nuevos,
        "sin_cantidad": sin_cantidad,
        "ignorados": ignorados,
        "ausentes": ausentes,
    }


def aplicar(cartera: dict, resultado: dict, hoy: str) -> dict:
    posiciones = {p["ticker"].upper(): p for p in cartera["posiciones"]}
    for c in resultado["cambios"]:
        pos = posiciones[c["ticker"]]
        pos["valor"] = c["nuevo"]
        if c["pl"] is not None:
            pos["pl"] = c["pl"]
    for n in resultado["nuevos"]:
        cartera["posiciones"].append(
            {
                "ticker": n["ticker"],
                "nombre": n["ticker"],
                "valor": n["valor"],
                "pl": n["pl"],
                "clase": "por_confirmar",
                "liquidez": None,
                "peso_en_nucleo": None,
                "notas": f"Importado el {hoy}. Falta clasificar (clase, liquidez).",
            }
        )
    cartera["actualizado"] = hoy
    return cartera


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Importar valores de cartera desde un CSV")
    ap.add_argument("modo", choices=["posiciones", "precios"])
    ap.add_argument("--archivo", help="CSV a importar (si falta, se lee de la entrada estándar)")
    ap.add_argument("--datos", help="directorio de datos")
    ap.add_argument("--aplicar", action="store_true", help="escribir los cambios en cartera.json")
    ap.add_argument("--hoy", help="fecha a registrar (AAAA-MM-DD)")
    args = ap.parse_args(argv)

    datos = dir_datos(args.datos)
    archivo_cartera = datos / "cartera.json"
    try:
        if not archivo_cartera.exists():
            raise ErrorDatos(f"Falta {archivo_cartera}.")
        texto = (
            Path(args.archivo).read_text(encoding="utf-8-sig")
            if args.archivo
            else sys.stdin.read()
        )
        if not texto.strip():
            raise ErrorDatos("No llegó ningún contenido para importar.")
        cartera = json.loads(archivo_cartera.read_text(encoding="utf-8"))
        filas, mapa = leer_filas(texto)
        r = calcular_cambios(cartera, filas, mapa, args.modo)
    except ErrorDatos as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"Error: no existe {exc.filename}", file=sys.stderr)
        return 1

    moneda = cartera.get("moneda", "USD")
    print(titulo(f"Importación en modo {args.modo}" + ("" if args.aplicar else " (simulación)")))
    print(f"Columnas detectadas: {', '.join(f'{k} <- {v}' for k, v in mapa.items())}")

    if r["cambios"]:
        print(subtitulo("Posiciones a actualizar"))
        for c in r["cambios"]:
            signo = "+" if c["delta"] >= 0 else "−"
            print(
                f"  {c['ticker']:<9}{money(c['anterior'], moneda):>14} → "
                f"{money(c['nuevo'], moneda):>14}   {signo}{money(abs(c['delta']), moneda)}"
            )
        total_delta = sum(c["delta"] for c in r["cambios"])
        print(f"\n  Variación total de lo actualizado: {money(total_delta, moneda)}")
    else:
        print("\n  Ninguna posición conocida coincide con el archivo.")

    if r["nuevos"]:
        print(subtitulo("Posiciones nuevas (quedan sin clasificar)"))
        for n in r["nuevos"]:
            print(f"  {n['ticker']:<9}{money(n['valor'], moneda):>14}")
        print("  Asignales clase y liquidez en cartera.json: sin eso no entran en las reglas.")
    if r["sin_cantidad"]:
        print(subtitulo("Sin cantidad cargada"))
        print("  " + ", ".join(r["sin_cantidad"]))
        print("  Agregá 'cantidad' a esas posiciones en cartera.json para poder valuarlas por precio.")
    if r["ignorados"]:
        print(subtitulo("Ignorados"))
        print("  " + ", ".join(r["ignorados"]) + " (no están en la cartera y el archivo no trae cantidad)")
    if r["ausentes"]:
        print(subtitulo("En la cartera pero no en el archivo"))
        print("  " + ", ".join(r["ausentes"]) + " — se dejan como estaban.")

    if not args.aplicar:
        print("\nSimulación: no se escribió nada. Repetí con --aplicar para guardar.")
        return 0

    hoy = args.hoy or date.today().isoformat()
    cartera = aplicar(cartera, r, hoy)
    archivo_cartera.write_text(
        json.dumps(cartera, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\ncartera.json actualizado ({hoy}). Revisá el informe: python3 herramientas/cartera.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

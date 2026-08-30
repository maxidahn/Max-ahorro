#!/usr/bin/env python3
"""Analiza la cartera y propone órdenes según tu política de inversión.

No predice precios ni recomienda activos: aplica las reglas que están en
datos/objetivo.json a los números que están en datos/cartera.json.

Uso:
    python3 herramientas/cartera.py                       # informe
    python3 herramientas/cartera.py aporte --monto 1000   # cómo colocar plata nueva
    python3 herramientas/cartera.py orden --tipo compra --ticker NVDA --monto 500 --clase accion
    python3 herramientas/cartera.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from comun import ErrorDatos, barra, dir_datos, money, pct, subtitulo, titulo

ARCHIVO_CARTERA = "cartera.json"
ARCHIVO_OBJETIVO = "objetivo.json"


def _leer(nombre: str, datos: Path) -> dict:
    archivo = datos / nombre
    if not archivo.exists():
        raise ErrorDatos(f"Falta {archivo}.")
    try:
        return json.loads(archivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ErrorDatos(f"{archivo} no es JSON válido: {exc}") from exc


def analizar(datos: Path) -> dict:
    cartera = _leer(ARCHIVO_CARTERA, datos)
    politica = _leer(ARCHIVO_OBJETIVO, datos)
    reglas = politica.get("reglas", {})
    objetivo = politica.get("objetivo", {})
    moneda = cartera.get("moneda", "USD")

    posiciones = [dict(p) for p in cartera.get("posiciones", [])]
    total = sum(float(p["valor"]) for p in posiciones) + float(cartera.get("efectivo") or 0)
    if total <= 0:
        raise ErrorDatos("La cartera no tiene valor: cargá posiciones en cartera.json.")

    declarado = cartera.get("total_declarado")
    avisos: list[str] = []
    if declarado and abs(float(declarado) - total) > 1:
        avisos.append(
            f"Las posiciones suman {money(total, moneda)} pero el total declarado es "
            f"{money(float(declarado), moneda)}: faltan cargar {money(float(declarado) - total, moneda)}."
        )

    for p in posiciones:
        p["valor"] = float(p["valor"])
        p["peso"] = p["valor"] / total
        p["clase"] = p.get("clase") or "sin_clase"
        p["costo"] = p["valor"] - float(p["pl"]) if p.get("pl") is not None else None
        p["pl_pct"] = (
            float(p["pl"]) / p["costo"] if p.get("pl") is not None and p["costo"] else None
        )
    posiciones.sort(key=lambda p: p["valor"], reverse=True)

    # --- composición por clase -------------------------------------------
    clases = {}
    for p in posiciones:
        c = clases.setdefault(p["clase"], {"valor": 0.0, "posiciones": []})
        c["valor"] += p["valor"]
        c["posiciones"].append(p["ticker"])
    efectivo = float(cartera.get("efectivo") or 0)
    if efectivo:
        clases.setdefault("efectivo", {"valor": 0.0, "posiciones": []})["valor"] += efectivo

    composicion = []
    for clase in dict.fromkeys(list(objetivo) + list(clases)):
        valor = clases.get(clase, {}).get("valor", 0.0)
        obj = float(objetivo.get(clase, 0.0))
        actual = valor / total
        composicion.append(
            {
                "clase": clase,
                "valor": valor,
                "peso": actual,
                "objetivo": obj,
                "desvio_pp": (actual - obj) * 100,
                "ajuste": (obj - actual) * total,
                "posiciones": clases.get(clase, {}).get("posiciones", []),
            }
        )
    composicion.sort(key=lambda c: c["valor"], reverse=True)

    # --- reglas -----------------------------------------------------------
    alertas: list[dict] = []
    max_pos = reglas.get("max_por_posicion_pct")
    exentas = set(reglas.get("clases_exentas_del_maximo") or [])
    max_accion = reglas.get("max_por_accion_individual_pct")
    min_pos = reglas.get("min_por_posicion_pct")
    tolerancia = float(reglas.get("tolerancia_pp") or 5)

    for p in posiciones:
        if p["clase"] == "por_confirmar":
            alertas.append(
                {
                    "nivel": "bloqueante",
                    "regla": "datos",
                    "texto": f"{money(p['valor'], moneda)} sin identificar ({p['peso'] * 100:.1f}% de la cartera). "
                    "No se puede decidir sobre lo que no está cargado.",
                }
            )
            continue
        if max_pos and p["clase"] not in exentas and p["peso"] > float(max_pos):
            exceso = (p["peso"] - float(max_pos)) * total
            alertas.append(
                {
                    "nivel": "alto",
                    "regla": "max_por_posicion_pct",
                    "texto": f"{p['ticker']} pesa {pct(p['peso'])}, sobre tu techo de {pct(float(max_pos))}: "
                    f"{money(exceso, moneda)} por encima.",
                }
            )
        if max_accion and p["clase"] == "accion" and p["peso"] > float(max_accion):
            exceso = (p["peso"] - float(max_accion)) * total
            alertas.append(
                {
                    "nivel": "alto",
                    "regla": "max_por_accion_individual_pct",
                    "texto": f"{p['ticker']} es una acción suelta con {pct(p['peso'])} de la cartera, sobre el "
                    f"techo de {pct(float(max_accion))}: {money(exceso, moneda)} de más.",
                }
            )
        if min_pos and p["peso"] < float(min_pos):
            alertas.append(
                {
                    "nivel": "medio",
                    "regla": "min_por_posicion_pct",
                    "texto": f"{p['ticker']} pesa {pct(p['peso'])} ({money(p['valor'], moneda)}): por debajo del "
                    f"mínimo de {pct(float(min_pos))}. Un ±10% en {p['ticker']} mueve tu cartera "
                    f"{p['peso'] * 10:.2f}%.",
                }
            )
        if p.get("liquidez") == "baja":
            alertas.append(
                {
                    "nivel": "medio",
                    "regla": "liquidez",
                    "texto": f"{p['ticker']}: {money(p['valor'], moneda)} en un activo que no se vende cuando querés.",
                }
            )
        if p.get("verificar"):
            alertas.append(
                {"nivel": "alto", "regla": "verificar", "texto": f"{p['ticker']}: {p['verificar']}"}
            )

    for c in composicion:
        if abs(c["desvio_pp"]) > tolerancia:
            direccion = "por encima" if c["desvio_pp"] > 0 else "por debajo"
            alertas.append(
                {
                    "nivel": "medio",
                    "regla": "tolerancia_pp",
                    "texto": f"Clase '{c['clase']}': {pct(c['peso'])} contra un objetivo de {pct(c['objetivo'])}, "
                    f"{abs(c['desvio_pp']):.1f} pp {direccion} (banda ±{tolerancia:.0f} pp).",
                }
            )

    if reglas.get("comision_por_operacion") is None and reglas.get("comision_pct") is None:
        alertas.append(
            {
                "nivel": "bloqueante",
                "regla": "costos",
                "texto": "No está cargada la comisión por operación en objetivo.json. Sin ese dato no se "
                "puede saber si una orden vale la pena ni si conviene el plan sin comisiones.",
            }
        )
    if not politica.get("confirmado_por_max"):
        alertas.append(
            {
                "nivel": "bloqueante",
                "regla": "politica",
                "texto": "objetivo.json todavía tiene la asignación de ejemplo (confirmado_por_max: false). "
                "Revisala y confirmala antes de usar sus órdenes.",
            }
        )

    orden_nivel = {"bloqueante": 0, "alto": 1, "medio": 2}
    alertas.sort(key=lambda a: orden_nivel.get(a["nivel"], 3))

    # --- concentración y resultado ----------------------------------------
    top1 = posiciones[0]["peso"] if posiciones else 0
    top3 = sum(p["peso"] for p in posiciones[:3])
    con_pl = [p for p in posiciones if p.get("pl") is not None]
    pl_total = sum(float(p["pl"]) for p in con_pl)
    costo_total = sum(p["costo"] for p in con_pl if p["costo"])
    pl_declarado = cartera.get("pl_declarado")
    pl_implicito = None
    if pl_declarado is not None:
        pl_implicito = float(pl_declarado) - pl_total
        if abs(pl_implicito) > 1:
            avisos.append(
                f"Las posiciones cargadas acumulan {money(pl_total, moneda)} y la app declara "
                f"{money(float(pl_declarado), moneda)}: las que faltan cargar suman "
                f"{money(pl_implicito, moneda)}."
            )
    solapamiento = [
        {
            "ticker": p["ticker"],
            "directo": p["valor"],
            "via_nucleo": p["peso_en_nucleo"],
        }
        for p in posiciones
        if p.get("peso_en_nucleo")
    ]

    return {
        "moneda": moneda,
        "total": total,
        "efectivo": efectivo,
        "actualizado": cartera.get("actualizado"),
        "posiciones": posiciones,
        "composicion": composicion,
        "alertas": alertas,
        "avisos": avisos,
        "top1": top1,
        "top3": top3,
        "pl_total": pl_total,
        "pl_pct_sobre_costo": pl_total / costo_total if costo_total else None,
        "posiciones_sin_pl": [p["ticker"] for p in posiciones if p.get("pl") is None],
        "pl_declarado": pl_declarado,
        "pl_implicito_no_cargado": pl_implicito,
        "solapamiento": solapamiento,
        "reglas": reglas,
        "politica_confirmada": bool(politica.get("confirmado_por_max")),
        "prohibiciones": politica.get("prohibiciones", []),
    }


def costo_orden(monto: float, reglas: dict) -> float:
    fija = reglas.get("comision_por_operacion")
    variable = reglas.get("comision_pct")
    costo = 0.0
    if fija is not None:
        costo += float(fija)
    if variable is not None:
        costo += monto * float(variable)
    return costo


def ordenes_de_aporte(a: dict, monto: float) -> list[dict]:
    """Reparte dinero nuevo entre las clases que están por debajo del objetivo."""
    reglas = a["reglas"]
    total_final = a["total"] + monto
    deficits = []
    for c in a["composicion"]:
        if c["objetivo"] <= 0:
            continue
        falta = c["objetivo"] * total_final - c["valor"]
        if falta > 0:
            deficits.append((c, falta))
    suma = sum(f for _, f in deficits)
    ordenes = []
    for c, falta in deficits:
        importe = monto * falta / suma if suma else 0
        if importe <= 0:
            continue
        destino = c["posiciones"][0] if len(c["posiciones"]) == 1 else "a elegir dentro de la clase"
        comision = costo_orden(importe, reglas)
        minima = float(reglas.get("orden_minima") or 0)
        tope = reglas.get("max_comision_sobre_orden")
        problemas = []
        if importe < minima:
            problemas.append(f"por debajo de la orden mínima ({money(minima, a['moneda'])})")
        if tope and importe and comision / importe > float(tope):
            problemas.append(
                f"la comisión sería {pct(comision / importe)} del importe, sobre tu tope de {pct(float(tope))}"
            )
        ordenes.append(
            {
                "clase": c["clase"],
                "destino": destino,
                "importe": round(importe, 2),
                "comision_estimada": round(comision, 2) if comision else None,
                "peso_resultante": (c["valor"] + importe) / total_final,
                "problemas": problemas,
            }
        )
    ordenes.sort(key=lambda o: o["importe"], reverse=True)
    return ordenes


def evaluar_orden(a: dict, tipo: str, ticker: str, monto: float, clase: str | None) -> dict:
    reglas = a["reglas"]
    moneda = a["moneda"]
    actual = next((p for p in a["posiciones"] if p["ticker"].upper() == ticker.upper()), None)
    valor_actual = actual["valor"] if actual else 0.0
    clase = clase or (actual["clase"] if actual else "accion")
    signo = 1 if tipo == "compra" else -1
    valor_nuevo = valor_actual + signo * monto
    # En una compra entra plata nueva; en una venta el total no cambia, la plata pasa a efectivo.
    total_nuevo = a["total"] + monto if tipo == "compra" else a["total"]
    peso_nuevo = max(valor_nuevo, 0) / total_nuevo if total_nuevo else 0

    problemas, notas = [], []
    if tipo == "venta" and monto > valor_actual + 0.01:
        problemas.append(
            f"Estás vendiendo {money(monto, moneda)} de una posición de {money(valor_actual, moneda)}."
        )
    comision = costo_orden(monto, reglas)
    if comision:
        notas.append(
            f"Comisión estimada {money(comision, moneda)} = {pct(comision / monto)} del importe."
        )
        tope = reglas.get("max_comision_sobre_orden")
        if tope and comision / monto > float(tope):
            problemas.append(
                f"La comisión ({pct(comision / monto)}) supera tu tope de {pct(float(tope))}."
            )
    else:
        problemas.append("No hay comisión cargada en objetivo.json: no se puede evaluar el costo.")

    minima = float(reglas.get("orden_minima") or 0)
    if monto < minima:
        problemas.append(f"Por debajo de tu orden mínima de {money(minima, moneda)}.")

    if tipo == "compra":
        max_pos = reglas.get("max_por_posicion_pct")
        exentas = set(reglas.get("clases_exentas_del_maximo") or [])
        max_accion = reglas.get("max_por_accion_individual_pct")
        if max_pos and clase not in exentas and peso_nuevo > float(max_pos):
            problemas.append(
                f"Después de la compra {ticker.upper()} pesaría {pct(peso_nuevo)}, sobre tu techo de "
                f"{pct(float(max_pos))}."
            )
        if max_accion and clase == "accion" and peso_nuevo > float(max_accion):
            problemas.append(
                f"Como acción individual quedaría en {pct(peso_nuevo)}, sobre el techo de "
                f"{pct(float(max_accion))}."
            )
        min_pos = reglas.get("min_por_posicion_pct")
        if min_pos and peso_nuevo < float(min_pos):
            problemas.append(
                f"Quedaría en {pct(peso_nuevo)}, por debajo de tu mínimo de {pct(float(min_pos))}: "
                "una posición que no mueve la aguja."
            )
        if a["efectivo"] < monto:
            notas.append(
                f"Tenés {money(a['efectivo'], moneda)} en efectivo: la compra requiere depositar o vender antes."
            )

    if actual and actual.get("pl_pct") is not None:
        notas.append(
            f"{ticker.upper()} acumula {money(float(actual['pl']), moneda)} "
            f"({pct(actual['pl_pct'])} sobre su costo). El resultado pasado no dice nada sobre el próximo "
            "movimiento; no lo uses como argumento."
        )

    return {
        "tipo": tipo,
        "ticker": ticker.upper(),
        "monto": monto,
        "clase": clase,
        "peso_actual": valor_actual / a["total"] if a["total"] else 0,
        "peso_resultante": peso_nuevo,
        "comision_estimada": round(comision, 2) if comision else None,
        "problemas": problemas,
        "notas": notas,
        "veredicto": "revisar" if problemas else "cumple las reglas",
    }


# ------------------------------------------------------------------ salida


def imprimir_informe(a: dict) -> None:
    m = a["moneda"]
    print(titulo(f"Cartera — {a['actualizado'] or 's/f'}"))
    print(f"Total {money(a['total'], m)} · efectivo {money(a['efectivo'], m)}")
    if a["pl_pct_sobre_costo"] is not None:
        print(
            f"Resultado acumulado: {money(a['pl_total'], m)} = {pct(a['pl_pct_sobre_costo'])} "
            "sobre el costo de las posiciones con dato."
        )
    if a["posiciones_sin_pl"]:
        print(f"(sin resultado cargado: {', '.join(a['posiciones_sin_pl'])})")

    print(subtitulo("Composición por clase"))
    print(f"  {'clase':<14}{'actual':>10}{'objetivo':>10}{'desvío':>10}   {'ajuste':>12}")
    for c in a["composicion"]:
        ajuste = money(c["ajuste"], m) if abs(c["ajuste"]) >= 1 else "—"
        print(
            f"  {c['clase'][:14]:<14}{pct(c['peso']):>10}{pct(c['objetivo']):>10}"
            f"{c['desvio_pp']:>+9.1f}pp   {ajuste:>12}"
        )

    print(subtitulo("Posiciones"))
    for p in a["posiciones"]:
        resultado = (
            f"{money(float(p['pl']), m)} ({pct(p['pl_pct'])})" if p.get("pl_pct") is not None else "s/d"
        )
        print(
            f"  {p['ticker'][:9]:<9}{money(p['valor'], m):>14}  {barra(p['peso'], 10)} "
            f"{p['peso'] * 100:>5.1f}%  {p['clase']:<12} {resultado}"
        )
    print(
        f"\n  Concentración: la mayor posición es {pct(a['top1'])} de la cartera; "
        f"las tres mayores suman {pct(a['top3'])}."
    )

    if a["solapamiento"]:
        print(subtitulo("Solapamiento con el núcleo"))
        for s in a["solapamiento"]:
            print(f"  {s['ticker']}: además de la posición directa, pesa {pct(s['via_nucleo'])} del núcleo.")

    if a["alertas"]:
        print(subtitulo("Reglas de tu política que no se están cumpliendo"))
        for al in a["alertas"]:
            print(f"  [{al['nivel']}] {al['texto']}")

    if a["avisos"]:
        print(subtitulo("Avisos"))
        for av in a["avisos"]:
            print(f"  • {av}")

    print(
        "\nEsto aplica tus propias reglas a tus propios números. No es una recomendación de compra "
        "o venta ni una opinión sobre ningún activo."
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Análisis de cartera y órdenes según tu política")
    ap.add_argument("--datos", help="directorio de datos")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="comando")

    p_ap = sub.add_parser("aporte", help="cómo colocar dinero nuevo sin vender nada")
    p_ap.add_argument("--monto", type=float, required=True)

    p_or = sub.add_parser("orden", help="evaluar una compra o venta puntual")
    p_or.add_argument("--tipo", choices=["compra", "venta"], required=True)
    p_or.add_argument("--ticker", required=True)
    p_or.add_argument("--monto", type=float, required=True)
    p_or.add_argument("--clase")

    args = ap.parse_args(argv)

    try:
        a = analizar(dir_datos(args.datos))
    except ErrorDatos as exc:
        print(f"Error en los datos: {exc}", file=sys.stderr)
        return 1

    m = a["moneda"]

    if args.comando == "aporte":
        ordenes = ordenes_de_aporte(a, args.monto)
        if args.json:
            print(json.dumps({"aporte": args.monto, "ordenes": ordenes}, ensure_ascii=False, indent=2))
            return 0
        print(titulo(f"Cómo colocar {money(args.monto, m)} sin vender nada"))
        if not ordenes:
            print("  Ninguna clase está por debajo del objetivo: no hace falta comprar nada.")
        for o in ordenes:
            print(f"\n  {money(o['importe'], m)} → {o['clase']} ({o['destino']})")
            print(f"     la clase quedaría en {pct(o['peso_resultante'])}")
            if o["comision_estimada"]:
                print(f"     comisión estimada {money(o['comision_estimada'], m)}")
            for pr in o["problemas"]:
                print(f"     ⚠ {pr}")
        print(
            "\n  Comprar lo que falta con plata nueva evita vender, evita el impuesto a la ganancia "
            "y evita una comisión de venta."
        )
        return 0

    if args.comando == "orden":
        ev = evaluar_orden(a, args.tipo, args.ticker, args.monto, args.clase)
        if args.json:
            print(json.dumps(ev, ensure_ascii=False, indent=2))
            return 0
        print(titulo(f"{ev['tipo'].capitalize()} de {money(ev['monto'], m)} en {ev['ticker']}"))
        print(f"  Peso actual: {pct(ev['peso_actual'])} → resultante: {pct(ev['peso_resultante'])}")
        for n in ev["notas"]:
            print(f"  · {n}")
        if ev["problemas"]:
            print("\n  Contra tus reglas:")
            for pr in ev["problemas"]:
                print(f"     ⚠ {pr}")
        else:
            print("\n  No rompe ninguna de tus reglas.")
        if a["prohibiciones"]:
            print("\n  Antes de mandarla, releé lo que vos mismo escribiste:")
            for pr in a["prohibiciones"]:
                print(f"     – {pr}")
        print(
            "\n  Si la hacés, registrala: python3 herramientas/registrar.py operacion "
            f"--tipo {ev['tipo']} --ticker {ev['ticker']} --monto {ev['monto']:.2f} --motivo \"...\""
        )
        return 0

    if args.json:
        print(json.dumps(a, ensure_ascii=False, indent=2))
    else:
        imprimir_informe(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

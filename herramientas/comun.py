"""Utilidades compartidas por las herramientas de Max-ahorro.

Sólo biblioteca estándar: no hace falta instalar nada.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS_POR_DEFECTO = RAIZ / "datos"

ARCHIVOS = {
    "perfil": "perfil.json",
    "cuentas": "cuentas.json",
    "metas": "metas.json",
    "saldos": "saldos.csv",
    "movimientos": "movimientos.csv",
}

COLUMNAS_SALDOS = ["fecha", "cuenta_id", "saldo", "moneda", "nota"]
COLUMNAS_MOVIMIENTOS = [
    "fecha",
    "tipo",
    "categoria",
    "monto",
    "moneda",
    "cuenta_id",
    "descripcion",
]
TIPOS_MOVIMIENTO = {"ingreso", "gasto", "aporte", "retiro", "rendimiento", "comision"}


class ErrorDatos(Exception):
    """Los datos del proyecto están incompletos o mal formados."""


# --------------------------------------------------------------------------- IO


def dir_datos(ruta: str | os.PathLike | None = None) -> Path:
    return Path(ruta).resolve() if ruta else DATOS_POR_DEFECTO


def ruta(clave: str, datos: Path) -> Path:
    return datos / ARCHIVOS[clave]


def leer_json(clave: str, datos: Path) -> dict:
    archivo = ruta(clave, datos)
    if not archivo.exists():
        raise ErrorDatos(f"Falta {archivo}. Copiá la plantilla de datos/ o corré con --datos.")
    try:
        return json.loads(archivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ErrorDatos(f"{archivo} no es JSON válido: {exc}") from exc


def escribir_json(clave: str, datos: Path, contenido: dict) -> None:
    archivo = ruta(clave, datos)
    archivo.write_text(
        json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def leer_csv(clave: str, datos: Path) -> list[dict]:
    archivo = ruta(clave, datos)
    if not archivo.exists():
        return []
    with archivo.open(encoding="utf-8", newline="") as fh:
        filas = [f for f in csv.DictReader(fh) if any((v or "").strip() for v in f.values())]
    return filas


def agregar_csv(clave: str, datos: Path, fila: dict, columnas: list[str]) -> Path:
    archivo = ruta(clave, datos)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not archivo.exists() or archivo.stat().st_size == 0
    with archivo.open("a", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas)
        if nuevo:
            escritor.writeheader()
        escritor.writerow({c: fila.get(c, "") for c in columnas})
    return archivo


# ---------------------------------------------------------------- conversiones


def a_fecha(texto: str) -> date:
    try:
        return datetime.strptime(texto.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError) as exc:
        raise ErrorDatos(f"Fecha inválida '{texto}': se espera AAAA-MM-DD") from exc


def a_numero(texto, campo: str = "monto") -> float:
    """Convierte a float aceptando formato argentino y formato inglés.

    1.234,56 -> 1234.56    (separador de miles + coma decimal)
    1234.56  -> 1234.56    (punto decimal)
    4.200    -> 4200.0     (punto + exactamente 3 dígitos = miles)
    0,5      -> 0.5
    0.035    -> 0.035      (parte entera "0": el punto es decimal)

    El único caso ambiguo es "X.YYY". Se resuelve como miles, que es lo que
    escribe alguien en Argentina; para decimales de 3 dígitos usá la coma.
    """
    if isinstance(texto, (int, float)):
        return float(texto)
    limpio = (texto or "").strip().replace("$", "").replace(" ", "")
    if not limpio:
        raise ErrorDatos(f"Falta el {campo}")
    negativo = limpio.startswith("-")
    limpio = limpio.lstrip("+-")
    if "," in limpio:
        # La coma manda: siempre es el separador decimal.
        limpio = limpio.replace(".", "").replace(",", ".")
    elif limpio.count(".") > 1:
        limpio = limpio.replace(".", "")
    elif "." in limpio:
        entero, _, decimal = limpio.partition(".")
        if len(decimal) == 3 and decimal.isdigit() and entero not in ("", "0"):
            limpio = entero + decimal
    try:
        valor = float(limpio)
    except ValueError as exc:
        raise ErrorDatos(f"{campo} inválido: '{texto}'") from exc
    return -valor if negativo else valor


class Cambio:
    """Convierte montos a la moneda base usando el tipo de cambio del perfil.

    perfil["tipo_cambio"] mapea moneda -> unidades de esa moneda por 1 unidad
    de la moneda base (ej. con base USD: {"USD": 1, "ARS": 1450}).
    """

    def __init__(self, perfil: dict):
        self.base = perfil.get("moneda_base", "USD")
        self.tasas = {
            k.upper(): float(v)
            for k, v in (perfil.get("tipo_cambio") or {}).items()
            if v not in (None, "", 0)
        }
        self.tasas.setdefault(self.base, 1.0)
        self.actualizado = perfil.get("tipo_cambio_actualizado")
        self.faltantes: set[str] = set()

    def a_base(self, monto: float, moneda: str) -> float:
        moneda = (moneda or self.base).upper()
        tasa = self.tasas.get(moneda)
        if not tasa:
            self.faltantes.add(moneda)
            return 0.0
        return monto / tasa

    def dias_desde_actualizacion(self, hoy: date | None = None) -> int | None:
        if not self.actualizado:
            return None
        return ((hoy or date.today()) - a_fecha(self.actualizado)).days


# ------------------------------------------------------------------- consultas


def cuentas_por_id(cuentas: dict) -> dict:
    return {c["id"]: c for c in cuentas.get("cuentas", [])}


def saldos_actuales(saldos: list[dict], corte: date | None = None) -> dict:
    """Último saldo registrado de cada cuenta (opcionalmente a una fecha de corte)."""
    ultimo: dict[str, dict] = {}
    for fila in saldos:
        f = a_fecha(fila["fecha"])
        if corte and f > corte:
            continue
        cid = fila["cuenta_id"].strip()
        if cid not in ultimo or f >= a_fecha(ultimo[cid]["fecha"]):
            ultimo[cid] = fila
    return ultimo


def mes_de(f: date) -> str:
    return f.strftime("%Y-%m")


def meses_hacia_atras(n: int, desde: date | None = None) -> list[str]:
    hoy = desde or date.today()
    meses, y, m = [], hoy.year, hoy.month
    for _ in range(n):
        meses.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(meses))


def flujo_mensual(movimientos: list[dict], cambio: Cambio, meses: list[str]) -> dict:
    """Suma por mes y tipo de movimiento, en moneda base."""
    resultado = {m: {t: 0.0 for t in TIPOS_MOVIMIENTO} for m in meses}
    categorias: dict[str, float] = {}
    for mov in movimientos:
        f = a_fecha(mov["fecha"])
        clave = mes_de(f)
        if clave not in resultado:
            continue
        tipo = (mov.get("tipo") or "").strip().lower()
        if tipo not in TIPOS_MOVIMIENTO:
            raise ErrorDatos(
                f"Tipo de movimiento desconocido '{tipo}' ({mov.get('fecha')}). "
                f"Válidos: {', '.join(sorted(TIPOS_MOVIMIENTO))}"
            )
        monto = cambio.a_base(abs(a_numero(mov["monto"])), mov.get("moneda"))
        resultado[clave][tipo] += monto
        if tipo in ("gasto", "comision"):
            cat = (mov.get("categoria") or "sin categoría").strip().lower()
            categorias[cat] = categorias.get(cat, 0.0) + monto
    return {"por_mes": resultado, "por_categoria": categorias}


def promedio(valores: list[float]) -> float:
    vals = [v for v in valores]
    return sum(vals) / len(vals) if vals else 0.0


# ------------------------------------------------------------------- salida


def money(monto: float, moneda: str = "USD") -> str:
    return f"{moneda} {monto:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def titulo(texto: str) -> str:
    return f"\n{texto}\n{'=' * len(texto)}"


def subtitulo(texto: str) -> str:
    return f"\n{texto}\n{'-' * len(texto)}"


def barra(fraccion: float, ancho: int = 24) -> str:
    lleno = max(0, min(ancho, round(fraccion * ancho)))
    return "█" * lleno + "·" * (ancho - lleno)

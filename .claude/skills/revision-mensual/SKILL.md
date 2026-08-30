---
name: revision-mensual
description: Revisión mensual del ahorro de Max — actualiza saldos, recalcula tasa de ahorro y rendimientos, y deja el plan del mes escrito en revisiones/. Usar cuando Max pida "revisión mensual", "cierre de mes", "actualizar el ahorro" o cuando arranque un mes nuevo.
---

# Revisión mensual

Ritual de cierre de mes. Toma entre 5 y 10 minutos de ida y vuelta con Max.

## 1. Actualizar la realidad (antes de calcular nada)

Pedí, en un solo mensaje, los saldos de cierre de cada cuenta activa de `cuentas.json`
(ARQ, OnTop Future Fund, Openbank y las que haya). Registralos:

```bash
python3 herramientas/registrar.py saldo --cuenta arq --monto <saldo> --fecha <AAAA-MM-DD>
```

Después preguntá por lo que no se registró durante el mes: ingresos extra, gastos
grandes, aportes hechos, comisiones. Cargá cada uno con `registrar.py`.

Revisá también si alguna tasa tiene `verificado` de hace más de 90 días. Si sí,
verificala (`WebSearch` o preguntando) y actualizala con
`python3 herramientas/registrar.py cuenta --id <id> --tasa <decimal> --fuente "<dónde, cuándo>"`.
El tipo de cambio de `perfil.json` se actualiza en la misma pasada.

## 2. Calcular

```bash
python3 herramientas/resumen.py --meses 6
python3 herramientas/plan.py
```

## 3. Comparar contra el mes pasado

Leé la última revisión en `revisiones/`. Respondé explícitamente:

- ¿Subió o bajó la tasa de ahorro, y por qué?
- ¿Se ejecutaron las acciones del mes pasado? Las que no, ¿siguen valiendo la pena?
- ¿El patrimonio creció por aportes o por rendimiento? (son cosas distintas: la primera
  depende de Max, la segunda del mercado)
- ¿Alguna oportunidad cerrada o nueva?

## 4. Escribir la revisión

Creá `revisiones/AAAA-MM.md` con esta estructura:

```markdown
# Revisión <mes AAAA>

## Números
| | Este mes | Mes anterior | Δ |
|---|---|---|---|
| Patrimonio | | | |
| Tasa de ahorro | | | |
| Aportes | | | |
| Gasto promedio | | | |
| Meses de emergencia cubiertos | | | |

## Qué pasó
(2-4 líneas: qué explica el cambio)

## Acciones del mes pasado
- [x] / [ ] ...

## Plan de este mes
1. Acción — monto — destino — impacto anual estimado
2. ...
3. ...

## Pendientes de dato
- ...
```

Máximo 3 acciones. Cada una con monto, destino e impacto anual.

## 5. Cerrar

Actualizá `perfil.json` → `revision.ultima` con la fecha de hoy, mostrale a Max el
resumen en 5 líneas y proponé la única acción más importante para los próximos 7 días.

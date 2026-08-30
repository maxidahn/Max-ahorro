# Cómo decide el agente

## El orden importa

El agente no optimiza rendimiento primero. Sigue esta cascada, de arriba hacia abajo:

1. **Colchón operativo** — la plata del mes, líquida. No se invierte.
2. **Deuda cara** — cualquier deuda con tasa mayor al mejor rendimiento disponible.
   Pagarla es una inversión con retorno garantizado igual a su tasa.
3. **Fondo de emergencia** — meses de gasto en instrumentos líquidos y de bajo riesgo.
   El objetivo está en `perfil.json` (`fondo_emergencia_meses_objetivo`).
4. **Metas con fecha** — cada meta con vencimiento reclama su cuota mensual.
5. **Crecimiento** — recién acá va el excedente al mejor rendimiento compatible con el
   perfil de riesgo.

Saltarse un escalón para perseguir un punto más de tasa es el error más caro y el más
común.

## Por qué el flujo pesa más que la tasa

Con un patrimonio de USD 25.000, pasar el rendimiento de 4% a 5% suma ~USD 250 al año.
Ahorrar USD 100 más por mes suma USD 1.200 al año, todos los años, y además compone.
Por eso el motor de reglas mira primero la tasa de ahorro y el excedente sin colocar, y
sólo después la asignación del capital.

## Reglas que corre `plan.py`

| Regla | Qué detecta | Cómo estima el impacto |
|---|---|---|
| `efectivo_ocioso` | Saldo a ~0% por encima del colchón operativo | exceso × mejor tasa segura |
| `fondo_emergencia` | Cobertura por debajo del objetivo | — (es prioridad, no rendimiento) |
| `colchon_excedido` | Más de un mes de gasto de más en bajo riesgo | exceso × (tasa crecimiento − tasa segura) |
| `tasa_ahorro` | Ahorro por debajo de la meta del perfil | brecha mensual × 12 |
| `excedente_sin_colocar` | Se ahorra pero no llega a una cuenta que rinda | excedente sin destino × 12 × mejor tasa |
| `aporte_manual` | Aportes que dependen de acordarse | — (riesgo de ejecución) |
| `concentracion` | Más del 40% en una sola cuenta | — (riesgo) |
| `riesgo` | Exposición de riesgo alto sobre el tope del perfil | — (riesgo) |
| `deuda_cara` | Deuda por encima del mejor rendimiento | saldo × (tasa deuda − mejor tasa) |
| `costos` | Comisiones anuales > 1% del patrimonio | mitad de los costos (parte evitable) |
| `gasto_discrecional` | Gasto recortable sin tocar lo fijo | 15% del gasto discrecional × 12 |
| `tasa_desconocida` | Cuentas sin rendimiento verificado | — (bloquea la comparación) |

Los umbrales están arriba de todo en `herramientas/plan.py`. Cambialos si tu criterio es
otro; están ahí para discutirse, no para creerse.

## Reglas de la cartera (`cartera.py`)

Salen todas de `datos/objetivo.json`, que es tuyo y editable. La herramienta no tiene
criterio propio sobre qué comprar: sólo mide y compara contra lo que vos escribiste.

| Regla | Qué hace |
|---|---|
| `tolerancia_pp` | Banda de desvío por clase antes de rebalancear. Evita operar por ruido. |
| `max_por_posicion_pct` | Techo por posición. No aplica a las clases de `clases_exentas_del_maximo`: un ETF de índice ya está diversificado por dentro. |
| `max_por_accion_individual_pct` | Techo más estricto para una empresa sola, que puede caer y no volver. |
| `min_por_posicion_pct` | Piso: por debajo, la posición no cambia el resultado y sí suma comisiones. |
| `orden_minima` y `max_comision_sobre_orden` | Frenan las órdenes donde el costo se come el beneficio. |
| `modo_rebalanceo` | `aporte` rebalancea comprando con dinero nuevo; `venta` permite vender. |

El orden de preferencia para corregir un desvío es siempre: **aportar > rebalancear
comprando > vender**. Vender realiza ganancias (impuesto) y paga comisión, así que es el
último recurso, salvo que la posición rompa un techo de riesgo.

## Lo que estas herramientas no hacen

No estiman el valor de una empresa, no proyectan precios, no leen el mercado y no
comparan tu cartera contra un índice. Nada de eso está implementado porque nada de eso se
puede hacer con confianza desde acá. Lo que sí hacen es medir peso, costo, concentración,
liquidez y coherencia con tus propias reglas, que es donde las decisiones se ganan o se
pierden de manera predecible.

## Límites conocidos

- El impacto anual es una **estimación con las tasas cargadas**. Si las tasas están
  viejas o mal, el número está mal. Por eso el agente exige `fuente_tasa` y `verificado`.
- Las proyecciones asumen rendimiento constante y aportes constantes. Ninguna de las dos
  cosas es cierta; sirven para comparar escenarios entre sí, no para prometer un saldo.
- La conversión entre monedas usa un tipo de cambio fijo del perfil. No modela
  devaluación ni inflación: comparar un rendimiento en pesos con uno en dólares requiere
  una decisión tuya sobre qué esperás del tipo de cambio.
- Los rendimientos de trading son pasados, no futuros, y pueden ser negativos.
- Los pesos de solapamiento (`peso_en_nucleo`) hay que cargarlos verificados: sin eso, la
  exposición real a una empresa que además está dentro del índice queda subestimada.
- Nada de esto es asesoramiento financiero profesional.

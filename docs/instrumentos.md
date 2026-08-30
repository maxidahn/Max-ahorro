# Instrumentos: qué hay que saber de cada uno

Este archivo no guarda tasas: las tasas viven en `datos/cuentas.json` con su fuente y su
fecha. Acá está **qué preguntarle a cada instrumento** para poder compararlo con otro.

## Los seis datos que definen a cualquier lugar donde ponés plata

| Dato | Por qué importa |
|---|---|
| Rendimiento **neto** anual | Bruto menos comisiones, mantenimiento y spread. Es lo único comparable. |
| Moneda | Un 30% en pesos y un 4% en dólares no se comparan sin tipo de cambio ni expectativa de devaluación. |
| Liquidez | Días hasta tener la plata disponible. Define si puede ser fondo de emergencia. |
| Riesgo (1–5) | 1 = depósito bancario a la vista; 5 = trading discrecional o activo volátil. |
| Costos | Comisión por operación, spread de compra/venta, mantenimiento, costo de salida. |
| Penalidades | Qué perdés si sacás la plata antes de tiempo. |

Cargá cada uno en `cuentas.json`. Lo que quede en `null` el agente lo trata como
desconocido y te lo va a pedir antes de recomendarte nada.

## ARQ App — trading en USD

Cuenta de inversión donde operás vos. Implicancias:

- **No tiene "tasa".** Tiene un resultado. Para `tasa_anual_estimada` usá el retorno real
  de los últimos 12 meses (podés calcularlo como: saldo actual − aportes del período,
  sobre el saldo inicial). Si es negativo, cargalo negativo.
- Riesgo 4–5 salvo que estés sólo en instrumentos de renta fija corta.
- Los costos se acumulan por operación: cada compra/venta va a `movimientos.csv` como
  tipo `comision`. Si operás seguido, esto define más el resultado que las decisiones.
- A verificar: comisión por operación, spread, costo de retiro de USD, y cuántos días
  tarda la plata en estar disponible en tu cuenta bancaria.

## OnTop Future Fund

Producto de ahorro/inversión en USD asociado a tu cobro por OnTop.

- A verificar y anotar: si el rendimiento es fijo o variable, quién lo administra, plazo
  mínimo, días de rescate, penalidad por retiro anticipado, comisión de administración,
  monto mínimo, y si el aporte se puede automatizar como porcentaje de cada cobro.
- La automatización es la ventaja fuerte de este tipo de producto: si podés desviar un %
  fijo de cada cobro antes de que la plata toque tu cuenta corriente, ahorrás sin
  decidirlo cada mes. Ponelo en `aporte_automatico: true` sólo si de verdad está activo.
- Ojo con contarlo como fondo de emergencia: si el rescate tarda o penaliza, no lo es.

## Openbank

Banco digital. Suele haber dos cosas distintas conviviendo:

- **Saldo a la vista**: liquidez total, rendimiento típicamente cero. Sirve para el
  colchón operativo del mes y nada más.
- **Saldo remunerado / plazo / fondo**: rinde, con distinto grado de disponibilidad.

Cargalos como **dos cuentas separadas** (`openbank-vista` y `openbank-remunerada`).
Mezclarlos esconde justo el problema que buscás: cuánta plata está quieta al 0%.

A verificar: tasa vigente y si es promocional o permanente, tope de saldo remunerado,
si la remuneración es diaria o mensual, y costo de mantenimiento de la cuenta.

## Opciones a comparar (no recomendaciones)

Si el diagnóstico muestra plata ociosa, estas son las familias de instrumentos que suele
tener sentido evaluar. Verificá condiciones y costos vigentes antes de mover nada:

- Cuentas remuneradas y fondos money market (liquidez inmediata o de 24 h).
- Plazos fijos, tradicionales o UVA, para plata con fecha conocida.
- Instrumentos de renta fija corta en USD para el tramo conservador.
- Fondos indexados amplios para el tramo de largo plazo, si el horizonte supera 5 años.

Ninguna de estas es una recomendación: son categorías para poner en la misma tabla y
comparar con los seis datos de arriba.

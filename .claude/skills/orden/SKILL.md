---
name: orden
description: Checklist previo a mandar una compra o una venta en la cartera. Usar antes de cualquier orden, y siempre que Max diga "quiero comprar", "voy a vender", "me quiero salir de", "¿aprovecho esta baja?".
---

# Antes de mandar la orden

Cinco minutos acá evitan la mayoría de las operaciones que después se lamentan. No es
para desalentar la orden: es para que la orden sea la que Max quiere haber hecho dentro
de un año.

## 1. Correr los números

```bash
python3 herramientas/cartera.py orden --tipo <compra|venta> --ticker <TICKER> --monto <IMPORTE>
```

## 2. Las siete preguntas

Pedile a Max que las conteste en una línea cada una. Si tres quedan en blanco, la orden
no está lista.

1. **¿Por qué esto y por qué ahora?** Si la respuesta empieza con "vi que", "leí que" o
   "está subiendo", no es una tesis.
2. **¿Qué me haría vender?** Un precio, un hecho o una fecha. Si no hay respuesta, no hay
   forma de saber si te equivocaste.
3. **¿Cuánto es esto de mi cartera después de la orden?** Sale del comando de arriba.
4. **Si esto cae 50%, ¿cuánto pierdo en dólares y me cambia algo?** Si la respuesta es
   "nada", la posición es demasiado chica para justificar el trabajo. Si es "mucho", es
   demasiado grande.
5. **¿Cuánto pago de comisión, en % del importe?**
6. **¿Qué regla de `objetivo.json` justifica esta orden?** Rebalanceo, techo de posición,
   piso de posición, cambio de tesis. "Ganas" no es una regla.
7. **Si esto lo hubiera mandado la semana pasada o lo mando la semana que viene, ¿cambia
   algo de verdad?** Si no cambia nada, no hay apuro: llevalo a la revisión mensual.

## 3. Señales de que conviene esperar

- Es un día de caída fuerte y el impulso es "salir antes de que baje más".
- Es después de una noticia y el impulso es "entrar antes de que suba más".
- La razón principal es el resultado acumulado de la posición (ganancia o pérdida).
- Es la tercera operación del mes sobre el mismo activo.
- Falta un dato bloqueante del informe de cartera.

Ninguna de estas frena una orden que corrige un techo de riesgo. Frenan las otras.

## 4. Registrar

Se registra la orden **se haya hecho o no**. Las que no se hicieron enseñan tanto como
las otras.

```bash
python3 herramientas/registrar.py operacion --tipo compra --ticker XXX --monto 500 \
    --comision 3 --motivo "<la tesis en una línea>" --regla <regla>
```

Después actualizá `datos/cartera.json`. En la revisión mensual se releen los motivos de
los últimos tres meses y se contesta una sola pregunta: **¿esto le ganó a no haber hecho
nada?**

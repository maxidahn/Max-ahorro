# Max-ahorro

Agente personal de ahorro. Toma tus saldos, ingresos y gastos, calcula cuánto estás
ahorrando de verdad y te dice dónde está la plata que podría estar rindiendo más.

Pensado para el caso concreto: ahorro en USD repartido entre **ARQ App** (trading),
**OnTop Future Fund** y **Openbank**, con la sensación de que se podría ahorrar más.

## Arrancar

```bash
# 1. Ver las herramientas funcionando con datos ficticios
python3 herramientas/resumen.py --datos datos/ejemplo
python3 herramientas/plan.py    --datos datos/ejemplo

# 2. Completar tus datos: en Claude Code, decile al agente
#    "arranquemos, ayudame a cargar mis datos"
#    o editar a mano datos/perfil.json y datos/cuentas.json

# 3. Tu foto real
python3 herramientas/resumen.py
python3 herramientas/plan.py
```

Sólo requiere Python 3.10+. No hay dependencias que instalar.

## Los dos agentes

**`ahorro`** (`.claude/agents/ahorro.md`) — cuánto entra, cuánto sale, cuánto queda y
dónde ponerlo. En Claude Code, dentro de este repo, alcanza con pedirle cosas como:

- "¿cómo vengo con el ahorro?"
- "¿dónde conviene que ponga el excedente de este mes?"
- "gasté 480 en el súper" · "el saldo de ARQ hoy es 9.800"
- "hagamos la revisión mensual" → sigue `.claude/skills/revision-mensual/SKILL.md`
- "¿me conviene Openbank remunerado o el Future Fund para el fondo de emergencia?"

**`cartera`** (`.claude/agents/cartera.md`) — comprar y vender con método. Trabaja sobre
tus posiciones reales y sobre tu política de inversión:

- "¿compro NVDA?" · "¿vendo SLV que está en rojo?"
- "me entraron 1.000 USD, ¿dónde los pongo?"
- "¿cómo viene la cartera?" → concentración, desvíos, reglas que no se cumplen
- antes de cualquier orden → checklist de `.claude/skills/orden/SKILL.md`

Lo que los agentes **no** hacen: mover plata, mandar órdenes, predecir precios, prometer
rendimientos o reemplazar a un asesor financiero. Calculan, ordenan, aplican **tus**
reglas y te dicen qué números faltan.

## Cartera

```bash
python3 herramientas/cartera.py                     # composición, concentración, reglas rotas
python3 herramientas/cartera.py aporte --monto 1000 # colocar plata nueva sin vender nada
python3 herramientas/cartera.py orden --tipo compra --ticker NVDA --monto 500 --clase accion
```

Para actualizar los valores sin editar el JSON a mano, exportá un CSV y:

```bash
python3 herramientas/importar.py posiciones --archivo ~/Downloads/cartera.csv   # simula
python3 herramientas/importar.py posiciones --archivo ~/Downloads/cartera.csv --aplicar
```

Sobre conectar TradingView por MCP: ver `docs/tradingview.md` (resumen: no hay servidor
oficial, y desde una sesión en la nube no se alcanza tu app de escritorio).

Tus posiciones están en `datos/cartera.json` y tus reglas en `datos/objetivo.json`
(techos por posición, piso por posición, banda de rebalanceo, orden mínima, comisión).
Los porcentajes objetivo que vienen cargados son un punto de partida editable, no una
recomendación: mientras `confirmado_por_max` siga en `false`, la herramienta lo avisa en
cada informe.

## Estructura

```
.claude/agents/ahorro.md              el agente de ahorro
.claude/skills/revision-mensual/      ritual de cierre de mes
datos/perfil.json                     ingresos, meta de ahorro, colchón, deudas, tipo de cambio
datos/cuentas.json                    cada instrumento: tasa, riesgo, liquidez, costos
datos/metas.json                      metas con monto y fecha
datos/cartera.json                    posiciones de la cuenta de inversión
datos/objetivo.json                   tu política: asignación objetivo y reglas de operación
datos/operaciones.csv                 registro de compras y ventas, con el motivo de cada una
datos/saldos.csv                      fotos de saldo por cuenta y fecha
datos/movimientos.csv                 ingresos, gastos, aportes, comisiones
datos/ejemplo/                        dataset ficticio para probar
herramientas/resumen.py               patrimonio, flujo, tasa de ahorro, fondo de emergencia
herramientas/plan.py                  oportunidades, plan mensual y proyección
herramientas/cartera.py               composición, rebalanceo y evaluación de órdenes
herramientas/importar.py              actualiza la cartera desde un CSV (TradingView, ARQ, planilla)
herramientas/apalancamiento.py        costo real de endeudarse para invertir, con escenarios
herramientas/cambio.py                cobrar en una moneda y gastar en otra: convertir vs endeudarse
herramientas/registrar.py             carga de datos sin editar CSV a mano
herramientas/pruebas.py               tests de las herramientas
docs/instrumentos.md                  qué verificar de ARQ, OnTop y Openbank
docs/tradingview.md                   qué se puede integrar de TradingView y qué no
docs/metodologia.md                   la cascada de decisión y las reglas del motor
revisiones/                           una revisión por mes
```

## Registrar cosas a mano

```bash
python3 herramientas/registrar.py saldo   --cuenta ontop --monto 5500
python3 herramientas/registrar.py gasto   --categoria supermercado --monto 480
python3 herramientas/registrar.py ingreso --categoria sueldo --monto 4200
python3 herramientas/registrar.py aporte  --cuenta arq --monto 400
python3 herramientas/registrar.py operacion --tipo compra --ticker SPY --monto 500 \
    --comision 3 --motivo "núcleo por debajo del objetivo" --regla tolerancia_pp
python3 herramientas/registrar.py cuenta  --id openbank-remunerada \
    --nombre "Openbank saldo remunerado" --moneda USD --tasa 0.035 \
    --riesgo 1 --liquidez 1 --proposito liquidez --fuente "app Openbank, 2026-08-30"
```

Las tasas se cargan en decimal: `0.035` = 3,5% anual.

## Privacidad

`datos/` guarda tus números reales. **Mantené el repositorio privado.** Si alguna vez lo
hacés público, sacá `datos/` primero.

## Aviso

Herramienta personal de cálculo y organización. No es asesoramiento financiero ni
impositivo, y no garantiza ningún rendimiento. Verificá tasas, costos y condiciones con
cada institución antes de mover plata.

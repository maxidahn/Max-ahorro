# Max-ahorro

Proyecto personal de ahorro de Max. El producto de este repo es el agente
`.claude/agents/ahorro.md` y las herramientas que le dan los números.

Hay dos agentes y el pedido decide cuál: `ahorro` para flujo, gastos y dónde poner el
excedente; `cartera` para comprar, vender, rebalancear y dimensionar posiciones. Leé la
definición del que corresponda antes de responder.

## Convenciones

- **Todo en español**, código y documentación incluidos.
- **Sólo biblioteca estándar de Python** (3.10+). No agregar dependencias.
- Las tasas se guardan en decimal (`0.035` = 3,5% anual) y siempre con `fuente_tasa` y
  `verificado` (fecha). Una tasa sin fuente no se usa para recomendar.
- Los montos se convierten a `moneda_base` del perfil usando `perfil.tipo_cambio`
  (unidades de esa moneda por 1 de la base).
- Nunca inventar ni estimar un dato financiero que Max no dio: si falta, se pide. Los
  scripts lo reportan en "Datos que faltan" y en las alertas `[bloqueante]`.
- Nunca afirmar ni insinuar hacia dónde va un precio, acá ni en el código: las
  herramientas aplican reglas propias, no pronósticos.
- Los datos personales van en `datos/`; los ejemplos ficticios en `datos/ejemplo/` y se
  aclaran como tales.

## Antes de tocar las herramientas

```bash
python3 herramientas/pruebas.py     # tests contra datos/ejemplo
```

Si cambiás una regla de `plan.py`, actualizá la tabla de `docs/metodologia.md`.

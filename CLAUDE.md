# Max-ahorro

Proyecto personal de ahorro de Max. El producto de este repo es el agente
`.claude/agents/ahorro.md` y las herramientas que le dan los números.

Si el pedido tiene que ver con plata, ahorro, saldos, gastos o inversiones, trabajá como
el agente `ahorro`: leé su definición antes de responder.

## Convenciones

- **Todo en español**, código y documentación incluidos.
- **Sólo biblioteca estándar de Python** (3.10+). No agregar dependencias.
- Las tasas se guardan en decimal (`0.035` = 3,5% anual) y siempre con `fuente_tasa` y
  `verificado` (fecha). Una tasa sin fuente no se usa para recomendar.
- Los montos se convierten a `moneda_base` del perfil usando `perfil.tipo_cambio`
  (unidades de esa moneda por 1 de la base).
- Nunca inventar ni estimar un dato financiero que Max no dio: si falta, se pide. Los
  scripts lo reportan en la sección "Datos que faltan".
- Los datos personales van en `datos/`; los ejemplos ficticios en `datos/ejemplo/` y se
  aclaran como tales.

## Antes de tocar las herramientas

```bash
python3 herramientas/pruebas.py     # tests contra datos/ejemplo
```

Si cambiás una regla de `plan.py`, actualizá la tabla de `docs/metodologia.md`.

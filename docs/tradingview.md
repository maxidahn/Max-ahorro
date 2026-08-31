# TradingView: qué se puede y qué no

Estado al 2026-08-30. Si algo de esto cambia, se corrige acá.

## No hay MCP oficial

TradingView **no publica un servidor MCP propio** y no figura en el directorio de
conectores de Claude (donde sí están, por ejemplo, Interactive Brokers, Webull y
Alpha Vantage). Tampoco tiene una API pública de lectura de tu cuenta: la API que ofrece
es para *mostrar* sus gráficos en un sitio, no para leer tus watchlists ni tus posiciones.

Lo que existe son **servidores MCP comunitarios**, proyectos independientes sin relación
con TradingView. Los hay de tres tipos:

- los que consultan endpoints internos de TradingView (cotizaciones, screener);
- los que exponen indicadores técnicos calculados con datos de terceros;
- un puente que maneja la **app de escritorio** por Chrome DevTools Protocol, es decir,
  controlando la aplicación desde afuera.

Antes de instalar cualquiera de los tres, tres cosas que conviene saber:

1. **Corren código de un tercero con acceso a tu sesión de TradingView.** El del puente,
   además, maneja tu app abierta y logueada.
2. **Usar endpoints internos suele ir contra los términos de uso** de la plataforma, y se
   rompen sin aviso cuando TradingView cambia algo.
3. **Ninguno te da datos de tu cuenta de ARQ**: TradingView sabe de gráficos y listas, no
   de tus tenencias reales.

Por eso este repo no incluye una configuración MCP apuntando a ninguno: instalar uno es
una decisión con consecuencias de seguridad, y se toma a ojos abiertos, no porque venía
en el repositorio.

## Y hay un límite más simple

Cuando esta conversación corre en Claude Code **en la nube**, el proyecto vive en un
contenedor remoto: no hay forma de alcanzar tu app de escritorio ni ningún servidor MCP
local. Para eso hay que correr Claude Code **en tu máquina**, en este mismo repo. Ahí sí,
si instalás un MCP local, aparece disponible para los agentes.

## Lo que sí funciona hoy

**Importar desde un CSV.** Exportás la lista desde TradingView (o desde ARQ, o desde una
planilla) y el importador actualiza la cartera:

```bash
# el archivo trae el valor de cada tenencia
python3 herramientas/importar.py posiciones --archivo ~/Downloads/cartera.csv

# el archivo trae el precio; el valor sale de precio x cantidad
python3 herramientas/importar.py precios --archivo ~/Downloads/watchlist.csv
```

Por defecto **sólo simula** y muestra el antes/después de cada posición. Con `--aplicar`
escribe. Entiende el formato de símbolo de TradingView (`NASDAQ:GOOGL` → `GOOGL`), acepta
`,` `;` o tabulador, y reconoce encabezados en español y en inglés.

Para el modo `precios`, cada posición necesita el campo `cantidad` en `cartera.json`.
Cargalo una vez y después la valuación se actualiza sola con cualquier lista de precios.

**Alertas.** Si querés que TradingView avise algo, sus alertas con webhook (planes pagos)
mandan un POST a una URL. Eso requiere un endpoint público escuchando: es un proyecto
aparte, no algo que se resuelva desde acá.

## Antes de conectar cualquier fuente de datos, la pregunta incómoda

Los agentes de este repo **no predicen precios por diseño** (ver `docs/metodologia.md`).
Un gráfico más no mejora una decisión que se toma por reglas de peso, costo y liquidez.
Lo único que la cartera necesita de una fuente externa es **el valor actualizado de cada
posición**, y para eso alcanza con el importador de arriba una vez por mes.

Si en algún momento querés precios automáticos de verdad, el camino soportado es un
conector del directorio oficial de Claude (Alpha Vantage cubre acciones, ETFs, FX y
fundamentals): lo conectás desde claude.ai y queda disponible sin instalar nada de
terceros ni depender de tu máquina.

## Fuentes

- [Directorio de conectores MCP de Claude](https://claude.ai/settings/connectors) —
  consultado el 2026-08-30, sin resultados para TradingView.
- [mcp-tradingview-server (bidouilles)](https://github.com/bidouilles/mcp-tradingview-server)
  y [TradingView MCP (atilaahmettaner)](https://lobehub.com/mcp/atilaahmettaner-tradingview-mcp)
  — proyectos comunitarios, sin afiliación con TradingView.
- [TradingView MCP Bridge (hilmituncay)](https://www.pulsemcp.com/servers/hilmituncay-tradingview-mcp)
  — el puente a la app de escritorio vía Chrome DevTools Protocol.

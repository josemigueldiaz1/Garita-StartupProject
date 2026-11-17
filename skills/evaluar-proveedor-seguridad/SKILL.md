---
name: evaluar-proveedor-seguridad
description: Evalúa y compara empresas de seguridad privada y vigilancia en el Perú para un servicio concreto, con datos de SUCAMEC, contratos públicos del OECE, SUNAT y la Defensoría del Pueblo. Úsala cuando alguien quiera contratar vigilancia o resguardo para una mina, campamento, planta, puerto, almacén u oficina; comparar propuestas u ofertas de seguridad; verificar si una empresa de seguridad está autorizada por SUCAMEC; saber cuánto debería costar un puesto de vigilancia 24/7; o detectar una oferta sospechosamente barata.
---

# Evaluar proveedor de seguridad

Garita pone los datos con su servidor MCP (`garita`) y esta skill pone el método. Las cuentas las hace Python con las herramientas y con `scripts/precio_puesto.py`, **nunca de memoria**.

## 1. Entender el pedido

Pide lo que falte, en una sola pregunta:

- **Lugar:** departamento, provincia y tipo de sitio (mina, campamento, planta, puerto, almacén u oficina).
- **Modalidad:** vigilancia con armas o sin armas. Si piden CCTV, GPS o control de accesos, esas son modalidades SUCAMEC aparte (ver `reference.md`).
- **Puestos y horario:** cuántos puestos y de cuántas horas (24/7, 12 h diurno, etc.) y por cuántos meses.
- **Ofertas a comparar**, si las hay: empresa (RUC si lo tienen) y monto total o precio por puesto-mes.

Si el pedido de `$ARGUMENTS` ya trae estos datos, no vuelvas a preguntarlos.

## 2. Verificar la autorización

1. Llama a `buscar_empresas(departamento, modalidad, armas, provincia)`.
2. Una empresa que **no aparece** no tiene sede autorizada y vigente para ese departamento y modalidad: **descártala y dilo** con su nombre, aunque su oferta sea la más barata.
3. Si una autorización vence en menos de 90 días, márcalo.
4. Si piden tecnología (CCTV, GPS, accesos), confirma esa modalidad con `ficha_empresa(ruc)`.

## 3. Precio

1. `benchmark_precio(departamento)` da el rango de mercado por puesto 24/7 y mes. Si `alcance` es `nacional`, dilo.
2. Si una oferta trae un **monto total**, conviértela a precio por puesto-mes con el script:

   ```bash
   uv run --project "${CLAUDE_SKILL_DIR}/../.." python "${CLAUDE_SKILL_DIR}/scripts/precio_puesto.py" \
       --monto 950000 --puestos-24h 8 --meses 12 --departamento "La Libertad"
   ```

   Con `--precio-ofertado` evalúa un precio que ya viene por puesto-mes. Sin `--monto` ni `--precio-ofertado`, estima cuánto debería costar el pedido según el mercado.
3. Para cada oferta usa `evaluar_oferta(precio_puesto_mes, horas_dia, departamento)`.
4. **Marca en rojo** (🔴) toda oferta con estado `bajo_piso`: no alcanza para pagar la planilla mínima de los agentes. Es una señal de informalidad, no una prueba; dilo así.
5. Si sirve como referencia, muestra 2 o 3 contratos parecidos con `contratos_vigilancia(departamento)`, con su `evidencia`.

## 4. Confianza y contexto

1. `puntaje_confianza(ruc, departamento, modalidad, armas)` para cada empresa que pasó el paso 2. Muestra **el desglose por componente**, no solo el número.
2. `riesgo_zona(departamento, provincia)` para dimensionar el servicio: cuántos conflictos hay en la provincia y cuántos son socioambientales.

## 5. Entregar

Una tabla comparativa, una fila por empresa:

| Empresa (RUC) | Autorización SUCAMEC | Vence | Puntaje | Precio puesto-mes | Semáforo | Fuente |
|---|---|---|---|---|---|---|

Debajo, en viñetas cortas: las descartadas y por qué, el riesgo de la zona y una recomendación.

## Reglas

- **Cita la fuente y el nivel de cada dato:** `verificado` (fuente oficial, con link), `extraido` (leído por Garita de un PDF oficial con OCR o LLM), `declarado` (lo dice la empresa) o `sintetico` (demo).
- **Nunca** presentes un dato declarado o sintético como verificado. El precio que ofrece una empresa es declarado.
- **Nunca** pidas, muestres ni inventes datos de vigilantes (nombres, DNI, fotos, estatura o peso de personas). La estatura o la experiencia son requisitos del cliente, no una base de personas.
- Si una herramienta responde que faltan datos procesados, dilo y no rellenes con estimaciones propias.
- Más detalle sobre modalidades, el puesto equivalente y las fuentes: `reference.md`.

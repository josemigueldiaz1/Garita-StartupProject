---
name: preparar-demo
description: Deja listo el demo en vivo de Garita - verifica que los datos procesados estén completos, que el caso de Pataz funcione de punta a punta, que pasen las pruebas y que la app levante. Úsala antes de presentar, ensayar o grabar el video de respaldo, o cuando pidan preparar o revisar el demo.
---

# Preparar el demo de Garita

El turno dura 3 minutos con el software corriendo en vivo, y la demo vale 8 de los 20 puntos. Esta skill confirma que nada falle.

## Pasos

1. **Chequeo automático**, sin gastar tokens:

   ```bash
   uv run python .claude/skills/preparar-demo/scripts/chequeo_demo.py
   ```

   Revisa las tablas de `data/processed`, las fechas de corte de cada fuente, si la clave está cargada (solo sí o no), el caso del demo y las pruebas. Si algo sale `FALTA`, corre `/actualizar-datos` con el paso que corresponda y repite.
2. **Levanta la app** y recorre el caso del demo:

   ```bash
   uv run streamlit run app.py
   ```

   Caso: *"vigilancia con armas, 8 puestos 24/7, campamento en Pataz (La Libertad)"*. Recorre en orden: pedido, mapa de riesgo, lista corta con su puntaje, precio con la alerta de oferta bajo el piso, documento con fechas de vencimiento y exportar la solicitud de propuesta.
3. **Modo demo:** confirma que la app funciona también sin la clave (por ejemplo, renombrando temporalmente `.env`). Si falla sin clave, es un error que hay que corregir antes de presentar.
4. **URL pública:** ábrela en una ventana privada. Si la app de Streamlit Cloud está dormida, despiértala unos minutos antes.
5. **Ensayo con cronómetro** siguiendo `docs/guion_demo.md`: problema (0:00–0:30), demo (0:30–2:30) y negocio (2:30–3:00).
6. Recuerda al usuario: conectarse a las 7:25 a. m., probar compartir pantalla y tener abierto el video de respaldo.

Antes de cualquier push de último minuto, corre `/revisar-secretos`.

# Print Manager Casa 🖨️

Calculadora interactiva, punto de venta (POS) y gestor de caja para servicios de **impresión, fotocopias, anillados, plastificados y trámites** en casa.

## Características Principales
- **Calculadora POS en tiempo real:** Presets de 1 toque para Impresión B/N, Fotocopia B/N, Impresión/Copia Color Normal y Color Full/Imagen.
- **Tramos de descuento por volumen automáticos:** Ajusta el precio unitario según la cantidad total de páginas (ej. 1–9, 10–49, 50+).
- **Cálculo de hojas físicas (Simple vs Doble Faz):** Calcula automáticamente cuántas hojas reales de papel se gastan y aplica descuento configurable por doble cara.
- **Detector de páginas PDF e imágenes:** Sube un PDF recibido por WhatsApp y el sistema cuenta las páginas automáticamente.
- **Calculadora de vuelto y resumen para WhatsApp:** Botones de billetes chilenos (`$1.000` a `$20.000`) y copiado de presupuesto en 1 clic.
- **Caja e historial (SQLite WAL):** Control de cobros del día, semana y mes, más seguimiento de trabajos pendientes/fiados.
- **100% Configurable desde la web:** Edita todos los precios, tramos, papeles y servicios extra sin tocar código.

## Ejecución Local
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt httpx
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\uvicorn webapp:app --reload --port 8095
```

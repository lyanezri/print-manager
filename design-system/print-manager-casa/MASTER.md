# Design System Master File — Raw Swiss Editorial & Tactile Minimal

**Project:** Print Manager Casa
**Style:** Raw Swiss Grid / Quiet Architectural Minimalism (Dieter Rams / Teenage Engineering / Editorial Paper & Ink)
**Principles:** Crudo (sin adornos ni colores chillones), Sencillo (cero ruido visual), Elegante (tipografía fina + monoespaciada y líneas de 1px expuestas), Intuitivo (jerarquía inmediata para cualquier persona de la casa).

---

## 1. Paleta de Materiales (Papel Crudo + Tinta + 1 Acento)

| Rol | Modo Papel (Light) | Modo Carbón (Dark) | Variable CSS |
|-----|--------------------|--------------------|--------------|
| Fondo Base (Papel Crudo) | `#F6F5F0` | `#111110` | `--bg` |
| Superficie / Tarjeta | `#FFFFFF` | `#181816` | `--surface` |
| Superficie Secundaria | `#EFECE6` | `#22221F` | `--surface-alt` |
| Tinta Principal | `#111111` | `#F3F2EE` | `--ink` |
| Tinta Secundaria | `#66645E` | `#9A9890` | `--ink-muted` |
| Línea Estructural (1px) | `#D6D3CD` | `#2E2E2A` | `--line` |
| Línea Fuerte / Activa | `#111111` | `#F3F2EE` | `--line-strong` |
| Acento Funcional (Naranja Braun) | `#D94E1F` | `#E85D2A` | `--accent` |
| Confirmación / Cobro | `#157F4B` | `#22A063` | `--ok` |

## 2. Tipografía
- **UI & Encabezados:** `Plus Jakarta Sans` / `Inter` (limpia, humana, pesos 500–700).
- **Precios, Cantidades y Totales:** `JetBrains Mono` (`tabular-nums`, clara y precisa como una máquina sumadora).

## 3. Reglas de Interfaz
- **Bordes expuestos de 1px** (`--line`), sin sombras infladas ni degradados.
- **Estado seleccionado inequívoco:** El botón activo invierte su color a **Tinta sólida (`#111111`) con texto claro**, logrando contraste instantáneo sin cansar la vista.
- **Cero jerga técnica:** Lenguaje cotidiano ("¿Qué vamos a imprimir?", "¿Cuántas páginas tiene?", "Total a cobrar").

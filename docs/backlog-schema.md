# Esquema de `backlog.json`

Fuente de verdad del backlog del proyecto. Lo genera la skill `pk-plan`, lo valida
`project-kit backlog validate` y lo consume `provision` para crear milestones, labels,
issues y los campos del Project. Vive en `.project-kit/backlog.json` del proyecto destino.

Un ejemplo completo y válido se instala en `.project-kit/templates/backlog.example.json`
(fuente: `src/project_kit/assets/templates/backlog.example.json`).

## Estructura

```json
{
  "version": 1,
  "phases": [ ... ],
  "labels": [ ... ],
  "issues": [ ... ]
}
```

Los campos desconocidos son un error (protege de erratas). La versión actual del formato es `1`.

### `phases` — fases

Cada fase es un milestone en el proveedor y una opción del campo `Phase` del Project. El orden
de la lista es el orden de entrega.

| Campo | Obligatorio | Descripción |
|---|---|---|
| `id` | sí | Identificador estable: minúsculas, dígitos y guiones (`mvp`, `v1-launch`) |
| `title` | sí | Nombre visible (`v0.1 MVP`). No puede repetirse |
| `description` | no | Texto del milestone |

### `labels` — labels propios (opcional)

Solo los labels **extra**. Los de tipo (`type:feature`…) y prioridad (`P0`…`P3`) los deriva
`provision` de cada issue y no hay que declararlos.

| Campo | Obligatorio | Descripción |
|---|---|---|
| `name` | sí | Nombre del label. No puede repetirse |
| `color` | no | 6 dígitos hexadecimales sin `#` (por defecto `ededed`) |
| `description` | no | Descripción |

### `issues` — épicas y tarjetas

| Campo | Obligatorio | Valores / descripción |
|---|---|---|
| `id` | sí | Identificador estable y único. Es la clave en `state.json` (`provider_ids.issues`), así que **no debe cambiar** una vez aprovisionado |
| `type` | sí | `epic`, `feature`, `adr`, `chore`, `bug`, `docs` (campo `Kind` del Project) |
| `phase` | sí | `id` de una fase existente |
| `title` | sí | Título de la issue |
| `priority` | sí | `P0` (crítica) a `P3` (baja) |
| `size` | sí | `XS`, `S`, `M`, `L`, `XL` |
| `parent` | no | `id` de una épica. Una épica no puede tener padre |
| `body` | no | Contexto en Markdown |
| `acceptance` | según tipo | Lista de criterios de aceptación (texto, sin `- [ ]`). **Obligatoria** (al menos uno) en `feature`, `bug` y `chore` |
| `labels` | no | Nombres de labels declarados en `labels` |

Las épicas enlazan a sus hijas por `parent`; `provision` genera la checklist de la épica a
partir de ellas.

## Reglas de validación

Se comprueban todas a la vez y se informa de cada problema:

- JSON válido, `version` soportada, sin campos desconocidos y con los tipos correctos.
- Ids con formato válido y sin duplicados (fases, labels e issues).
- `type`, `priority` y `size` dentro de los valores permitidos.
- Toda `phase` referenciada existe.
- Todo `parent` existe y es una épica; una épica no puede tener padre.
- Todo label usado en una issue está declarado en `labels`.
- Las `feature`, `bug` y `chore` tienen criterios de aceptación.

## Flujo de aprobación

1. `pk-plan` escribe `.project-kit/backlog.json`.
2. `project-kit backlog validate` debe pasar.
3. La persona usuaria aprueba el plan de forma explícita.
4. `project-kit approve plan` registra la aprobación en `state.json` (con fecha) y avanza la
   fase. Se niega a hacerlo si el backlog no existe o no es válido.

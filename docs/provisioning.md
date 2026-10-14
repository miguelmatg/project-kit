# Provisionado en GitHub

`project-kit provision` crea en el repositorio lo que el backlog necesita. Esta primera parte
cubre **milestones, labels y ramas permanentes**; el Project y las issues llegan en la
siguiente (#21).

```
project-kit provision [--repo owner/nombre] [--dry-run] [--yes]
```

## Cómo funciona

1. **Planifica** leyendo GitHub (solo lectura): qué milestones, labels y ramas existen ya.
2. **Muestra el plan**: lo que se va a crear y lo que ya está.
3. **Pide confirmación** (`[y/N]`). Sin terminal o con cualquier respuesta distinta de `y`,
   no hace nada. `--yes` omite la pregunta.
4. **Aplica**: milestones, luego labels, luego ramas.

`--dry-run` hace solo los pasos 1 y 2 y no modifica nada, ni en GitHub ni en `state.json`.
Para aplicar hay que haber aprobado el plan (`project-kit approve plan`).

## Qué se crea

| Elemento | Origen | Detalle |
|---|---|---|
| Milestones | Una por fase del backlog | El id se guarda en `state.json` (`provider_ids.milestones`) |
| Labels | Derivados de las issues y declarados en `labels` | `type:epic`, `type:feature`, `type:adr`, `type:chore`, `type:docs`, `bug`, `P0`–`P3`; solo los que el backlog usa, más los declarados |
| Ramas | `config.yml` → `branches` | `release` y `develop` si faltan, creadas desde `main` |

## Idempotencia y reanudación

- Solo se crea lo que **falta**. Lo que ya existe no se toca, aunque su color, descripción
  o contenido sean distintos: nunca se pisan ediciones manuales. Los labels se comparan sin
  distinguir mayúsculas, como hace GitHub.
- Ejecutarlo dos veces seguidas no cambia nada y la segunda no pregunta.
- Si algo falla a mitad (GitHub da 502 de vez en cuando), el progreso queda guardado y basta
  con repetir el comando: no se duplica lo ya creado.

## Condiciones que bloquean

Se informan con `BLOCKING` y no se aplica nada:

- `branches.main` de `config.yml` no es la rama por defecto del repositorio.
- El repositorio no tiene commits: las ramas nuevas se crean a partir de `main`, así que hace
  falta un commit inicial.

## Protección de ramas

Los repositorios **privados con plan gratuito no permiten** proteger ramas ni crear rulesets.
project-kit lo detecta consultando el endpoint de rulesets (GitHub responde un 403 con
"Upgrade to GitHub Pro or make this repository public") y, en ese caso:

- **no intenta** proteger ninguna rama,
- lo indica en cada ejecución,
- y la política de ramas debe cumplirse **por disciplina**: todo entra por PR hacia `develop`,
  y `release` y `main` solo por promoción.

Cuando el repositorio sea público o el plan lo permita, project-kit lo reconoce y lo indica,
pero **todavía no configura la protección**: hay que activarla a mano.

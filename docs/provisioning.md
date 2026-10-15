# Provisionado en GitHub

`project-kit provision` crea en el repositorio lo que el backlog necesita: milestones, labels,
ramas permanentes, el Project con sus campos y las issues.

```
project-kit provision [--repo owner/nombre] [--project número|título] [--dry-run] [--yes]
```

## Cómo funciona

1. **Planifica** leyendo GitHub (solo lectura): qué existe ya.
2. **Muestra el plan**: lo que se va a crear y lo que ya está.
3. **Pide confirmación** (`[y/N]`). Sin terminal o con cualquier respuesta distinta de `y`,
   no hace nada. `--yes` omite la pregunta.
4. **Aplica**, en este orden: milestones, labels, ramas, Project y campos, issues, enlaces de
   las épicas y tarjetas del Project.

`--dry-run` hace solo los pasos 1 y 2 y no modifica nada, ni en GitHub ni en `state.json`.
Para aplicar hay que haber aprobado el plan (`project-kit approve plan`).

## Qué se crea

| Elemento | Origen | Detalle |
|---|---|---|
| Milestones | Una por fase del backlog | El id se guarda en `state.json` (`provider_ids.milestones`) |
| Labels | Derivados de las issues y declarados en `labels` | `type:epic`, `type:feature`, `type:adr`, `type:chore`, `type:docs`, `bug`, `P0`–`P3`; solo los que el backlog usa, más los declarados |
| Ramas | `config.yml` → `branches` | `release` y `develop` si faltan, creadas desde `main` |
| Project | El que ya tengas (ver abajo) o uno nuevo, `<project_name> Roadmap` por defecto | Vinculado al repositorio |
| Campos | Del backlog | `Phase` (una opción por fase), `Kind` (Epic, Feature, ADR, Chore, Bug, Docs), `Priority` (P0–P3), `Size` (XS–XL) y `Status` (Backlog, Ready, In progress, In review, Done) |
| Issues | Una por entrada del backlog | Milestone de su fase, labels de tipo y prioridad más los suyos, y un cuerpo con contexto, criterios de aceptación y una marca oculta (`<!-- project-kit:id=… -->`) |
| Épicas | Las issues con `parent` | La épica lleva una checklist de sus hijas; cada hija dice `Part of #N` |
| Tarjetas | Cada issue en el Project | Con `Status`, `Phase`, `Kind`, `Priority` y `Size` |

Las épicas se crean antes que sus hijas, para poder enlazarlas.

## Idempotencia y reanudación

- Solo se crea lo que **falta**. Lo que ya existe no se toca, aunque su color, descripción o
  contenido sean distintos: nunca se pisan ediciones manuales.
- Ejecutarlo dos veces seguidas no cambia nada y la segunda no pregunta. Si el estado local se
  perdió pero todo existe en GitHub, esa ejecución lo reconstruye sin escribir en GitHub.
- Cada issue se reconoce por su marca oculta, además de por `state.json`: perder el estado no
  duplica issues.
- Si algo falla a mitad (GitHub da 502 o limita las peticiones), el progreso queda guardado y
  basta con repetir el comando. Cada ejecución vuelve a leer GitHub, no confía en un plan
  anterior.

## Qué no se pisa nunca

- **Issues existentes:** no se reescriben el título ni el cuerpo. La única excepción es el
  bloque de hijas de una épica (entre `project-kit:children:start` y `end`), que es de
  project-kit: se actualiza al añadir hijas y **conserva las casillas que ya marcaste**.
- **Campos del Project:** solo se rellenan los **vacíos**. Una tarjeta que moviste de columna
  o a la que cambiaste la prioridad se queda como la dejaste. `Status` se pone a `Backlog` una
  sola vez, al añadir la tarjeta.
- **Opciones de campo:** al añadir una fase nueva se añade su opción a `Phase` conservando las
  existentes (y los valores ya asignados).
- **`Status` personalizado:** solo se sustituye si es el que trae GitHub por defecto
  (`Todo`, `In Progress`, `Done`) **y** el Project no tiene tarjetas todavía, porque
  sustituirlo reinicia el estado de las tarjetas existentes. En cualquier otro caso se deja
  tal cual y se avisa de las opciones que faltan.

## Condiciones que bloquean

Se informan con `BLOCKING` y no se aplica nada:

- `branches.main` de `config.yml` no es la rama por defecto del repositorio.
- El repositorio no tiene commits: las ramas nuevas se crean a partir de `main`, así que hace
  falta un commit inicial.

## Límite de peticiones de GitHub

Con backlogs grandes GitHub puede limitar las peticiones. project-kit lo detecta, lo explica
("espera un minuto y repite") y **no reintenta a ciegas**; como el progreso está guardado,
repetir el comando continúa donde se quedó.

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

## Qué Project se usa

Antes de crear nada, `provision` busca los Projects **ya vinculados al repositorio** (y uno con
el título por defecto, aunque no esté vinculado), de modo que funciona igual en un repositorio
nuevo que en uno que ya tiene su tablero:

| Encuentra | Con terminal | Sin terminal o con `--yes` |
|---|---|---|
| Ninguno | Pregunta el nombre (Intro: `<project_name> Roadmap`) y lo crea | Lo crea con el nombre por defecto |
| Uno | Pregunta si usarlo (Intro: sí); si no, pide el nombre de uno nuevo | Lo usa |
| Varios | Los lista para elegir, con la opción de crear uno nuevo | Se detiene y pide `--project` |

`--project` acepta el número o el título exacto de un Project abierto del propietario, o un
título nuevo para crearlo. Lo elegido se guarda en `.project-kit/state.json` y las siguientes
ejecuciones lo reutilizan sin preguntar; un `--project` explícito lo sustituye. Un `--dry-run`
pregunta pero no guarda nada. Los Projects cerrados se ignoran.

## Vistas del Project

La API de GitHub no permite crear vistas (Board, Roadmap, tabla). Hay que crearlas a mano una
vez en la interfaz del Project.

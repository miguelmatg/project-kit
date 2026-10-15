# Actualizar un proyecto: `project-kit upgrade`

`uv tool upgrade project-kit-cli` actualiza el **programa**. Pero `project-kit init` copia al
repositorio ficheros que después viven allí por su cuenta (las skills de `.claude/skills/pk-*`,
las plantillas de `.project-kit/templates/` y `.project-kit/workflow.yml`) y no los sobrescribe
nunca. Por eso un proyecto ya creado se queda con la versión con la que nació. `upgrade` lo pone
al día sin pisar lo que hayas editado.

```
project-kit upgrade             # muestra qué cambia; no escribe nada
project-kit upgrade --diff      # además, las diferencias de cada fichero
project-kit upgrade --apply     # lo aplica
project-kit upgrade --apply --adopt
```

## Cómo decide

`init` y `upgrade` guardan en `.project-kit/installed.json` la huella (SHA-256) de cada fichero tal
como lo instalaron. Se versiona con el repositorio. Con ella, para cada fichero:

| Situación | Resultado |
|---|---|
| Idéntico a la versión actual | Nada que hacer |
| No lo editaste y el paquete trae una versión nueva | **update**: se reemplaza |
| Falta (es nuevo en esta versión, o lo borraste) | **add**: se crea |
| Lo editaste y el paquete no lo cambió | Se deja; no hay nada nuevo |
| Lo editaste **y** el paquete lo cambió | **conflict**: se queda el tuyo y la versión nueva se deja en `.project-kit/upgrade/new/` para que la mezcles |
| Difiere y no hay huella registrada (proyecto anterior a esta función) | **unknown**: igual que un conflicto, salvo con `--adopt` |
| Estaba instalado y ya no se distribuye | **obsolete**: se avisa, nunca se borra |

Los saltos de línea CRLF de un checkout de Git en Windows no cuentan como edición.

## Proyectos anteriores al registro

Un proyecto creado con una versión que no guardaba huellas no permite saber si un fichero distinto
es una versión antigua o una edición tuya, y `upgrade` no lo adivina. Los marca `unknown` y, sin
`--apply --adopt`, no los toca (deja la versión nueva en `.project-kit/upgrade/new/`). Si sabes que
no los editaste, `--adopt` los reemplaza. Revisa antes el resultado de `project-kit upgrade --diff`.

## Seguridad

- Sin `--apply` no se escribe nada.
- Todo fichero que se reemplaza se copia antes a `.project-kit/upgrade/backup/`.
- Nunca se pisa un fichero que hayas editado (ni con `--adopt`).
- `.project-kit/upgrade/` es temporal: cuando hayas revisado o mezclado, bórralo o añádelo a
  `.gitignore`.
- `config.yml`, `state.json`, el backlog y tus documentos no se tocan.

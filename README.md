# project-kit

Herramienta para el **antes** de un proyecto: definirlo, planificarlo, decidir su
arquitectura y montar su flujo de desarrollo y gestión (GitHub primero, GitLab después).
Al terminar entrega el relevo a [Spec Kit](https://github.com/github/spec-kit), que define e
implementa cada spec.

> Estado: diseño y esqueleto del paquete (v0.1 en desarrollo). Ver [`docs/design.md`](docs/design.md).

## Instalación y uso

Requisitos: [uv](https://docs.astral.sh/uv/), `git`, y [`gh`](https://cli.github.com/) con
sesión iniciada y los scopes `repo` y `project` (`gh auth refresh -s project`) para publicar en
GitHub. [Claude Code](https://claude.com/claude-code) es el agente que guía las fases.

```
# Instalar (ahora, desde un clon; cuando se publique será `uv tool install project-kit-cli`; el comando es `project-kit`)
uv tool install --editable <ruta-a-este-clon>

# En el repositorio del proyecto (puede estar vacío)
project-kit doctor     # comprueba las herramientas
project-kit init       # instala skills y plantillas; pregunta si la IA firma commits y si abrir Claude
project-kit help       # guía visual del flujo y los comandos (también: `project-kit` a secas)
```

`init` copia los ficheros y, al terminar, muestra los agentes de IA soportados (hoy solo Claude
Code) y ofrece abrirlo en esa misma terminal ya con **`/pk-start`** (Intro acepta). Se puede
evitar con `--agent none`; sin terminal no pregunta ni lanza nada, y dentro de Claude Code no
abre otro. Si lo prefieres, ábrelo tú y ejecuta `/pk-start`. Pregunta si quieres **solo
inicializar** o **empezar a definir el proyecto**, y al terminar cada fase ofrece continuar o
parar. `project-kit status` muestra en qué fase estás y cuál toca.

| Fase | Skill | Qué hace | Salida |
|---|---|---|---|
| 0 | `/pk-start` | Comprueba el entorno y elige: solo inicializar o empezar | `.project-kit/` |
| 1 | `/pk-discover` | Entrevista sobre qué es el proyecto | `docs/project/brief.md` |
| 2 | `/pk-decide` | Guía las decisiones de stack y arquitectura | `docs/adr/*.md` |
| 3 | `/pk-workflow` | Acuerda el flujo de trabajo del equipo | `docs/development-workflow.md` |
| 4 | `/pk-plan` | Deriva fases, épicas y backlog | `roadmap.md`, `backlog.json` |
| 5 | `/pk-provision` | Crea milestones, ramas, Project e issues | GitHub |
| 6 | `/pk-handoff` | Relevo a Spec Kit (una spec por issue) | `constitution-input.md` |

Cada fase termina con una aprobación (`project-kit approve <fase>`) y puede rellenarse a mano
a partir de las plantillas de `.project-kit/templates/`. Las fases se listan en
`.project-kit/workflow.yml`, con el mismo estilo que el de Spec Kit; para un proyecto pequeño se
desactiva una con `enabled: false`.

## Documentación

- [Diseño](docs/design.md): alcance, fases, proveedor, relevo a Spec Kit, decisiones abiertas.
- [Publicación](docs/publishing.md): qué hace falta para `uv tool install project-kit-cli` público.
- [Esquema de `backlog.json`](docs/backlog-schema.md): formato del backlog y reglas de validación.
- [Relevo a Spec Kit](docs/handoff.md): qué genera `handoff`, cómo instala Spec Kit y qué viene después.
- [Provisionado en GitHub](docs/provisioning.md): qué crea `provision`, idempotencia y protección de ramas.
- [Referencia: playbook del flujo](docs/references/template-repo-playbook.md): receta de origen
  (extraída de otro proyecto).

## Licencia y contribuciones

MIT ([`LICENSE`](LICENSE)). Las issues con ideas y mejoras son bienvenidas; el código lo
desarrolla solo su autor y las pull requests están desactivadas ([`CONTRIBUTING.md`](CONTRIBUTING.md)).

## Ramas

`main` (estable), `release` (pruebas) y `develop` (desarrollo). Todo entra por PR.

## Desarrollo

Requiere [uv](https://docs.astral.sh/uv/).

```
uv sync                 # entorno y dependencias
uv run project-kit --version
uv run pytest           # tests
uv run ruff check .     # lint
uv run ruff format .    # formato
```

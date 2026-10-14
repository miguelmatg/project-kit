# project-kit

Herramienta para el **antes** de un proyecto: definirlo, planificarlo, decidir su
arquitectura y montar su flujo de desarrollo y gestión (GitHub primero, GitLab después).
Al terminar entrega el relevo a [Spec Kit](https://github.com/github/spec-kit), que define e
implementa cada spec.

> Estado: diseño y esqueleto del paquete (v0.1 en desarrollo). Ver [`docs/design.md`](docs/design.md).

## Documentación

- [Diseño](docs/design.md): alcance, fases, proveedor, relevo a Spec Kit, decisiones abiertas.
- [Esquema de `backlog.json`](docs/backlog-schema.md): formato del backlog y reglas de validación.
- [Relevo a Spec Kit](docs/handoff.md): qué genera `handoff`, cómo instala Spec Kit y qué viene después.
- [Provisionado en GitHub](docs/provisioning.md): qué crea `provision`, idempotencia y protección de ramas.
- [Referencia: playbook del flujo](docs/references/template-repo-playbook.md): receta de origen
  (extraída de otro proyecto).

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

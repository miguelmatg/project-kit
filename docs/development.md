# Desarrollo de project-kit

Este documento es para quien trabaja en el propio proyecto. La documentación de uso está en el
[README](../README.md), que es también la página del paquete en PyPI.

## Entorno

Requiere [uv](https://docs.astral.sh/uv/).

```
uv sync                       # entorno y dependencias
uv run project-kit --version  # ejecutar la CLI desde el código fuente
uv run pytest                 # tests
uv run ruff check .           # lint
uv run ruff format .          # formato
```

Dentro del repositorio, `project-kit` suelto puede resolver al ejecutable del `.venv` y no al
instalado con `uv tool`; usa `uv run project-kit` para estar seguro de lo que ejecutas. Para
probar en otro directorio sin publicar: `uv tool install --editable <ruta-a-este-clon>`.

## Ramas

`main` (estable, publicada), `release` (pruebas) y `develop` (desarrollo). Todo entra por PR:
squash a `develop` y merge commit a `release` y `main`. Las tres están protegidas y solo se
puede abrir PRs desde la cuenta del autor.

## Commits y versiones

Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `ci:`). Los títulos de las PRs
a `develop` son los mensajes de los commits, y de ellos sale la versión: `feat:` sube la menor y
`fix:` el parche. Un cambio que solo toque `docs:` o `chore:` **no** genera versión, y por tanto
no actualiza la página de PyPI (los metadatos y el README se fijan al subir cada versión).

## Publicar

Automático al llegar a `main`; ver [publishing.md](publishing.md).

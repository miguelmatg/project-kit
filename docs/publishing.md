# Publicar project-kit

Objetivo: que cualquiera pueda ejecutar `uv tool install project-kit-cli` (o
`uvx --from project-kit-cli project-kit init`). El paquete se llama `project-kit-cli` en PyPI
(`project-kit` estaba ocupado en la práctica para este uso) y el comando que instala es
`project-kit`. La publicación es automática desde `main`; las pruebas se hacen en
local, instalando el clon con `uv tool install --editable <ruta>`.

## Cómo funciona

```
develop ──PR──▶ release ──PR──▶ main ──(push)──▶ release-please abre/actualiza la "PR de release"
                                                         │ se fusiona
                                                         ▼
                                       tag vX.Y.Z + GitHub release ──▶ tests ──▶ PyPI
```

- El workflow es `.github/workflows/release.yml`; la configuración, `release-please-config.json`
  y `.release-please-manifest.json`.
- **Versión automática.** [release-please](https://github.com/googleapis/release-please) lee los
  Conventional Commits que llegan a `main` y propone la versión siguiente: `feat:` sube la
  menor, `fix:` el parche, y `feat!:` o `BREAKING CHANGE:` lo incompatible (mientras la versión
  sea `0.x`, eso también sube la menor). Actualiza `pyproject.toml`, `uv.lock` y `CHANGELOG.md`
  en una PR que **tú fusionas** cuando quieras publicar. Si no la fusionas, no se publica nada.
- **Publicación.** Al fusionarla se crea el tag y la release y un segundo job pasa ruff y los
  tests, construye con `uv build` y sube a PyPI con `uv publish`. PyPI confía en el workflow
  (*trusted publishing*): no hay tokens guardados.
- **Una sola versión por número.** PyPI no deja volver a subir un número ya publicado. Por eso
  la versión la pone release-please y no se edita a mano.
- Los títulos de las PRs a `develop` son los mensajes de los commits (squash): mantenlos en
  formato `feat: …`, `fix: …`, `docs: …`. Los `chore:`, `docs:` y `test:` no generan versión.

## TestPyPI no hace falta

`test.pypi.org` es un servidor aparte, con cuentas propias, y lo que se sube ahí no lo ve
`uv tool install project-kit-cli`. Aquí se descarta: se prueba en local y la versión final va
directamente a **pypi.org**.

## Lo que tienes que hacer tú (una vez)

1. ~~Licencia (D4)~~: hecho, MIT.
2. **Cuenta en [pypi.org](https://pypi.org/account/register/)** (no en test.pypi.org), con
   verificación en dos pasos. PyPI no permite entrar con GitHub: es un usuario y contraseña
   propios.
3. **Registrar el publicador de confianza** antes de la primera subida, en
   <https://pypi.org/manage/account/publishing/> ("Add a new pending publisher"):

   | Campo | Valor |
   |---|---|
   | PyPI project name | `project-kit-cli` |
   | Owner | `miguelmatg` |
   | Repository name | `project-kit` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

4. **En GitHub**, ya configurado: el repositorio es público, el permiso de Actions para crear
   PRs está activo, y `develop`, `release` y `main` tienen rulesets (todo por PR, sin
   force-push ni borrado) y las PRs de otras personas están desactivadas. El environment `pypi`
   se crea solo en la primera ejecución; si quieres un freno extra, añade *required reviewers*.

## Primera publicación

1. Con lo anterior hecho, `develop` → `release` → `main` por PR, como siempre.
2. Al llegar a `main`, release-please abre la PR *"chore(main): release 0.1.0"*. Revísala y
   fusiónala.
3. Mira la ejecución de *Release* en la pestaña Actions. Si termina bien, en unos minutos:

   ```
   uv tool install project-kit-cli
   project-kit --version
   ```

## Avisos

- **Las PRs que crea release-please con el `GITHUB_TOKEN` no lanzan otros workflows** (`ci.yml`
  no corre sobre ella). No importa aquí, porque el job `publish` vuelve a pasar los tests antes
  de subir; si algún día quieres CI en esa PR, hace falta un token personal.
- **Después de cada release `main` tiene un commit que `develop` no.** Propágalo de vuelta a
  `develop` con una PR, igual que un hotfix.
- Si el job `publish` falla (tests, o PyPI rechaza algo), la release de GitHub ya existe pero
  PyPI no tiene la versión. Se arregla en `develop`, se promociona, y release-please propone la
  siguiente versión; no se reutiliza el número.
- Los tests no se han ejecutado todavía en Linux. `ci.yml` los corre en Ubuntu y Windows en cada
  PR para enterarte antes de llegar a `main`.

## Alternativa sin PyPI

```
uv tool install git+https://github.com/miguelmatg/project-kit
uv tool install git+https://github.com/miguelmatg/project-kit@v0.1.0   # una versión concreta
```

Funciona con el repositorio público, o privado si cada usuario tiene acceso (clave SSH o
credenciales de Git).

## Lista de comprobación

- [x] D4: licencia MIT; `LICENSE` y `license` en `pyproject.toml`
- [ ] Cuenta de PyPI con 2FA y *pending publisher* registrado
- [x] Ajuste de Actions "crear y aprobar PRs" activado
- [x] D5: repositorio público
- [ ] Primera PR a `main`; fusionar la PR de release; comprobar `uv tool install project-kit-cli`

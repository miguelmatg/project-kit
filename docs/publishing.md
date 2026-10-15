# Publicar project-kit

Objetivo: que cualquiera pueda ejecutar `uv tool install project-kit` (o
`uvx project-kit init`). Hay dos caminos; el segundo no necesita PyPI.

## Camino A: PyPI (el estándar)

`uv tool install <nombre>` descarga de PyPI. Hace falta:

1. **Cuenta en PyPI** con verificación en dos pasos, y opcionalmente otra en
   [TestPyPI](https://test.pypi.org) para ensayar. El nombre `project-kit` estaba libre al
   comprobarlo (octubre de 2026); se reserva al publicar la primera versión.
2. **Decidir la licencia (D4)** y poner un fichero `LICENSE`. Sin licencia, el código es
   legalmente "todos los derechos reservados" aunque esté en PyPI.
3. **Completar los metadatos de `pyproject.toml`**: `license`, `authors`, `keywords`,
   `classifiers` (versión de Python, sistema operativo, estado de desarrollo) y
   `[project.urls]` (Homepage, Repository, Issues). El `README.md` es la página del paquete.
4. **Una versión que uv instale**: `0.1.0.dev0` es una pre-versión y `uv tool install` la
   ignora salvo con `--prerelease allow`. Hay que publicar `0.1.0` (o `0.1.0a1` y avisar del
   flag).
5. **Repositorio público (D5)** si se quiere que las URLs del paquete funcionen y que otros
   contribuyan. No es obligatorio para publicar en PyPI, pero un paquete público que enlaza a un
   repositorio privado confunde.
6. **Credenciales para publicar**, mejor sin contraseñas:
   - *Trusted publishing*: se registra el repositorio y el workflow en PyPI y un workflow de
     GitHub Actions publica al crear un tag `vX.Y.Z` con `uv build` y
     `uv publish --trusted-publishing always` (permiso `id-token: write`). No hay tokens que
     guardar.
   - O un *API token* de PyPI en `UV_PUBLISH_TOKEN` y `uv publish` desde la máquina.

Ensayo recomendado antes de la primera publicación real:

```
uv build                                          # genera dist/ (wheel y sdist)
uv publish --publish-url https://test.pypi.org/legacy/ --token <token-testpypi>
uv tool install --index https://test.pypi.org/simple/ project-kit
```

Ya se ha comprobado que el wheel incluye las skills, plantillas, el `workflow.yml` y el hook,
que son los ficheros que no son `.py`.

Cada versión de PyPI es **inmutable**: un número publicado no se puede reutilizar ni cambiar.
Se versiona con SemVer y se publica desde un tag en `main`.

## Camino B: directamente desde Git (sin PyPI)

```
uv tool install git+https://github.com/<usuario>/project-kit
uv tool install git+https://github.com/<usuario>/project-kit@v0.1.0   # una versión concreta
```

Funciona con el repositorio público tal cual. Con uno privado, cada usuario necesita acceso
(clave SSH o credenciales de Git). Sirve para empezar a probar con otras personas sin cuenta en
PyPI ni decisiones de licencia, pero no hay búsqueda ni control de versiones tan limpio.

## Lista de comprobación

- [ ] D4: nombre y licencia decididos; `LICENSE` en el repositorio
- [ ] Metadatos completos en `pyproject.toml`
- [ ] Versión `0.1.0` (sin `.dev`)
- [ ] D5: repositorio público
- [ ] Cuenta de PyPI con 2FA y trusted publishing configurado
- [ ] Ensayo en TestPyPI y prueba de `uv tool install` en una máquina limpia
- [ ] Tag `v0.1.0` y publicación

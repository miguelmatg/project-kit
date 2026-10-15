# Relevo a Spec Kit

`project-kit handoff` cierra el trabajo de project-kit y deja el proyecto listo para que
[Spec Kit](https://github.com/github/spec-kit) defina e implemente cada spec.

```
project-kit handoff [--install-speckit] [--dry-run] [--yes]
```

El único contrato con Spec Kit es **un fichero de texto** y sus comandos públicos. project-kit
**no escribe nunca dentro de `.specify/`**: Spec Kit es el dueño de
`.specify/memory/constitution.md`.

## Qué hace

1. **Detecta Spec Kit**: el ejecutable `specify` (y su versión) y el directorio `.specify/`
   (y la versión con la que se inicializó).
2. **Genera `.project-kit/handoff/constitution-input.md`**: el texto que se pasa a
   `/speckit-constitution`, en el orden que usa su plantilla (principios, restricciones, flujo
   de trabajo y puertas de calidad, gobierno). Es determinista: con las mismas entradas sale
   siempre lo mismo.
3. **Instala Spec Kit si falta** (solo con `--install-speckit` y tras confirmar).
4. **Indica los pasos siguientes**, sin ejecutarlos: el comando de la constitución y la
   relación entre las issues del backlog y las specs.

## De dónde salen los datos

| En la constitución | Origen |
|---|---|
| Nombre, idioma y nombres de las ramas | `.project-kit/config.yml` |
| Patrón de rama de una spec y estrategia de fusión por rama | `workflow:` de `.project-kit/config.yml` (lo escribe `/pk-workflow`) |
| Principios y Definition of Done | Plantilla genérica (ver abajo) |
| Decisiones registradas | `docs/adr/*.md`: título y, si lo tienen, el estado (`Status: Accepted`) |
| Documentos y fases | `docs/project/brief.md`, `docs/project/roadmap.md` y las fases del backlog, si existen |
| Dónde viven las reglas (índice) | Lo que existe en el proyecto: ver "Índice de reglas" |
| Reglas propias del proyecto | `.project-kit/handoff/constitution-extra.md`, si existe |
| Stack | "Definido por las decisiones" si hay ADRs; si no, "pendiente de un ADR" |

El patrón de rama y la estrategia de fusión salen de datos, no de la prosa de
`docs/development-workflow.md`, así que `/pk-workflow` los guarda en `config.yml` además de en
el documento:

```yaml
workflow:
  spec_branch: "spec/<name>"   # por defecto NNN-name
  merge:                       # squash | merge | rebase
    develop: squash
    release: merge
    main: merge
```

### Índice de reglas

La constitución incluye una sección **"Where the project's rules live"** que dice dónde mirar
para cada cosa en lugar de repetirlo en cada spec. Solo aparecen las fuentes que el proyecto
tiene:

- **Tareas y seguimiento**: el GitHub Project (título y URL, guardados al hacer `provision`) y
  las issues son la fuente de verdad; una issue es una spec y su PR la cierra (`Closes #N`); no
  hay una lista de tareas paralela; la tarjeta pasa a In progress, In review y Done.
- **Backlog** (`.project-kit/backlog.json`), **alcance** (`brief.md`), **hoja de ruta**
  (`roadmap.md`), **decisiones** (`docs/adr/`), **proceso** (`docs/development-workflow.md`) y
  las **plantillas** de PR e issues.

### Ficheros temporales

`constitution-input.md` y `constitution-extra.md` solo existen para alimentar
`/speckit-constitution`. Cuando la constitución real está escrita, la fuente única es ella, y
**`project-kit approve handoff` los borra**. Para poder aprobar, `.specify/memory/constitution.md`
tiene que existir y no ser ya la plantilla de Spec Kit (la plantilla vacía está llena de
marcadores `[EN_MAYÚSCULAS]`; una constitución escrita no tiene ninguno). Si se vuelve a ejecutar
`handoff` después, avisa de que ya está hecho y no recrea el fichero. Para cambiar las reglas
desde entonces se enmienda la constitución con `/speckit-constitution`.

### Fichero regenerable y reglas propias

`constitution-input.md` lleva la cabecera `<!-- project-kit:managed -->`: se **regenera** cada
vez que cambian las entradas, hasta que se aprueba el relevo. Para añadir reglas del proyecto
(seguridad, cumplimiento normativo, convenciones del equipo) no se edita ese fichero: se
escriben en **`constitution-extra.md`**, que project-kit nunca toca y se añade al final como
"Project-specific rules". Solo contenido de gobierno: Spec Kit rechaza peticiones de construir
funcionalidades. Ya no hace falta usarlo para corregir el flujo de ramas: eso sale de
`config.yml`.

Si alguien borra la cabecera de `constitution-input.md`, el fichero pasa a ser suyo y deja de
regenerarse (se avisa; para volver a generarlo basta borrarlo).

### Plantilla sobrescribible

El texto base se instala con `init` en `.project-kit/templates/constitution-input.md` y puede
editarse. Usa variables `{{...}}` (`project_name`, `language`, `provider`, `branches.main`,
`branches.release`, `branches.develop`, `spec_branch`, `merge_summary`, `stack`, `references`,
`decisions`, `rules_index`, `extra`). Una variable desconocida (una errata) es un error, no se
cuela en el resultado.

## Instalar Spec Kit

Con `--install-speckit`, project-kit muestra lo que va a ejecutar y pregunta antes (`--yes`
omite la pregunta):

| Situación | Comando |
|---|---|
| No hay CLI de Spec Kit | `uv tool install specify-cli` |
| No está inicializado en el repositorio | `specify init --here --integration claude --force --non-interactive` |

- Necesita `uv`. Si falta, lo dice y propone instalar el paquete `specify-cli` por otro medio.
- `specify init` **fusiona** sus ficheros con los existentes. Se ha comprobado que respeta los
  del proyecto y los de project-kit; lo único que toca es `.claude/settings.json`, que
  reformatea conservando su contenido.
- Si tras instalar el CLI no está en el PATH, indica `uv tool update-shell`.
- Un fallo en cualquier paso detiene el proceso.

## Versiones

project-kit se ha probado con Spec Kit **1.2.x**. Ante otra versión **avisa y continúa**:
como solo depende del fichero de entrada, debería seguir funcionando.

## Después del relevo

1. En Claude Code: `/speckit-constitution @.project-kit/handoff/constitution-input.md`
2. Opcional: mencionar `docs/project/` y `docs/adr/` en `CLAUDE.md` o `AGENTS.md`, para que
   `/speckit-specify` y `/speckit-plan` los lean.
3. Cada issue del backlog es candidata a una spec; su texto sirve de entrada a
   `/speckit-specify`.
4. Cuando la constitución esté creada: `project-kit approve handoff` (borra los ficheros
   temporales del relevo).

Las skills `pk-handoff` y `pk-provision` guían estos pasos desde Claude Code.

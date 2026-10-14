# project-kit — Documento de diseño (v0, borrador)

> Estado: **diseño, sin código**. Objetivo de este documento: acordar qué es project-kit,
> qué hace cada fase, cómo se instala y cómo entrega el relevo a Spec Kit, para poder
> implementarlo después sin redactar todo de nuevo en cada proyecto.

## 1. Qué es y qué no es

**project-kit** es una herramienta instalable para el **antes** de un proyecto: definirlo,
decidir su arquitectura, planificarlo y montar su flujo de desarrollo y su gestión en
GitHub. Cuando termina, entrega el relevo a **Spec Kit**, que define e implementa cada spec.

| | project-kit | Spec Kit |
|---|---|---|
| Momento | Antes del código y puntualmente después | Durante todo el desarrollo |
| Unidad de trabajo | El proyecto (fases, épicas, ADRs, flujo) | Una feature (spec → plan → tasks → implement) |
| Salida | Documentación del proyecto, backlog, normas, plantillas, repo/Project configurados | Specs, planes, tareas, código |
| Frecuencia de uso | Intensa al principio; luego esporádica | Diaria |

No-objetivos:
- No sustituye ni reimplementa Spec Kit; **no escribe dentro de su lógica** ni depende de su formato interno.
- No es un gestor de tareas de implementación (eso son las `tasks.md` de Spec Kit).
- No decide el stack ni el producto: guía la decisión y la deja registrada.

Se mueve en el mismo terreno que BMAD-METHOD (planificación previa), pero **complementa**
a Spec Kit en lugar de reemplazarlo. No existe hoy una herramienta que cubra la
combinación; ver `docs/references/` para el análisis de lo existente (extensiones
comunitarias de Spec Kit: Product Forge, Spec Roadmap, Tasks to GitHub Project, Charter,
adrkit…). Antes de implementar cada fase, **reevaluar si alguna de esas piezas la cubre**.

## 2. Por qué no es una extensión de Spec Kit

Los comandos de extensión de Spec Kit exigen un proyecto ya inicializado con
`specify init`. project-kit actúa antes y debe poder **ofrecer instalar Spec Kit**, así
que es una herramienta independiente que convive con él.

## 3. Principios de diseño

1. **Un flujo, varios proveedores.** La lógica es única; GitHub se implementa primero y
   GitLab después como adaptador (§7).
2. **Idempotente y reanudable.** Cualquier fase se puede repetir; el estado vive en
   `.project-kit/state.json`.
3. **Humano en el bucle.** Cada fase termina en una puerta de aprobación; nada se crea en
   GitHub sin confirmación explícita.
4. **Agnóstico de dominio.** Plantillas parametrizadas; ningún texto de producto.
5. **Documentación como producto.** Las salidas son ficheros versionados en el repo
   (`docs/project/…`), legibles por humanos y por Spec Kit.
6. **Degradación elegante.** Si falta `gh`, Spec Kit o permisos, lo detecta, lo explica y
   deja el resto de fases utilizables (modo "solo ficheros").
7. **Dueños claros de cada fichero.** project-kit nunca modifica `.specify/` salvo la
   entrega acordada (§8).

## 4. Flujo de usuario y fases

Cada fase es una **skill** de Claude Code (`/pk-<fase>`) respaldada por plantillas y
scripts. Todas leen y escriben `.project-kit/state.json`.

| Fase | Skill | Entradas | Salidas | Puerta |
|------|-------|----------|---------|--------|
| 0 | `pk-init` | Repo vacío o existente | `.project-kit/config.yml` (proveedor, idioma, nombres de rama); detección de `gh`/`glab`, Spec Kit, Python/Node; oferta de instalar lo que falte | Config confirmada |
| 1 | `pk-discover` | Entrevista guiada | `docs/project/brief.md` (visión, usuarios, valor, no-objetivos, restricciones legales/negocio, riesgos) | Brief aprobado |
| 2 | `pk-decide` | Brief | `docs/adr/NNNN-*.md` (stack, arquitectura, auth, datos, despliegue…) con opciones y decisión | ADRs críticos aceptados |
| 3 | `pk-plan` | Brief + ADRs | `docs/project/roadmap.md`, `.project-kit/backlog.json` (fases, épicas, tarjetas con criterios de aceptación, prioridad y tamaño) | Roadmap y backlog aprobados |
| 4 | `pk-workflow` | Config + decisiones | `docs/development-workflow.md`, `.github/` (PR/issue templates), política de ramas y de protección, normas de proceso | Normas aprobadas |
| 5 | `pk-provision` | Backlog + workflow + proveedor | Ramas permanentes, labels, milestones, Project (campos, estados), issues y épicas enlazadas | Confirmación antes de escribir en el proveedor |
| 6 | `pk-handoff` | Todo lo anterior | `.project-kit/handoff/constitution-input.md` + índice de docs; instalación/inicialización de Spec Kit si falta; instrucciones para `/speckit-constitution` y primera spec | Relevo entregado |
| — | `pk-status` / `pk-amend` | Estado | Resumen de fases; cambios posteriores (nueva épica, ADR, cambio de proceso) que actualizan docs y proveedor | — |

Las fases 1–3 pueden ejecutarse en modo "ligero" (proyectos pequeños) saltando ADRs
no críticos.

## 5. Estructura que se instala en el proyecto destino

```
<proyecto>/
├── .claude/skills/pk-*/SKILL.md     # skills de cada fase
├── .project-kit/
│   ├── config.yml                   # proveedor, idioma, convenciones (versionado)
│   ├── state.json                   # fase actual, ids creados en el proveedor
│   ├── backlog.json                 # fuente de verdad del backlog
│   ├── templates/                   # plantillas parametrizadas (se pueden sobrescribir)
│   ├── scripts/                     # CLI/scripts de proveedor
│   └── handoff/constitution-input.md
├── docs/project/{brief,roadmap}.md
├── docs/adr/
├── docs/development-workflow.md
└── .github/ (o .gitlab/)            # plantillas de PR/MR e issues
```

Convención: lo que escribe project-kit lleva cabecera `<!-- project-kit:managed -->` o vive
bajo `.project-kit/`, para que `pk-amend` sepa qué puede regenerar sin pisar ediciones
manuales.

## 6. Estructura del paquete (repo project-kit)

```
project-kit/
├── skills/pk-*/SKILL.md             # fuente de las skills
├── templates/                       # constitución-input, brief, ADR, roadmap, PR, issues…
├── providers/
│   ├── github/                      # implementación de la interfaz de proveedor
│   └── gitlab/                      # (fase posterior)
├── pyproject.toml                   # paquete Python (uv), entrada `project-kit`
├── src/project_kit/                 # CLI: init, doctor, install, upgrade, provision
├── docs/ (diseño, referencias)
└── tests/
```

Instalación: `uv tool install project-kit` (o desde git) y `project-kit init --here` en la raíz del repo destino.\nCLI mínimo: `project-kit init`, `doctor` (diagnóstico de requisitos), `upgrade`
(actualiza skills/plantillas respetando ediciones), `provision`, `status`.

## 7. Interfaz de proveedor

Operaciones que debe ofrecer un proveedor (todas idempotentes, con reintentos y backoff):

| Operación | GitHub | GitLab (futuro) |
|---|---|---|
| `auth.check()` y scopes | `gh auth status` (repo, project) | `glab auth status` |
| `branches.ensure(names)` | `git push` | igual |
| `branches.protect(rules)` (si el plan lo permite) | rulesets | protected branches |
| `labels.sync()` | labels | labels |
| `milestones.sync()` | milestones | milestones |
| `board.ensure(fields, statuses)` | Projects v2 (campos single-select, Status) | Issue boards + scoped labels |
| `issues.sync(backlog)` | issues + `item-add/edit` | issues + epics (según plan) |
| `epics.link()` | checklist en el cuerpo | epics nativas (Premium) o checklist |
| `templates.install()` | `.github/ISSUE_TEMPLATE`, PR template | `.gitlab/issue_templates`, MR templates |
| `views.hint()` | vistas manuales (sin API) | n/a |

Notas heredadas de GitHub: sin protección en repos privados con plan gratuito (debe
detectarlo y documentarlo en las normas); sin API para crear vistas del Project;
errores 502/GraphQL intermitentes (reintentos, varias pasadas, esperar antes de
verificar). Terminología: PR en GitHub = MR en GitLab; las plantillas se parametrizan.

## 8. Relevo a Spec Kit (handoff)

1. **Detección:** busca `.specify/` y `specify` en el PATH; lee la versión.
2. **Instalación si falta:** con confirmación, `uv tool install specify-cli` y
   `specify init --here` con la integración elegida (p. ej. `claude`). Si falta `uv`, lo
   indica y ofrece alternativas.
3. **Normas:** genera `.project-kit/handoff/constitution-input.md` con principios,
   restricciones, flujo de ramas, puertas de calidad, Definition of Done y gobernanza
   (derivados de §4.4), en el estilo que espera `/speckit-constitution`.
4. **Entrega:** indica (o ejecuta, si el usuario lo pide) `/speckit-constitution` con ese
   contenido. **Spec Kit sigue siendo dueño** de `.specify/memory/constitution.md`.
5. **Contexto para las specs:** deja `docs/project/` y `docs/adr/` como referencias
   estables; sugiere que `AGENTS.md`/`CLAUDE.md` los mencionen para que
   `/speckit-specify` y `/speckit-plan` los lean.
6. **Backlog ↔ specs:** cada tarjeta lista del backlog es candidata a una spec
   `NNN-nombre`; la issue enlazada sirve de entrada a `/speckit-specify`.
7. **Versiones:** registra la versión de Spec Kit probada; ante una versión desconocida,
   avisa y usa solo el contrato mínimo (el fichero de entrada).

## 9. Estado, idempotencia y plantillas

- `state.json`: fase actual, aprobaciones, mapa `id_local → id_en_proveedor` (milestones,
  issues, project). Permite reanudar tras fallos parciales.
- Plantillas con variables (`{{project_name}}`, `{{provider}}`, `{{branches.*}}`,
  `{{language}}`). Sobrescribibles por el proyecto en `.project-kit/templates/`.
- Todo lo generado es determinista salvo el contenido de la entrevista.

## 10. Material heredado (reutilizable)

Del proyecto `multi-saas` (ver `docs/references/template-repo-playbook.md`):
constitución genérica, guía de flujo, plantillas de PR/issues/ADR, backlog del proceso,
scripts de GitHub con las correcciones, y 11 trampas conocidas (PATH de `gh`, scopes,
`!` ejecuta bash, PowerShell 5.1, inestabilidad de la API, plan gratuito, vistas manuales…).

## 11. Decisiones abiertas

| # | Decisión | Opciones | Recomendación |
|---|----------|----------|---------------|
| D1 | **Lenguaje/runtime e instalación** | (a) Python con `uv tool install`; (b) TypeScript/npm; (c) mixto | **DECIDIDO: (a) Python distribuido con uv.** Se instala como Spec Kit (`uv tool install project-kit`, comando `project-kit init --here`), copiando skills y scripts a la raíz del repo, sin `node_modules`. `uv` ya es requisito de Spec Kit: una sola dependencia. Scripts y CLI en Python |
| D2 | Forma de las skills | Skills de Claude Code en `.claude/skills` (como Spec Kit) / además soporte para otros agentes | Empezar con Claude Code |
| D3 | ¿Fases 1–3 totalmente guiadas o con plantillas para rellenar a mano? | Guiadas / plantillas / ambas | Ambas: entrevista + documento editable |
| D4 | Nombre y licencia | `project-kit`; licencia por decidir | Decidir antes de publicar |
| D5 | Visibilidad del repo | Privado (ahora) → público si se quiere compartir | Privado hasta tener una versión usable |
| D6 | Alcance del primer MVP | init + discover + plan + provision(GitHub) + handoff | Ver §12 |

## 12. Hoja de ruta de project-kit

- **v0.1 (MVP):** `init`/`doctor`, `pk-plan` con `backlog.json`, `provision` en GitHub,
  `handoff` con `constitution-input.md`. Probar en un proyecto real.
- **v0.2:** `pk-discover`, `pk-decide`, `pk-workflow` completos, plantillas sobrescribibles,
  `upgrade`.
- **v0.3:** `pk-amend`/`status`, modo "solo ficheros", tests de idempotencia.
- **v0.4:** proveedor GitLab.
- **v1.0:** documentación, ejemplos y publicación.

## 13. Riesgos

- Solapamiento con extensiones existentes: reevaluar antes de cada fase (§1).
- Cambios en el formato de Spec Kit: se mitiga con un contrato mínimo basado en ficheros.
- APIs de proveedores inestables: reintentos, estado reanudable, verificación diferida.
- Exceso de ceremonia en proyectos pequeños: modo ligero y fases saltables.

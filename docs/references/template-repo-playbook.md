# Playbook: repo plantilla de flujo de desarrollo (agnóstico del producto)

> Documento de arranque para crear **un repo nuevo en modo template** (y un **GitHub Project
> plantilla**) que contenga solo el flujo de desarrollo profesional y el planteamiento de
> proyectos, reutilizable en cualquier producto. No habla de ningún producto concreto.
> Origen: se destila de lo montado en `multi-saas` (nada de eso se borra; este doc es la
> receta para extraerlo y generalizarlo después).

Cómo usarlo: abrir una sesión de Claude Code en el repo nuevo, darle este fichero y pedir
*"ejecuta el playbook"*. Las secciones 1–2 son decisiones ya tomadas; la 3 son preguntas a
confirmar; las 4–9 son los artefactos a generar; la 10 es el orden de ejecución; la 11,
las trampas conocidas.

---

## 1. Objetivo y alcance

- Un repo **template** de GitHub (`Use this template`) con: modelo de ramas, constitución
  genérica, guía de flujo, plantillas de PR/issues, plantilla de ADR, scripts de bootstrap
  y backlog **del proceso** (no del producto).
- Un **GitHub Project plantilla** (campos, estados, vistas) que se copia a cada proyecto
  nuevo.
- Pensado para **una sola persona** trabajando con asistentes de IA, con rigor profesional.
- Spec-driven con **Spec Kit** (`/speckit-*`), que ya trae sus skills en `.claude/skills/`
  y `.specify/`.

Fuera de alcance: cualquier decisión de producto, stack o dominio. Eso lo decide cada
proyecto mediante sus propios ADRs.

## 2. Decisiones ya tomadas (heredadas)

| Tema | Decisión |
|------|----------|
| Ramas permanentes | `main` (producto lanzado), `release` (pruebas/aceptación), `develop` (desarrollo) |
| Ramas de trabajo | Salen de `develop`: `NNN-nombre` (una por spec, formato Spec Kit), `chore/*`, `docs/*`, `fix/*`. `hotfix/*` sale de `main` |
| Flujo de promoción | `develop → release → main`; hotfix a `main` y `release` y retropropagación a `develop` |
| Fusión | *squash* a `develop`; *merge commit* a `release` y `main`; etiqueta SemVer `vX.Y.Z` en `main` |
| Commits | Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`, `ci:`) |
| Todo por PR | Sin push directo a las tres ramas permanentes; sin aprobación humana obligatoria (1 persona) pero con checklist de PR |
| Protección técnica | **Depende del plan de GitHub**: repo privado + plan Free = no hay protección de ramas ni rulesets → se cumple por disciplina y queda escrito en la constitución. Repo público o plan de pago → activar rulesets con el script de la §8.2 |
| Planificación | GitHub Project como fuente de verdad. Milestones = fases. Épicas = issues con label `type:epic` que listan sus hijas |
| Campos del Project | Fase, Tipo (Epic/Feature/ADR/Chore/Bug/Docs), Prioridad (P0–P3), Tamaño (XS–XL) + Status: Backlog → Ready → In progress → In review → Done |
| WIP | Máximo 1 spec *In progress* y 1 *In review* |
| Ready | Una tarjeta solo pasa a Ready con criterios de aceptación |
| Constitución | Principios genéricos (spec-driven, test-first, seguridad/secretos, simplicidad, ADRs), con la elección de stack como **ADR pendiente por proyecto** |
| Decisiones | ADRs numerados en `docs/adr/` (Proposed/Accepted/Superseded) |
| CI/CD | Se diseña como tarjetas del planteamiento (GitHub Actions por defecto), no se incluye en el template |
| Idioma | Documentación en español; identificadores, commits y ramas en inglés/minúsculas sin acentos |

## 3. Preguntas a confirmar al arrancar (no asumir)

1. Nombre del repo plantilla y owner (¿cuenta personal u organización?). ¿Público (permite
   protección de ramas gratis) o privado?
2. ¿Idioma de las plantillas y la doc? (por defecto español).
3. ¿Mantener Spec Kit tal cual (versión de `.specify/`) o actualizarlo?
4. ¿Se quiere incluir un `CLAUDE.md` con las reglas del flujo para los asistentes? (recomendado)
5. ¿Incluir `.gitignore`/`.editorconfig`/`.gitattributes` genéricos (fin de línea LF)?
6. ¿Licencia del template?
7. ¿Fases del backlog de proceso a incluir? (propuesta en §7: Flujo, Planteamiento, Fundaciones)
8. ¿CI mínimo genérico en el template (lint de markdown/commits) o ninguno?

## 4. Estructura del repo template

```
.
├── .claude/skills/speckit-*            # Spec Kit (copiado tal cual)
├── .specify/                           # Spec Kit + memory/constitution.md genérica
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── ISSUE_TEMPLATE/{feature,bug,adr,config}.yml
│   └── project/backlog.json            # backlog del PROCESO (§7)
├── docs/
│   ├── development-workflow.md         # guía operativa (§6)
│   ├── adr/0000-template.md
│   └── template-repo-playbook.md       # este documento (opcional conservarlo)
├── scripts/
│   ├── github-bootstrap.ps1            # labels, milestones, Project, issues (§8.1)
│   └── github-branch-protection.ps1    # rulesets, solo si el plan lo permite (§8.2)
├── CLAUDE.md                           # reglas de flujo para asistentes (opcional)
└── README.md                           # cómo usar el template (§9)
```

## 5. Constitución genérica (esqueleto)

Generar con `/speckit-constitution` a partir de este esqueleto. Marcadores `<<...>>` =
completar por proyecto.

```markdown
# <<Proyecto>> Constitution

## Core Principles
### I. Spec-Driven Development (NON-NEGOTIABLE)
Toda funcionalidad sigue specify → clarify → plan → tasks → implement. Sin spec aprobada no
hay código de producto. Cada spec vive en su rama NNN-nombre desde develop y en
specs/NNN-nombre/. Cambios triviales (typos, deps, config) pueden ir como chore sin spec.

### II. Test-First y calidad verificable
Lógica de dominio con tests primero (Red-Green-Refactor). Tests de integración en fronteras
(puertos/adaptadores) y de contrato en cambios de API/esquema. Sin CI verde no se fusiona;
un bug corregido incluye el test que lo reproduce.

### III. Seguridad y secretos
Autorización en backend. Secretos solo en gestor de secretos / GitHub Secrets, nunca en el
repo (se versiona un .env.example sin valores). Datos personales tratados según RGPD/normativa
aplicable y documentado en la spec.

### IV. Automatización y reproducibilidad
Infraestructura y procesos como configuración versionada; sin cambios manuales no reflejados
en el repo; tareas críticas idempotentes y reintentables.

### V. Simplicidad (YAGNI)
Solución más simple que valide el producto; toda complejidad extra se justifica por escrito
(Complexity Tracking del plan o ADR).

### VI. Decisiones por escrito (ADR)
Toda decisión transversal (stack, auth, datos, despliegue) se registra como ADR en docs/adr/.

## Restricciones adicionales
- Stack de lenguaje/framework: <<pendiente: ADR en la fase de planteamiento>>.
- Idioma: docs/specs en <<es>>; código, commits y ramas en inglés/minúsculas.
- <<Restricciones específicas del proyecto>>

## Flujo de desarrollo y puertas de calidad
(Ramas: tabla main/release/develop; ramas de trabajo; hotfix; squash a develop, merge commit
a release/main; SemVer en main; Conventional Commits.)
- Todo por PR; sin push directo a main, release ni develop.
- **Protección de ramas:** <<técnica (rulesets) | por disciplina porque el repo es privado en
  plan gratuito; se activará con scripts/github-branch-protection.ps1 si cambia>>.
- Project como fuente de verdad; Ready solo con criterios de aceptación; WIP 1+1.
- Definition of Done: criterios de aceptación cumplidos, tests en CI verdes, docs/ADR
  actualizados, PR con `Closes #N`, rama de trabajo eliminada.

## Governance
La constitución prevalece sobre otras prácticas. Enmiendas por PR contra develop con
justificación, versionadas SemVer. Cada plan incluye Constitution Check.

**Version**: 1.0.0 | **Ratified**: <<fecha>> | **Last Amended**: <<fecha>>
```

## 6. Guía de flujo (`docs/development-workflow.md`) — contenido

Secciones: (1) ramas con diagrama y tabla origen/destino/fusión; (2) ciclo de una
funcionalidad: elegir tarjeta Ready → `git switch develop && git pull` → `/speckit-specify`
(crea `NNN-nombre`) → clarify → plan → tasks → analyze → implement → PR a `develop` con
`Closes #N` → squash → borrar rama; (3) promoción `develop→release→main` con etiqueta SemVer
y GitHub Release, y hotfix; (4) GitHub Project: campos, columnas, vistas, WIP, enlace;
(5) fases del proyecto (tabla fase/objetivo/salida); (6) ADRs; (7) entornos (local, pruebas =
`release`, producción = `main`). Tomar `docs/development-workflow.md` de `multi-saas` como
base y **quitar toda referencia al producto**.

## 7. Backlog del proceso (`.github/project/backlog.json`)

Tres fases genéricas. Cada tarjeta lleva criterios de aceptación. El script de §8.1 lo carga.
Formato: `milestones[]`, `labels[]`, `issues[]` (`id`, `parent`, `phase`, `type`,
`priority`, `size`, `labels`, `title`, `body`).

**Fase 0 – Repo y flujo** (montar el sistema de desarrollo)
- Épica *Modelo de ramas y reglas*: crear `main/release/develop`; documentar política de
  protección (técnica o por disciplina) según plan de GitHub; convención de commits y
  nombres de rama; estrategia de fusión y SemVer.
- Épica *Gobierno*: constitución genérica v1.0.0; plantilla de ADR; `CLAUDE.md`;
  `.gitignore`/`.editorconfig`/`.gitattributes`.
- Épica *Plantillas y automatización de GitHub*: PR template; issue templates
  (feature/bug/adr); labels y milestones; scripts de bootstrap; Project con campos y
  estados; vistas Board/Roadmap/Tabla (manual) y marcar el Project como template.
- Épica *Documentación*: guía de flujo; README del template; este playbook.

**Fase 1 – Planteamiento del proyecto** (se repite en cada proyecto nuevo)
- Épica *Descubrimiento*: visión, usuarios y propuesta de valor; requisitos legales y de
  privacidad; modelo de negocio; nombre/dominio.
- Épica *Decisiones (ADRs)*: stack; estructura del repo y límites de módulos; autenticación y
  autorización; modelo de datos/tenancy; estrategia de despliegue.
- Épica *Planificación*: roadmap por fases y milestones; backlog inicial de épicas; criterios
  de Ready/Done del proyecto; riesgos.

**Fase 2 – Fundaciones técnicas** (se repite en cada proyecto nuevo)
- Épica *CI/CD y entornos*: CI en PR (lint+tests+build); publicación de artefactos/imágenes;
  CD a `release` y a `main`; release automática (tag + changelog); definición de entornos.
- Épica *Infraestructura base*: servidor/hosting y hardening; DNS y HTTPS; entorno local
  reproducible; backups y restauración verificada; observabilidad; gestión de secretos.
- Épica *Esqueleto*: aplicación mínima desplegada extremo a extremo (walking skeleton).

## 8. Scripts

### 8.1 `scripts/github-bootstrap.ps1` (versión corregida y genérica)

Idempotente, con reintentos (GitHub da 502/errores GraphQL intermitentes) y sincroniza los
campos del Project de **todas** las issues en cada ejecución. La opción de `Fase` se deriva
de los milestones del JSON. Compatible con **Windows PowerShell 5.1**.

```powershell
<#
.SYNOPSIS  Crea labels, milestones, Project (campos) e issues desde un backlog JSON.
.NOTES     Requiere gh con scopes repo y project: gh auth login -s project,repo
           Idempotente. Lanzar con: powershell -NoProfile -File scripts/github-bootstrap.ps1 -Repo owner/repo
#>
param(
  [Parameter(Mandatory)][string]$Repo,
  [string]$ProjectTitle = 'Roadmap',
  [string]$Backlog = "$PSScriptRoot/../.github/project/backlog.json"
)
$ErrorActionPreference = 'Stop'
$gh = (Get-Command gh -ErrorAction SilentlyContinue).Source
if (-not $gh) { $gh = 'C:\Program Files\GitHub CLI\gh.exe' }
$owner = $Repo.Split('/')[0]
$tmp = if ($env:CLAUDE_JOB_DIR) { Join-Path $env:CLAUDE_JOB_DIR 'tmp' } else { $env:TEMP }
$utf8 = New-Object Text.UTF8Encoding $false

function Gh { for ($t=1;$t -le 4;$t++) { & $gh @args; if ($LASTEXITCODE -eq 0) { return }; Start-Sleep (2*$t) }; throw "gh $($args -join ' ') fallo" }
function GhJson { for ($t=1;$t -le 4;$t++) { $o = & $gh @args; if ($LASTEXITCODE -eq 0) { return ($o -join "`n" | ConvertFrom-Json) }; Start-Sleep (2*$t) }; throw "gh $($args -join ' ') fallo" }

$data = Get-Content $Backlog -Raw -Encoding UTF8 | ConvertFrom-Json

Write-Host '== Labels'
foreach ($l in $data.labels) { Gh label create $l.name --repo $Repo --color $l.color --description $l.description --force | Out-Null }

Write-Host '== Milestones'
$ms = GhJson api "repos/$Repo/milestones?state=all&per_page=100"
foreach ($m in $data.milestones) {
  if (-not ($ms | Where-Object title -eq $m.title)) {
    # OJO: interpolar con $($m.title) entre comillas; sin eso PS pasa el objeto entero
    Gh api "repos/$Repo/milestones" -f "title=$($m.title)" -f "description=$($m.description)" | Out-Null
    Write-Host "  + $($m.title)"
  }
}

Write-Host '== Project'
$proj = (GhJson project list --owner $owner --format json --limit 100).projects | Where-Object title -eq $ProjectTitle
if (-not $proj) { $proj = GhJson project create --owner $owner --title $ProjectTitle --format json; Write-Host "  + $ProjectTitle" }
$pn = $proj.number
try { Gh project link $pn --owner $owner --repo $Repo | Out-Null } catch { }

function Get-Fields { (GhJson project field-list $pn --owner $owner --format json --limit 100).fields }
$fields = Get-Fields
$want = [ordered]@{
  'Fase'      = ($data.milestones | ForEach-Object { $_.title }) -join ','
  'Tipo'      = 'Epic,Feature,ADR,Chore,Bug,Docs'
  'Prioridad' = 'P0,P1,P2,P3'
  'Tamano'    = 'XS,S,M,L,XL'
}
foreach ($k in $want.Keys) {
  if (-not ($fields | Where-Object name -eq $k)) {
    Gh project field-create $pn --owner $owner --name $k --data-type SINGLE_SELECT --single-select-options $want[$k] | Out-Null
    Write-Host "  + campo $k"
  }
}
$fields = Get-Fields

# Status personalizado. La consulta va a FICHERO: pasarla inline rompe las comillas en PS 5.1
$status = $fields | Where-Object name -eq 'Status'
if (-not ($status.options | Where-Object name -eq 'Backlog')) {
  $q = 'mutation($f:ID!){updateProjectV2Field(input:{fieldId:$f,singleSelectOptions:[' +
       '{name:"Backlog",color:GRAY,description:"Sin refinar"},' +
       '{name:"Ready",color:BLUE,description:"Con criterios de aceptacion"},' +
       '{name:"In progress",color:YELLOW,description:"Rama creada"},' +
       '{name:"In review",color:ORANGE,description:"PR abierto"},' +
       '{name:"Done",color:GREEN,description:"Fusionado en develop"}]}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}'
  $qf = Join-Path $tmp 'status.graphql'; [IO.File]::WriteAllText($qf, $q, $utf8)
  try { Gh api graphql -F "query=@$qf" -f "f=$($status.id)" | Out-Null; Write-Host '  ~ Status actualizado' }
  catch { Write-Warning 'Status no actualizado por API; editalo a mano en Settings del Project.' }
  $fields = Get-Fields
}
$projId = (GhJson project view $pn --owner $owner --format json).id
# OJO: en PowerShell $F y $f son la MISMA variable (no distingue mayusculas)
$FieldMap = @{}; foreach ($fld in $fields) { $FieldMap[$fld.name] = $fld }
function Opt($field, $name) { ($FieldMap[$field].options | Where-Object { $_.name -eq $name } | Select-Object -First 1).id }

Write-Host '== Issues'
$existing = GhJson issue list --repo $Repo --state all --limit 500 --json 'number,title,url'
$created = @{}
foreach ($i in $data.issues) {
  $hit = $existing | Where-Object title -eq $i.title | Select-Object -First 1
  $mTitle = ($data.milestones | Where-Object phase -eq $i.phase).title
  if ($hit) { $created[$i.id] = @{ number = $hit.number; url = $hit.url } }
  else {
    $bf = Join-Path $tmp "issue-$($i.id).md"; [IO.File]::WriteAllText($bf, $i.body, $utf8)
    $url = (& $gh issue create --repo $Repo --title $i.title --body-file $bf --milestone $mTitle --label ($i.labels -join ',')) | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear $($i.id)" }
    $created[$i.id] = @{ number = [int]($url -split '/')[-1]; url = $url }
    Write-Host "  + #$($created[$i.id].number) $($i.title)"
  }
  # Sincroniza SIEMPRE (item-add es idempotente): una ejecucion cortada deja items sin campos
  $item = GhJson project item-add $pn --owner $owner --url $created[$i.id].url --format json
  foreach ($s in @(@('Status','Backlog'), @('Fase',$mTitle), @('Tipo',$i.type), @('Prioridad',$i.priority), @('Tamano',$i.size))) {
    $oid = Opt $s[0] $s[1]
    if ($oid) { Gh project item-edit --id $item.id --project-id $projId --field-id $FieldMap[$s[0]].id --single-select-option-id $oid | Out-Null }
  }
}

Write-Host '== Epicas'
foreach ($e in ($data.issues | Where-Object { $_.type -eq 'Epic' })) {
  $list = ($data.issues | Where-Object { $_.parent -eq $e.id } | ForEach-Object { "- [ ] #$($created[$_.id].number) $($_.title)" }) -join "`n"
  $bf = Join-Path $tmp "epic-$($e.id).md"; [IO.File]::WriteAllText($bf, "$($e.body)`n`n## Tarjetas`n$list", $utf8)
  Gh issue edit $created[$e.id].number --repo $Repo --body-file $bf | Out-Null
}
Write-Host "`nListo: https://github.com/users/$owner/projects/$pn  (si es una organizacion: /orgs/$owner/projects/$pn)"
Write-Host 'Manual: vistas Board/Roadmap/Tabla. Ejecutar 2-3 veces si GitHub devuelve errores intermitentes.'
```

Verificación posterior (el listado del Project puede tardar unos segundos en reflejar los
cambios; esperar ~30 s antes de contar):

```powershell
$items = (gh project item-list <N> --owner <owner> --format json --limit 200 | ConvertFrom-Json).items
"Items: $($items.Count)"
"Incompletos: " + (($items | ? { -not ($_.fase -and $_.prioridad -and $_.tamano -and $_.tipo -and $_.status) } | % { $_.content.number }) -join ',')
```

### 8.2 `scripts/github-branch-protection.ps1` (solo si el plan lo permite)

Tomar tal cual el de `multi-saas` (`scripts/github-branch-protection.ps1`): ajusta el repo
(squash y merge commit, borrar rama al fusionar) y crea rulesets: `main`/`release` solo
*merge commit*, `develop` solo *squash*, PR obligatorio, sin borrado ni force-push, con
`-RequiredChecks` opcional. **No funciona en repos privados con plan Free** (el código lo
intenta y GitHub lo ignora/rechaza). Revisar nombres de ramas.

## 9. Plantillas de GitHub

Copiar de `multi-saas` sin cambios (ya son genéricas):
`.github/PULL_REQUEST_TEMPLATE.md` (resumen, `Closes #`, tipo de PR, checklist: rama/destino
correctos, spec enlazada, tests y CI, sin secretos/datos personales, docs/ADR, Conventional
Commits), `.github/ISSUE_TEMPLATE/{feature,bug,adr,config}.yml` y `docs/adr/0000-template.md`
(estado, fecha, contexto, opciones, decisión, consecuencias). **Quitar** del PR/bug cualquier
mención a *tenants* si no aplica al template (hay un checkbox de fuga entre tenants en
`bug.yml` y una línea en la plantilla de PR).

### Cómo reutilizar el template en un proyecto nuevo

1. En GitHub: **Use this template** → nuevo repo (decidir público/privado).
2. Copiar el Project plantilla: `gh project copy <N> --source-owner <owner> --target-owner <owner> --title "<Proyecto> Roadmap"`
   (copia campos, estados y **vistas**; basta crear las vistas una sola vez en la plantilla
   y marcarla *template* en Settings).
3. Crear ramas: `git branch develop; git branch release; git push -u origin main develop release`.
4. Editar el backlog `.github/project/backlog.json` a las fases del proyecto y lanzar el
   bootstrap con `-Repo owner/nuevo -ProjectTitle "..."`. Si se quiere usar el Project ya
   copiado, pasar su título exacto en `-ProjectTitle`.
5. `/speckit-constitution` para fijar la constitución del proyecto (§5) y empezar por las
   tarjetas de la Fase 1 (Planteamiento).

## 10. Orden de ejecución del playbook

1. Responder las preguntas de §3.
2. Instalar y autenticar `gh` con scopes `repo` y `project` (§11.1).
3. Crear el repo (template habilitado), copiar Spec Kit (`.claude/`, `.specify/`) y el resto
   de la estructura (§4).
4. Generar constitución (§5), guía (§6), plantillas (§9), scripts (§8) y backlog (§7).
5. Crear ramas permanentes y subirlas; el primer commit puede ir a `main` (no hay
   protección aún); a partir de ahí, todo por PR a `develop` (dogfooding del flujo).
6. Lanzar el bootstrap (repetir hasta que la verificación no muestre faltantes).
7. Crear las vistas del Project a mano, marcarlo como template y verificar `gh project copy`.
8. Marcar el repo como template (Settings → Template repository) y probar creando un repo
   de prueba desde él.

## 11. Trampas conocidas (aprendidas montando `multi-saas`)

1. **`gh` en Windows:** tras instalar con winget hay que reiniciar la terminal para el PATH;
   ruta típica `C:\Program Files\GitHub CLI\gh.exe`. El scope `project` no viene por defecto:
   `gh auth login -s project,repo` o `gh auth refresh -s project`.
2. **`!` en Claude Code ejecuta bash**, no PowerShell: no usar `&` ni sintaxis PS. En bash:
   `! "/c/Program Files/GitHub CLI/gh.exe" auth refresh -h github.com -s project`. Si se
   hace el login en otra terminal, el asistente puede no ver la sesión (comprobar con
   `gh auth status` desde su propio shell).
3. **PowerShell 5.1:** `$F` y `$f` son la misma variable; `-f title=$m.title` pasa el objeto
   entero (usar `-f "title=$($m.title)"`; esto creó milestones con títulos corruptos);
   consultas GraphQL inline pierden las comillas → pasarlas con `-F query=@fichero`;
   `--jq` con comillas falla → usar `ConvertFrom-Json`; evitar `2>&1` con ejecutables nativos.
4. **GitHub inestable a ratos:** 502 y "Something went wrong while executing your query".
   Reintentos en el script y varias pasadas; `item-list` va con retraso (esperar antes de contar).
5. **Free + privado:** sin protección de ramas ni rulesets. Documentarlo en la constitución;
   las alternativas son repo público o plan Pro.
6. **Project views:** no hay API para crearlas; hacerlo a mano una vez en la plantilla.
   El Status personalizado sí se puede cambiar por GraphQL (`updateProjectV2Field`).
7. **Numeración:** el número del Project es por owner (puede haber proyectos previos); usar
   el que devuelva `project list`.
8. **Fin de línea:** Git avisa de LF→CRLF en Windows; añadir `.gitattributes` (`* text=auto eol=lf`).
9. **Primer commit antes de proteger:** subir la base a `main`/`develop`/`release` antes de
   activar rulesets, o el propio bootstrap no podrá empujar.
10. **Merge por CLI** (`gh pr merge --squash --delete-branch`) puede fallar por errores
    transitorios aunque el estado siga `OPEN`: reintentar y comprobar `gh pr view`.
11. **Spec Kit:** `/speckit-taskstoissues` está *deprecated*; para convertir tareas de una
    spec en issues usar el bootstrap o crear las issues a mano en el Project.

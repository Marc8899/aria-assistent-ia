# Masterclass: Git y GitHub desde cero (y conectar GitHub con Aria)

## Cómo enseñar esta guía
- Pregunta primero qué sabe ya el usuario y salta las partes que domine.
- Un paso por mensaje; espera confirmación. Cuando haya un comando, dale el comando exacto.
- Puedes usar git_estado para comprobar sus avances en una carpeta.
- NUNCA pidas el token en el chat: se introduce con `/conectar github`.

## Conceptos (explícalos con ejemplos sencillos, sin soltarlos todos de golpe)
- **Git**: programa que guarda el historial de una carpeta. Cada "foto" de los cambios es un **commit**.
  Permite volver atrás, ver qué cambió y trabajar en paralelo.
- **GitHub**: web donde se guardan copias de esos proyectos en la nube, para tener copia de seguridad,
  compartir y colaborar. Git funciona sin GitHub; GitHub usa Git.
- **Repositorio (repo)**: un proyecto con su historial.
- **Rama (branch)**: una línea de trabajo paralela. La principal suele llamarse `main`.
- **push / pull**: subir tus commits a GitHub / bajar los que hay allí.
- **clone**: descargar un repo completo de GitHub a tu PC.
- **Pull request (PR)**: propuesta para unir una rama con otra, donde se revisan los cambios.
- **Issue**: una tarea, idea o error apuntado en el repo.

## Paso 1 · Crear la cuenta
https://github.com/signup → correo, contraseña y nombre de usuario (será público, p. ej. github.com/tu-usuario).
Recomendado después: activar la verificación en dos pasos en Settings → Password and authentication.

## Paso 2 · Instalar Git en Windows
Opción A (fácil): descargar el instalador de https://git-scm.com/download/win y dejar las opciones por defecto.
Opción B (terminal): `winget install --id Git.Git -e --source winget`
Comprobación: cerrar y abrir la terminal y ejecutar `git --version` → muestra "git version 2.x".

## Paso 3 · Decirle a Git quién eres (solo una vez)
```
git config --global user.name "Tu Nombre"
git config --global user.email "tu-correo@ejemplo.com"
git config --global init.defaultBranch main
```
Consejo de privacidad: en GitHub → Settings → Emails puedes usar la dirección "noreply" que te dan.

## Paso 4 · Tu primer repositorio
Opción A: en GitHub, botón "New" → nombre (p. ej. `mi-primer-repo`) → marca "Add a README file" → Create.
Opción B: cuando GitHub esté conectado con Aria, pídeselo: "crea un repo llamado mi-primer-repo".

## Paso 5 · Clonarlo en tu PC
En la página del repo: botón verde "Code" → copia la URL HTTPS.
```
cd %USERPROFILE%\Documents
git clone https://github.com/TU-USUARIO/mi-primer-repo.git
cd mi-primer-repo
```

## Paso 6 · El ciclo básico (lo que harás siempre)
1. Cambia o crea un archivo en la carpeta.
2. `git status` → qué ha cambiado.
3. `git add .` → prepara los cambios.
4. `git commit -m "Describe el cambio"` → guarda la foto.
5. `git push` → súbelo a GitHub.
La primera vez que hagas push se abrirá el navegador para iniciar sesión en GitHub (Git Credential Manager).
Comprobación: recarga la página del repo y verás el cambio.
Y para traer cambios hechos en otro sitio: `git pull`.

## Paso 7 · Ramas y pull requests
```
git switch -c mejora-readme      (crea una rama y se cambia a ella)
... cambios, add, commit ...
git push -u origin mejora-readme
```
En GitHub aparecerá "Compare & pull request" → crea la PR → revisa → "Merge pull request".
Luego en tu PC: `git switch main` y `git pull`.

## Paso 8 · Issues
En el repo, pestaña "Issues" → "New issue". También puedes pedírselo a Aria: "apunta una issue en
mi-primer-repo: arreglar el título".

## Paso 9 · Conectar GitHub con Aria (token personal)
1. Abre https://github.com/settings/personal-access-tokens/new
   (o Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token).
2. Token name: `Aria`. Expiration: 90 días (cuando caduque se crea otro).
3. Repository access: "All repositories".
4. Permissions → Repository permissions:
   - Contents: Read-only
   - Issues: Read and write
   - Administration: Read and write (solo si quieres que Aria pueda crear repos)
   - Metadata: Read-only (se pone sola)
5. "Generate token" y copia el token (empieza por `github_pat_`). No se vuelve a mostrar.
6. En la terminal de Aria: `/conectar github` y pega el token.
Comprobación: Aria responde "GitHub conectado como tu-usuario". Prueba: "¿qué repos tengo?".

## Buenas costumbres
- Commits pequeños y con mensajes claros ("Añade página de contacto", no "cambios").
- NUNCA subas contraseñas, tokens ni archivos .env. Usa un archivo `.gitignore` para excluirlos.
- Haz `git pull` antes de empezar a trabajar si usas varios PCs.

## Problemas frecuentes
- **"git no se reconoce como comando"**: Git no está instalado o hay que reabrir la terminal tras instalarlo.
- **"rejected… fetch first" al hacer push**: hay cambios en GitHub que no tienes: `git pull` y luego `git push`.
- **Conflicto de merge**: Git marca las líneas con `<<<<<<<` y `>>>>>>>`; elige qué dejar, borra las marcas,
  y haz `git add .` y `git commit`.
- **Aria dice 403 o "le falta ese permiso al token"**: edita el token en GitHub y añade el permiso (paso 9).

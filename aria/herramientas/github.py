# GitHub por su API REST con un token personal (/conectar github), y git local.
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from aria import secretos

GRUPO = "github"
PALABRAS_CLAVE = ("github", "git", "repo", "issue", "commit", "push", "pull", "rama", "clonar")
API = "https://api.github.com"


class ErrorGitHub(Exception):
    pass


def comprobar_conexion():
    if not secretos.obtener("github_token"):
        raise ErrorGitHub(
            "GitHub no está conectado. Ofrece al usuario conectarlo; si acepta, llama a consultar_guia('github') "
            "y sigue el paso 9 (token fine-grained). No des instrucciones de memoria. "
            "Al final tendrá que escribir /conectar github."
        )


def peticion(metodo: str, ruta: str, datos: dict | None = None, token: str | None = None, requiere_token=False):
    if requiere_token and not token:
        comprobar_conexion()
    token = token or secretos.obtener("github_token")
    cabeceras = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "Aria-asistente"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    solicitud = urllib.request.Request(API + ruta, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(solicitud, timeout=20) as respuesta:
            return json.loads(respuesta.read() or b"null")
    except urllib.error.HTTPError as e:
        detalle = e.read().decode(errors="replace")[:300]
        if e.code == 401:
            raise ErrorGitHub("El token de GitHub no es válido o ha caducado. Que el usuario repita /conectar github.")
        if e.code == 403:
            raise ErrorGitHub(f"GitHub deniega el permiso (¿le falta ese permiso al token?): {detalle}")
        if e.code == 404:
            raise ErrorGitHub("No encontrado. Si el repositorio es privado, hace falta un token con acceso a él.")
        raise ErrorGitHub(f"GitHub respondió {e.code}: {detalle}")


def _nombre_repo(repo: str) -> str:
    repo = repo.strip().removesuffix(".git").rstrip("/")
    return repo.split("github.com/")[-1]


def registrar(registro, ctx):
    @registro.herramienta("Lista los repositorios del usuario en GitHub, los más recientes primero.")
    def github_mis_repos() -> str:
        repos = peticion("GET", "/user/repos?sort=updated&per_page=20", requiere_token=True)
        return "\n".join(
            f"- {r['full_name']}{' (privado)' if r['private'] else ''}: {r['description'] or 'sin descripción'} "
            f"· actualizado {r['updated_at'][:10]}"
            for r in repos
        ) or "No tiene repositorios."

    @registro.herramienta(
        "Información de un repositorio de GitHub y sus últimos commits.",
        repo="'usuario/repositorio' o la URL",
    )
    def github_repo(repo: str) -> str:
        nombre = _nombre_repo(repo)
        r = peticion("GET", f"/repos/{nombre}")
        commits = peticion("GET", f"/repos/{nombre}/commits?per_page=5")
        lineas = [f"{r['full_name']} · {r['description'] or 'sin descripción'}",
                  f"Lenguaje: {r['language']} · estrellas: {r['stargazers_count']} · "
                  f"issues abiertas: {r['open_issues_count']} · rama principal: {r['default_branch']}",
                  f"URL: {r['html_url']}", "Últimos commits:"]
        lineas += [f"- {c['commit']['author']['date'][:10]} {c['commit']['message'].splitlines()[0]}"
                   for c in commits]
        return "\n".join(lineas)

    @registro.herramienta(
        "Lista las issues de un repositorio de GitHub.",
        repo="'usuario/repositorio' o la URL",
        estado="open, closed o all",
    )
    def github_issues(repo: str, estado: str = "open") -> str:
        issues = peticion("GET", f"/repos/{_nombre_repo(repo)}/issues?state={estado}&per_page=20")
        issues = [i for i in issues if "pull_request" not in i]
        return "\n".join(f"- #{i['number']} [{i['state']}] {i['title']}" for i in issues) or "No hay issues."

    @registro.herramienta(
        "Crea una issue (tarea o error) en un repositorio de GitHub. El usuario la aprobará antes.",
        confirmar=True,
        requisito=comprobar_conexion,
        repo="'usuario/repositorio' o la URL",
        titulo="Título de la issue",
        cuerpo="Descripción",
    )
    def github_crear_issue(repo: str, titulo: str, cuerpo: str = "") -> str:
        issue = peticion("POST", f"/repos/{_nombre_repo(repo)}/issues", {"title": titulo, "body": cuerpo},
                         requiere_token=True)
        return f"Issue #{issue['number']} creada: {issue['html_url']}"

    @registro.herramienta(
        "Crea un repositorio nuevo en la cuenta de GitHub del usuario. El usuario lo aprobará antes.",
        confirmar=True,
        requisito=comprobar_conexion,
        nombre="Nombre del repositorio (sin espacios)",
        descripcion="Descripción corta",
        privado="true para que sea privado",
    )
    def github_crear_repo(nombre: str, descripcion: str = "", privado: bool = True) -> str:
        r = peticion("POST", "/user/repos",
                     {"name": nombre, "description": descripcion, "private": privado, "auto_init": True},
                     requiere_token=True)
        return f"Repositorio creado: {r['html_url']} (para clonarlo: git clone {r['clone_url']})"

    @registro.herramienta(
        "Muestra el estado de git de una carpeta local: rama, cambios pendientes y últimos commits.",
        carpeta="Ruta de la carpeta del proyecto",
    )
    def git_estado(carpeta: str) -> str:
        if not shutil.which("git"):
            return "Git no está instalado en este PC. La guía 'github' explica cómo instalarlo."
        ruta = Path(carpeta).expanduser()
        if not ruta.is_dir():
            return f"No existe la carpeta {ruta}."

        def git(*args):
            r = subprocess.run(["git", "-C", str(ruta), *args], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=20)
            return (r.stdout or r.stderr).strip()

        estado = git("status", "-sb")
        if "not a git repository" in estado:
            return f"{ruta} no es un repositorio de git (se crea con 'git init' o 'git clone')."
        return f"{estado}\n\nÚltimos commits:\n{git('log', '--oneline', '-5') or '(ninguno)'}"

#!/usr/bin/env python3
"""
command.py — Script di gestione cross-platform per PCBDEV.

Uso:
    python command.py --init       Crea la .venv e installa i requirements
    python command.py --update     Aggiorna il codice da GitHub (git pull)
    python command.py --compile    Compila l'eseguibile per il SO corrente
    python command.py --commit     Aggiunge, committa e pusha le modifiche
    python command.py --release    Crea un tag e attiva il rilascio automatico
    python command.py --all        Esegue --update, --init e --compile in sequenza
    python command.py --help       Mostra questo messaggio
"""
import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ============================================================
#  FIX ENCODING
# ============================================================
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


# ============================================================
#  COSTANTI
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
ENTRY_POINT = PROJECT_DIR / "src" / "main.py"
EXE_NAME = "pcbdev"
IS_WINDOWS = platform.system() == "Windows"
REPO_SLUG = "mvoud/pcbdev"   # ← cambio qui se il repo cambia


# ============================================================
#  OUTPUT
# ============================================================

class Colors:
    enabled = (sys.stdout.isatty() and os.environ.get("NO_COLOR") is None)
    RED    = "\033[0;31m" if enabled else ""
    GREEN  = "\033[0;32m" if enabled else ""
    YELLOW = "\033[1;33m" if enabled else ""
    BLUE   = "\033[0;34m" if enabled else ""
    BOLD   = "\033[1m"    if enabled else ""
    NC     = "\033[0m"    if enabled else ""


if IS_WINDOWS and not sys.stdout.encoding.lower().startswith("utf"):
    S_INFO, S_OK, S_WARN, S_ERR = "[i]", "[+]", "[!]", "[x]"
else:
    S_INFO, S_OK, S_WARN, S_ERR = "ℹ️", "✅", "⚠️", "❌"


def info(msg):  print(f"{Colors.BLUE}{S_INFO}  {msg}{Colors.NC}")
def ok(msg):    print(f"{Colors.GREEN}{S_OK} {msg}{Colors.NC}")
def warn(msg):  print(f"{Colors.YELLOW}{S_WARN}  {msg}{Colors.NC}")
def err(msg):   print(f"{Colors.RED}{S_ERR} {msg}{Colors.NC}", file=sys.stderr)


# ============================================================
#  UTILITÀ
# ============================================================

def run(cmd, cwd=None, check=True, capture=False):
    if isinstance(cmd, (list, tuple)):
        display = " ".join(str(c) for c in cmd)
    else:
        display = str(cmd)
    info(f"$ {display}")

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_DIR,
            check=check,
            text=True,
            capture_output=capture,
            encoding="utf-8" if capture else None,
            errors="replace" if capture else None,
        )
        return result
    except FileNotFoundError:
        err(f"Comando non trovato: {cmd[0] if isinstance(cmd, list) else cmd}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        if check:
            err(f"Comando fallito con codice {e.returncode}")
            if capture and e.stdout: print(e.stdout)
            if capture and e.stderr: print(e.stderr, file=sys.stderr)
            sys.exit(1)
        return e


def venv_python():
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / "python.exe"
    for name in ("python", "python3"):
        candidate = VENV_DIR / "bin" / name
        if candidate.exists():
            return candidate
    return VENV_DIR / "bin" / "python"


def venv_pip():
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / "pip.exe"
    for name in ("pip", "pip3"):
        candidate = VENV_DIR / "bin" / name
        if candidate.exists():
            return candidate
    return VENV_DIR / "bin" / "pip"


def venv_activate_cmd():
    if IS_WINDOWS:
        return f"{VENV_DIR}\\Scripts\\activate"
    return f"source {VENV_DIR}/bin/activate"


def ensure_git():
    if shutil.which("git") is None:
        err("git non è installato o non è nel PATH")
        sys.exit(1)
    if not (PROJECT_DIR / ".git").is_dir():
        err("Nessun repository Git trovato in questa directory")
        sys.exit(1)


def which_python():
    for name in ("python3", "python"):
        candidate = shutil.which(name)
        if candidate:
            return candidate
    err("Nessun Python trovato nel PATH. Installa Python 3.9+")
    sys.exit(1)


def git_tags():
    """Restituisce la lista dei tag locali (ordinati come dal git)."""
    result = run(["git", "tag", "--sort=version:refname"],
                 capture=True, check=False)
    if result.returncode != 0:
        return []
    return [t.strip() for t in result.stdout.splitlines() if t.strip()]


def ultima_versione():
    """Restituisce l'ultimo tag di versione (es. 'v1.0.0') o None."""
    tags = git_tags()
    return tags[-1] if tags else None


def bump_version(version, tipo="patch"):
    """
    Incrementa una versione semantica.
    :param version: stringa tipo 'v1.0.0'
    :param tipo: 'major', 'minor', 'patch'
    :return: stringa tipo 'v1.0.1'
    """
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)$", version)
    if not match:
        raise ValueError(f"Versione non valida: {version}")
    major, minor, patch = map(int, match.groups())
    if tipo == "major":
        return f"v{major + 1}.0.0"
    elif tipo == "minor":
        return f"v{major}.{minor + 1}.0"
    else:
        return f"v{major}.{minor}.{patch + 1}"


# ============================================================
#  COMANDI
# ============================================================

def cmd_init(args):
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== INIT ==={Colors.NC}\n")
    info(f"Python di sistema: {sys.version.split()[0]}")
    info(f"Piattaforma: {platform.system()} {platform.release()} ({platform.machine()})")

    if sys.version_info < (3, 9):
        err("Serve Python 3.9 o superiore")
        sys.exit(1)

    if VENV_DIR.is_dir():
        ok(f"Virtualenv già presente: {VENV_DIR}")
    else:
        info(f"Creazione virtualenv in {VENV_DIR}...")
        py = which_python()
        run([py, "-m", "venv", str(VENV_DIR)])
        ok("Virtualenv creata")

    py_venv = str(venv_python())
    pip_venv = str(venv_pip())

    info("Aggiornamento pip...")
    run([py_venv, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])

    if REQUIREMENTS.is_file():
        info(f"Installazione dipendenze da {REQUIREMENTS.name}...")
        run([pip_venv, "install", "-r", str(REQUIREMENTS), "--quiet"])
        ok("Dipendenze installate")
    else:
        warn(f"File non trovato: {REQUIREMENTS}")

    info("Verifica import del modulo main...")
    src_dir = str(PROJECT_DIR / "src")
    check_script = f"import sys; sys.path.insert(0, {src_dir!r}); import main"
    result = run([py_venv, "-c", check_script], check=False, capture=True)
    if result.returncode == 0:
        ok("Modulo 'main' importabile")
    else:
        warn("Impossibile importare 'main' — controlla la struttura src/")

    print()
    ok("Init completato!")
    print(f"   Attiva la venv con:")
    print(f"     {venv_activate_cmd()}")


def cmd_update(args):
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== UPDATE ==={Colors.NC}\n")
    ensure_git()

    result = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        check=False, capture=True,
    )
    if result.returncode != 0:
        warn("Nessun upstream configurato per il branch corrente")
        return

    upstream = result.stdout.strip()
    info(f"Upstream: {upstream}")

    info("Fetch dal remoto...")
    run(["git", "fetch", "--quiet"])

    local  = run(["git", "rev-parse", "HEAD"], capture=True).stdout.strip()
    remote = run(["git", "rev-parse", "@{u}"], capture=True).stdout.strip()

    if local == remote:
        ok("Repository già aggiornato")
        return

    status = run(["git", "status", "--porcelain"], capture=True).stdout.strip()
    if status:
        warn("Ci sono modifiche locali non committate:")
        print(status)
        warn("Salvale prima di aggiornare (git stash / git commit)")
        sys.exit(1)

    info("Aggiornamento in corso...")
    run(["git", "pull", "--ff-only"])
    ok("Repository aggiornato")


def cmd_commit(args):
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== COMMIT ==={Colors.NC}\n")
    ensure_git()

    info("Stato del repository:")
    status = run(["git", "status", "--short"], capture=True).stdout.rstrip()
    if not status:
        ok("Nessuna modifica da committare")
        return
    print(status)
    print()

    message = args.message
    if not message:
        info("Inserisci il messaggio di commit (lascia vuoto per annullare):")
        try:
            message = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            warn("Operazione annullata")
            return
        if not message:
            warn("Messaggio vuoto, commit annullato")
            return

    if args.paths:
        info(f"Aggiungo solo i file specificati: {args.paths}")
        for p in args.paths:
            run(["git", "add", p])
    else:
        info("Aggiungo tutte le modifiche (git add -A)...")
        run(["git", "add", "-A"])

    staged = run(["git", "diff", "--cached", "--name-only"], capture=True).stdout.strip()
    if not staged:
        warn("Nessun file in staging, commit annullato")
        return
    info(f"File in staging:\n{staged}")
    print()

    info(f"Commit: {message}")
    run(["git", "commit", "-m", message])
    ok("Commit creato")

    if args.no_push:
        info("--no-push: salto il push")
        return

    result = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        check=False, capture=True,
    )
    if result.returncode != 0:
        warn("Nessun upstream configurato, salto il push")
        return

    info("Push verso il remoto...")
    run(["git", "push"])
    ok("Push completato")


def cmd_release(args):
    """--release: crea un tag e attiva il rilascio automatico."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== RELEASE ==={Colors.NC}\n")
    ensure_git()

    # 1. Verifica modifiche non committate
    status = run(["git", "status", "--porcelain"], capture=True).stdout.strip()
    if status:
        warn("Ci sono modifiche non committate:")
        print(status)
        print()
        if args.message:
            info("Committo automaticamente con il messaggio fornito...")
            run(["git", "add", "-A"])
            run(["git", "commit", "-m", args.message])
            run(["git", "push"])
            ok("Commit + push completati")
        else:
            err("Committa prima le modifiche, oppure usa -m per farlo automaticamente")
            err("Esempio: python command.py --release -m 'Fix bug'")
            sys.exit(1)

    # 2. Determina la versione
    if args.version:
        nuova_versione = args.version
        if not nuova_versione.startswith("v"):
            nuova_versione = "v" + nuova_versione
    else:
        ultima = ultima_versione()
        if not ultima:
            nuova_versione = "v0.1.0"
            info(f"Nessun tag esistente, parto da {nuova_versione}")
        else:
            tipo = "major" if args.major else ("minor" if args.minor else "patch")
            nuova_versione = bump_version(ultima, tipo)
            info(f"Versione precedente: {ultima}")
            info(f"Nuova versione:      {nuova_versione} ({tipo})")

    # 3. Verifica che il tag non esista già
    if nuova_versione in git_tags():
        err(f"Il tag {nuova_versione} esiste già")
        err("Usa --version vX.Y.Z per specificarne uno diverso")
        sys.exit(1)

    # 4. Verifica di essere sul branch main
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                 capture=True).stdout.strip()
    if branch != "main":
        warn(f"Sei sul branch '{branch}', non 'main'")
        warn("Il workflow CI si attiva sul push di tag, non sul branch")

    # 5. Crea il tag
    info(f"Creazione tag {nuova_versione}...")
    run(["git", "tag", nuova_versione])
    ok(f"Tag {nuova_versione} creato localmente")

    # 6. Pusha il tag
    if args.no_push:
        info("--no-push: tag creato ma non pushato")
        info(f"Per pushare: git push origin {nuova_versione}")
        return

    info(f"Push del tag {nuova_versione}...")
    run(["git", "push", "origin", nuova_versione])
    ok(f"Tag {nuova_versione} pushato")

    # 7. Mostra link utili
    print()
    ok(f"Release {nuova_versione} avviata!")
    print()
    info("Monitora il progresso:")
    print(f"   https://github.com/{REPO_SLUG}/actions")
    print()
    info("La release sarà disponibile a:")
    print(f"   https://github.com/{REPO_SLUG}/releases/tag/{nuova_versione}")


def cmd_compile(args):
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== COMPILE ==={Colors.NC}\n")
    system = platform.system()
    info(f"Sistema operativo: {system} ({platform.machine()})")

    exe_name = EXE_NAME + (".exe" if IS_WINDOWS else "")

    if not VENV_DIR.is_dir():
        err("Virtualenv non trovata. Esegui prima: python command.py --init")
        sys.exit(1)

    py = str(venv_python())
    pip = str(venv_pip())

    result = run([py, "-c", "import PyInstaller"], check=False, capture=True)
    if result.returncode != 0:
        warn("PyInstaller non trovato, installazione in corso...")
        run([pip, "install", "pyinstaller", "--quiet"])
    version = run([py, "-m", "PyInstaller", "--version"], capture=True).stdout.strip()
    ok(f"PyInstaller: {version}")

    for d in ["build", "dist"]:
        p = PROJECT_DIR / d
        if p.is_dir():
            info(f"Rimozione {d}/...")
            shutil.rmtree(p)
    for spec in PROJECT_DIR.glob("*.spec"):
        spec.unlink()

    pyinstaller_cmd = [
        py, "-m", "PyInstaller",
        "--onefile", "--name", EXE_NAME,
        "--clean", "--noconfirm",
    ]

    if system == "Linux":
        if shutil.which("strip"):
            pyinstaller_cmd.append("--strip")

    if not ENTRY_POINT.is_file():
        err(f"Entry point non trovato: {ENTRY_POINT}")
        sys.exit(1)
    pyinstaller_cmd.append(os.fspath(ENTRY_POINT))

    info("Avvio PyInstaller...")
    run(pyinstaller_cmd)

    exe_path = PROJECT_DIR / "dist" / exe_name
    if not exe_path.is_file():
        err(f"Build fallita: {exe_path} non trovato")
        sys.exit(1)

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print()
    ok(f"Eseguibile compilato: {exe_path} ({size_mb:.1f} MB)")


def cmd_all(args):
    cmd_update(args)
    cmd_init(args)
    cmd_compile(args)


# ============================================================
#  MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        prog="command.py",
        description="Script di gestione per PCBDEV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python command.py --init                              Setup iniziale
  python command.py --update                            Aggiorna da GitHub
  python command.py --compile                           Compila l'eseguibile
  python command.py --commit -m "Fix generazione pin"   Commit + push
  python command.py --release                           Release (bump patch automatico)
  python command.py --release --minor                   Release (bump minor)
  python command.py --release --major                   Release (bump major)
  python command.py --release --version v2.0.0          Release con versione specifica
  python command.py --release -m "Fix bug"              Committa + release in un colpo
  python command.py --all                               Update + Init + Compile
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init",    action="store_true", help="Crea la .venv e installa i requirements")
    group.add_argument("--update",  action="store_true", help="Aggiorna il codice da GitHub")
    group.add_argument("--compile", action="store_true", help="Compila l'eseguibile per il SO corrente")
    group.add_argument("--commit",  action="store_true", help="Aggiunge, committa e pusha le modifiche")
    group.add_argument("--release", action="store_true", help="Crea un tag e attiva il rilascio automatico")
    group.add_argument("--all",     action="store_true", help="Esegue --update, --init e --compile")

    # Opzioni per --commit
    parser.add_argument("-m", "--message", type=str, default=None,
                        help="Messaggio di commit (solo con --commit o --release)")
    parser.add_argument("--no-push", action="store_true",
                        help="Non eseguire il push (solo con --commit o --release)")
    parser.add_argument("--paths", nargs="+", default=None,
                        help="Aggiungi solo questi file specifici (solo con --commit)")

    # Opzioni per --release
    parser.add_argument("--version", type=str, default=None,
                        help="Versione specifica (solo con --release, es. v2.0.0)")
    parser.add_argument("--major", action="store_true",
                        help="Bump major (solo con --release)")
    parser.add_argument("--minor", action="store_true",
                        help="Bump minor (solo con --release)")

    args = parser.parse_args()

    try:
        if args.init:      cmd_init(args)
        elif args.update:  cmd_update(args)
        elif args.compile: cmd_compile(args)
        elif args.commit:  cmd_commit(args)
        elif args.release: cmd_release(args)
        elif args.all:     cmd_all(args)
    except KeyboardInterrupt:
        print()
        warn("Interrotto dall'utente")
        sys.exit(130)


if __name__ == "__main__":
    main()
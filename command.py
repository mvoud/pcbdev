#!/usr/bin/env python3
"""
command.py — Script di gestione cross-platform per PCBDEV.

Uso:
    python command.py --init       Crea la .venv e installa i requirements
    python command.py --update     Aggiorna il codice da GitHub (git pull)
    python command.py --compile    Compila l'eseguibile per il SO corrente
    python command.py --commit     Aggiunge, committa e pusha le modifiche
    python command.py --all        Esegue --update, --init e --compile in sequenza
    python command.py --help       Mostra questo messaggio
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


# ============================================================
#  FIX ENCODING (Windows)
# ============================================================
# Su Windows la console usa cp1252 di default, che non può stampare
# emoji. Forziamo UTF-8 su stdout/stderr per evitare UnicodeEncodeError.

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
else:
    # Su Unix forziamo UTF-8 anche se il locale è "C" o "POSIX"
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


# ============================================================
#  UTILITÀ OUTPUT
# ============================================================

class Colors:
    """Colori ANSI, disattivati se non supportati."""
    enabled = (
        sys.stdout.isatty()
        and os.environ.get("NO_COLOR") is None
    )
    RED    = "\033[0;31m" if enabled else ""
    GREEN  = "\033[0;32m" if enabled else ""
    YELLOW = "\033[1;33m" if enabled else ""
    BLUE   = "\033[0;34m" if enabled else ""
    BOLD   = "\033[1m"    if enabled else ""
    NC     = "\033[0m"    if enabled else ""


# Simboli ASCII-safe per Windows (evita problemi con cp1252 in ambienti strani)
if IS_WINDOWS and not sys.stdout.encoding.lower().startswith("utf"):
    S_INFO  = "[i]"
    S_OK    = "[+]"
    S_WARN  = "[!]"
    S_ERR   = "[x]"
else:
    S_INFO  = "ℹ️"
    S_OK    = "✅"
    S_WARN  = "⚠️"
    S_ERR   = "❌"


def info(msg):  print(f"{Colors.BLUE}{S_INFO}  {msg}{Colors.NC}")
def ok(msg):    print(f"{Colors.GREEN}{S_OK} {msg}{Colors.NC}")
def warn(msg):  print(f"{Colors.YELLOW}{S_WARN}  {msg}{Colors.NC}")
def err(msg):   print(f"{Colors.RED}{S_ERR} {msg}{Colors.NC}", file=sys.stderr)


# ============================================================
#  UTILITÀ COMANDI
# ============================================================

def run(cmd, cwd=None, check=True, capture=False):
    """Esegue un comando mostrandolo a video."""
    # Su Windows, se il comando è una stringa con spazi, passiamo una lista
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
            if capture and e.stdout:
                print(e.stdout)
            if capture and e.stderr:
                print(e.stderr, file=sys.stderr)
            sys.exit(1)
        return e


def venv_python():
    """Percorso del python dentro la venv (cross-platform)."""
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / "python.exe"
    # Su Unix può essere python o python3
    for name in ("python", "python3"):
        candidate = VENV_DIR / "bin" / name
        if candidate.exists():
            return candidate
    return VENV_DIR / "bin" / "python"   # fallback


def venv_pip():
    """Percorso del pip dentro la venv (cross-platform)."""
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / "pip.exe"
    for name in ("pip", "pip3"):
        candidate = VENV_DIR / "bin" / name
        if candidate.exists():
            return candidate
    return VENV_DIR / "bin" / "pip"


def venv_activate_cmd():
    """Comando per attivare la venv, specifico per OS."""
    if IS_WINDOWS:
        return f"{VENV_DIR}\\Scripts\\activate"
    return f"source {VENV_DIR}/bin/activate"


def ensure_git():
    """Verifica che git sia installato e che siamo in un repo."""
    if shutil.which("git") is None:
        err("git non è installato o non è nel PATH")
        sys.exit(1)
    if not (PROJECT_DIR / ".git").is_dir():
        err("Nessun repository Git trovato in questa directory")
        sys.exit(1)


def which_python():
    """Restituisce il python di sistema da usare per creare la venv."""
    for name in ("python3", "python"):
        candidate = shutil.which(name)
        if candidate:
            return candidate
    err("Nessun Python trovato nel PATH. Installa Python 3.9+")
    sys.exit(1)


# ============================================================
#  COMANDI
# ============================================================

def cmd_init(args):
    """--init: crea la .venv e installa i requirements."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== INIT ==={Colors.NC}\n")

    info(f"Python di sistema: {sys.version.split()[0]}")
    info(f"Piattaforma: {platform.system()} {platform.release()} ({platform.machine()})")

    if sys.version_info < (3, 9):
        err("Serve Python 3.9 o superiore")
        sys.exit(1)

    # 1. Crea la venv se non esiste
    if VENV_DIR.is_dir():
        ok(f"Virtualenv già presente: {VENV_DIR}")
    else:
        info(f"Creazione virtualenv in {VENV_DIR}...")
        py = which_python()
        run([py, "-m", "venv", str(VENV_DIR)])
        ok("Virtualenv creata")

    py_venv = str(venv_python())
    pip_venv = str(venv_pip())

    # 2. Aggiorna pip
    info("Aggiornamento pip...")
    run([py_venv, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])

    # 3. Installa requirements
    if REQUIREMENTS.is_file():
        info(f"Installazione dipendenze da {REQUIREMENTS.name}...")
        run([pip_venv, "install", "-r", str(REQUIREMENTS), "--quiet"])
        ok("Dipendenze installate")
    else:
        warn(f"File non trovato: {REQUIREMENTS}")

    # 4. Verifica importabilità del main (con path esplicito, no raw string)
    info("Verifica import del modulo main...")
    src_dir = str(PROJECT_DIR / "src")
    check_script = f"import sys; sys.path.insert(0, {src_dir!r}); import main"
    result = run([py_venv, "-c", check_script], check=False, capture=True)
    if result.returncode == 0:
        ok("Modulo 'main' importabile")
    else:
        warn("Impossibile importare 'main' — controlla la struttura src/")
        if result.stderr:
            print(f"   Dettaglio: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'n/d'}")

    print()
    ok("Init completato!")
    print(f"   Attiva la venv con:")
    print(f"     {venv_activate_cmd()}")


def cmd_update(args):
    """--update: aggiorna il codice da GitHub con git pull."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== UPDATE ==={Colors.NC}\n")
    ensure_git()

    result = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        check=False, capture=True,
    )
    if result.returncode != 0:
        warn("Nessun upstream configurato per il branch corrente")
        warn("Configuralo con: git branch --set-upstream-to=origin/<branch>")
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
    """--commit: aggiunge, committa e pusha le modifiche."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== COMMIT ==={Colors.NC}\n")
    ensure_git()

    # 1. Stato attuale
    info("Stato del repository:")
    status = run(["git", "status", "--short"], capture=True).stdout.rstrip()
    if not status:
        ok("Nessuna modifica da committare")
        return
    print(status)
    print()

    # 2. Messaggio di commit
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

    # 3. Add
    if args.paths:
        info(f"Aggiungo solo i file specificati: {args.paths}")
        for p in args.paths:
            run(["git", "add", p])
    else:
        info("Aggiungo tutte le modifiche (git add -A)...")
        run(["git", "add", "-A"])

    # 4. Verifica staging
    staged = run(["git", "diff", "--cached", "--name-only"], capture=True).stdout.strip()
    if not staged:
        warn("Nessun file in staging, commit annullato")
        return
    info(f"File in staging:\n{staged}")
    print()

    # 5. Commit
    info(f"Commit: {message}")
    run(["git", "commit", "-m", message])
    ok("Commit creato")

    # 6. Push
    if args.no_push:
        info("--no-push: salto il push")
        return

    result = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        check=False, capture=True,
    )
    if result.returncode != 0:
        warn("Nessun upstream configurato, salto il push")
        warn("Configuralo con: git push -u origin <branch>")
        return

    info("Push verso il remoto...")
    run(["git", "push"])
    ok("Push completato")


def cmd_compile(args):
    """--compile: compila l'eseguibile in base al SO."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== COMPILE ==={Colors.NC}\n")

    system = platform.system()
    info(f"Sistema operativo: {system} ({platform.machine()})")

    exe_name = EXE_NAME + (".exe" if IS_WINDOWS else "")

    if not VENV_DIR.is_dir():
        err("Virtualenv non trovata. Esegui prima: python command.py --init")
        sys.exit(1)

    py = str(venv_python())
    pip = str(venv_pip())

    # Verifica/installa PyInstaller
    result = run([py, "-c", "import PyInstaller"], check=False, capture=True)
    if result.returncode != 0:
        warn("PyInstaller non trovato, installazione in corso...")
        run([pip, "install", "pyinstaller", "--quiet"])
    version = run([py, "-m", "PyInstaller", "--version"], capture=True).stdout.strip()
    ok(f"PyInstaller: {version}")

    # Pulizia
    for d in ["build", "dist"]:
        p = PROJECT_DIR / d
        if p.is_dir():
            info(f"Rimozione {d}/...")
            shutil.rmtree(p)
    for spec in PROJECT_DIR.glob("*.spec"):
        spec.unlink()

    # Comando base
    pyinstaller_cmd = [
        py, "-m", "PyInstaller",
        "--onefile",
        "--name", EXE_NAME,
        "--clean",
        "--noconfirm",
    ]

    # Opzioni specifiche per OS
    if system == "Linux":
        if shutil.which("strip"):
            pyinstaller_cmd.append("--strip")
        else:
            warn("'strip' non trovato, salto l'ottimizzazione binaria")
    elif system == "Darwin":
        # universal2 richiede Python universal; se fallisce, lo omettiamo
        # Lo aggiungiamo solo se l'utente lo richiede esplicitamente
        # pyinstaller_cmd.extend(["--target-arch", "universal2"])
        pass

    if not ENTRY_POINT.is_file():
        err(f"Entry point non trovato: {ENTRY_POINT}")
        sys.exit(1)
    pyinstaller_cmd.append(os.fspath(ENTRY_POINT))

    info("Avvio PyInstaller...")
    run(pyinstaller_cmd)

    # Verifica output
    exe_path = PROJECT_DIR / "dist" / exe_name
    if not exe_path.is_file():
        err(f"Build fallita: {exe_path} non trovato")
        sys.exit(1)

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print()
    ok(f"Eseguibile compilato: {exe_path} ({size_mb:.1f} MB)")
    print()
    info("Prossimi passi:")
    if IS_WINDOWS:
        print(f"   .\\dist\\{exe_name} <percorso_progetto>")
    else:
        print(f"   ./dist/{exe_name} <percorso_progetto>")
        print(f"   cp dist/{exe_name} ~/.local/bin/    → installazione nel PATH")


def cmd_all(args):
    """--all: esegue update, init e compile in sequenza."""
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
  python command.py --commit                            Commit interattivo
  python command.py --commit --no-push -m "WIP"         Commit senza push
  python command.py --all                               Update + Init + Compile
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init",    action="store_true", help="Crea la .venv e installa i requirements")
    group.add_argument("--update",  action="store_true", help="Aggiorna il codice da GitHub")
    group.add_argument("--compile", action="store_true", help="Compila l'eseguibile per il SO corrente")
    group.add_argument("--commit",  action="store_true", help="Aggiunge, committa e pusha le modifiche")
    group.add_argument("--all",     action="store_true", help="Esegue --update, --init e --compile")

    parser.add_argument("-m", "--message", type=str, default=None,
                        help="Messaggio di commit (solo con --commit)")
    parser.add_argument("--no-push", action="store_true",
                        help="Non eseguire il push (solo con --commit)")
    parser.add_argument("--paths", nargs="+", default=None,
                        help="Aggiungi solo questi file specifici (solo con --commit)")

    args = parser.parse_args()

    try:
        if args.init:      cmd_init(args)
        elif args.update:  cmd_update(args)
        elif args.compile: cmd_compile(args)
        elif args.commit:  cmd_commit(args)
        elif args.all:     cmd_all(args)
    except KeyboardInterrupt:
        print()
        warn("Interrotto dall'utente")
        sys.exit(130)


if __name__ == "__main__":
    main()
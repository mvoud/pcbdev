#!/usr/bin/env python3
"""
command.py — Script di gestione per PCBDEV.

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
from datetime import datetime
from pathlib import Path


# ============================================================
#  COSTANTI
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
ENTRY_POINT = PROJECT_DIR / "src" / "main.py"
EXE_NAME = "pcbdev"


# ============================================================
#  UTILITÀ
# ============================================================

class Colors:
    """Colori ANSI, disattivati automaticamente su Windows legacy."""
    enabled = sys.stdout.isatty() and platform.system() != "Windows"
    RED    = "\033[0;31m" if enabled else ""
    GREEN  = "\033[0;32m" if enabled else ""
    YELLOW = "\033[1;33m" if enabled else ""
    BLUE   = "\033[0;34m" if enabled else ""
    NC     = "\033[0m"  if enabled else ""


def info(msg):  print(f"{Colors.BLUE}ℹ️  {msg}{Colors.NC}")
def ok(msg):    print(f"{Colors.GREEN}✅ {msg}{Colors.NC}")
def warn(msg):  print(f"{Colors.YELLOW}⚠️  {msg}{Colors.NC}")
def err(msg):   print(f"{Colors.RED}❌ {msg}{Colors.NC}", file=sys.stderr)


def run(cmd, cwd=None, check=True, capture=False):
    """Esegue un comando mostrandolo a video."""
    info(f"$ {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_DIR,
            check=check,
            text=True,
            capture_output=capture,
        )
        return result
    except FileNotFoundError:
        err(f"Comando non trovato: {cmd[0]}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        if check:
            err(f"Comando fallito con codice {e.returncode}")
            sys.exit(1)
        return e


def venv_python():
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def venv_pip():
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"


def ensure_git():
    """Verifica che git sia installato e che siamo in un repo."""
    if shutil.which("git") is None:
        err("git non è installato o non è nel PATH")
        sys.exit(1)
    if not (PROJECT_DIR / ".git").is_dir():
        err("Nessun repository Git trovato in questa directory")
        sys.exit(1)


# ============================================================
#  COMANDI
# ============================================================

def cmd_init(args):
    """--init: crea la .venv e installa i requirements."""
    print(f"\n{Colors.BLUE}=== INIT ==={Colors.NC}\n")

    info(f"Python: {sys.version.split()[0]}")
    if sys.version_info < (3, 9):
        err("Serve Python 3.9 o superiore")
        sys.exit(1)

    if VENV_DIR.is_dir():
        ok(f"Virtualenv già presente: {VENV_DIR}")
    else:
        info(f"Creazione virtualenv in {VENV_DIR}...")
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
        ok("Virtualenv creata")

    info("Aggiornamento pip...")
    run([str(venv_python()), "-m", "pip", "install", "--upgrade", "pip", "--quiet"])

    if REQUIREMENTS.is_file():
        info(f"Installazione dipendenze da {REQUIREMENTS.name}...")
        run([str(venv_pip()), "install", "-r", str(REQUIREMENTS), "--quiet"])
        ok("Dipendenze installate")
    else:
        warn(f"File non trovato: {REQUIREMENTS}")

    info("Verifica import del modulo main...")
    check_cmd = [
        str(venv_python()), "-c",
        f"import sys; sys.path.insert(0, r'{PROJECT_DIR / 'src'}'); import main"
    ]
    result = run(check_cmd, check=False, capture=True)
    if result.returncode == 0:
        ok("Modulo 'main' importabile")
    else:
        warn("Impossibile importare 'main' — controlla la struttura src/")

    print()
    ok("Init completato!")
    print(f"   Attiva la venv con:")
    if platform.system() == "Windows":
        print(f"     {VENV_DIR}\\Scripts\\activate")
    else:
        print(f"     source {VENV_DIR}/bin/activate")


def cmd_update(args):
    """--update: aggiorna il codice da GitHub con git pull."""
    print(f"\n{Colors.BLUE}=== UPDATE ==={Colors.NC}\n")
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
    print(f"\n{Colors.BLUE}=== COMMIT ==={Colors.NC}\n")
    ensure_git()

    # 1. Mostra lo stato attuale
    info("Stato del repository:")
    status = run(["git", "status", "--short"], capture=True).stdout.rstrip()
    if not status:
        ok("Nessuna modifica da committare")
        return
    print(status)
    print()

    # 2. Determina il messaggio di commit
    message = args.message
    if not message:
        # Prompt interattivo
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

    # 3. Aggiungi tutti i file modificati
    if args.paths:
        info(f"Aggiungo solo i file specificati: {args.paths}")
        for p in args.paths:
            run(["git", "add", p])
    else:
        info("Aggiungo tutte le modifiche (git add -A)...")
        run(["git", "add", "-A"])

    # 4. Verifica che ci sia qualcosa in staging
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

    # 6. Push (opzionale)
    if args.no_push:
        info("--no-push: salto il push")
        return

    # Verifica upstream
    result = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        check=False, capture=True,
    )
    if result.returncode != 0:
        warn("Nessun upstream configurato, salto il push")
        warn(f"Configuralo con: git push -u origin <branch>")
        return

    info("Push verso il remoto...")
    run(["git", "push"])
    ok("Push completato")


def cmd_compile(args):
    """--compile: compila l'eseguibile in base al SO."""
    print(f"\n{Colors.BLUE}=== COMPILE ==={Colors.NC}\n")

    system = platform.system()
    info(f"Sistema operativo: {system} ({platform.machine()})")

    exe_name = EXE_NAME + (".exe" if system == "Windows" else "")

    if not VENV_DIR.is_dir():
        err("Virtualenv non trovata. Esegui prima: python command.py --init")
        sys.exit(1)

    py = str(venv_python())

    result = run([py, "-c", "import PyInstaller"], check=False, capture=True)
    if result.returncode != 0:
        warn("PyInstaller non trovato, installazione in corso...")
        run([str(venv_pip()), "install", "pyinstaller", "--quiet"])
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
        "--onefile",
        "--name", EXE_NAME,
        "--clean",
        "--noconfirm",
    ]

    if system == "Linux":
        pyinstaller_cmd.append("--strip")
    elif system == "Darwin":
        pyinstaller_cmd.extend(["--target-arch", "universal2"])

    if not ENTRY_POINT.is_file():
        err(f"Entry point non trovato: {ENTRY_POINT}")
        sys.exit(1)
    pyinstaller_cmd.append(str(ENTRY_POINT))

    info("Avvio PyInstaller...")
    run(pyinstaller_cmd)

    exe_path = PROJECT_DIR / "dist" / exe_name
    if not exe_path.is_file():
        err(f"Build fallita: {exe_path} non trovato")
        sys.exit(1)

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print()
    ok(f"Eseguibile compilato: {exe_path} ({size_mb:.1f} MB)")
    print()
    info("Prossimi passi:")
    if system == "Windows":
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
  python command.py --commit                            Commit interattivo (chiede il messaggio)
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

    # Opzioni specifiche per --commit
    parser.add_argument("-m", "--message", type=str, default=None,
                        help="Messaggio di commit (solo con --commit)")
    parser.add_argument("--no-push", action="store_true",
                        help="Non eseguire il push (solo con --commit)")
    parser.add_argument("--paths", nargs="+", default=None,
                        help="Aggiungi solo questi file specifici (solo con --commit)")

    args = parser.parse_args()

    if args.init:     cmd_init(args)
    elif args.update: cmd_update(args)
    elif args.compile: cmd_compile(args)
    elif args.commit: cmd_commit(args)
    elif args.all:    cmd_all(args)


if __name__ == "__main__":
    main()
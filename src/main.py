import os
import sys
import json
import shutil

from src.generator import genera_tutto


# Default sensati se config.json è assente
DEFAULT_CONFIG = {
    "footprint_output_dir": "~/.local/share/kicad/{kicad_version}/footprints/{project_name}.pretty",
    "symbol_output_dir":    "~/.local/share/kicad/{kicad_version}/symbols",
    "symbol_filename":      "{project_name}.kicad_sym",
    "copy_to_kicad":        True,
}


def trova_progetti(percorso):
    progetti = []

    def registra(cartella):
        layout = os.path.join(cartella, "layout.json")
        if os.path.isfile(layout):
            config = os.path.join(cartella, "config.json")
            progetti.append({
                "nome": os.path.basename(os.path.abspath(cartella)),
                "layout": layout,
                "config": config if os.path.isfile(config) else None,
            })

    if os.path.isfile(percorso) and percorso.endswith(".json"):
        registra(os.path.dirname(os.path.abspath(percorso)))
        return progetti

    if os.path.isdir(percorso):
        if os.path.isfile(os.path.join(percorso, "layout.json")):
            registra(percorso)
            return progetti
        for nome in sorted(os.listdir(percorso)):
            sub = os.path.join(percorso, nome)
            if os.path.isdir(sub):
                registra(sub)

    return progetti


def trova_ultima_versione_kicad():
    base = os.path.expanduser("~/.local/share/kicad")
    if not os.path.isdir(base):
        return None
    versioni = []
    for voce in os.listdir(base):
        if os.path.isdir(os.path.join(base, voce)):
            try:
                a, b = voce.split(".")
                versioni.append((int(a), int(b), voce))
            except ValueError:
                continue
    if not versioni:
        return None
    versioni.sort()
    return versioni[-1][2]


def risolvi_percorso(template, project_name, kicad_version):
    """Sostituisce i placeholder ed espande ~ nel percorso."""
    percorso = template.replace("{project_name}", project_name)
    percorso = percorso.replace("{kicad_version}", kicad_version or "")
    percorso = os.path.expanduser(percorso)
    return os.path.abspath(percorso)


def carica_config(config_path):
    """Carica config.json se esiste, altrimenti restituisce i default."""
    config = dict(DEFAULT_CONFIG)   # copia dei default

    if config_path and os.path.isfile(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            utente = json.load(f)
        config.update(utente)       # override con i valori dell'utente

    return config


def copia_in_kicad(src, dest_dir, file_name):
    os.makedirs(dest_dir, exist_ok=True)
    dst = os.path.join(dest_dir, file_name)
    shutil.copy2(src, dst)
    print(f"📦 Copiato in KiCad: {dst}")


def main():
    versione = trova_ultima_versione_kicad()
    if versione:
        print(f"🔍 KiCad rilevato: versione {versione}")
    else:
        print("⚠️  Nessuna installazione KiCad trovata in ~/.local/share/kicad/")

    target = "." if len(sys.argv) < 2 else sys.argv[1].strip().strip('"').strip("'")
    progetti = trova_progetti(target)
    if not progetti:
        print(f"❌ Nessun progetto (layout.json) trovato in: {target}")
        sys.exit(1)

    print(f"\n🔍 Trovati {len(progetti)} progetti\n")

    for progetto in progetti:
        print(f"📄 {progetto['layout']}")
        config = carica_config(progetto["config"])

        try:
            risultati = genera_tutto(
                progetto["layout"],
                library_nickname=progetto["nome"],
            )

            # Se copy_to_kicad è False, salta la copia (solo build locale)
            if not config.get("copy_to_kicad", True):
                print("⏭️  copy_to_kicad=false: salto la copia in KiCad")
                print()
                continue

            # --- Copia footprints ---
            if "footprints" in risultati:
                fp_tpl = config.get("footprint_output_dir")
                if fp_tpl:
                    dest_dir = risolvi_percorso(fp_tpl, progetto["nome"], versione)
                    for fp_path in risultati["footprints"]:
                        fn = os.path.basename(fp_path)
                        copia_in_kicad(fp_path, dest_dir, fn)
                else:
                    print("⚠️  config: manca 'footprint_output_dir'")

            # --- Copia simbolo ---
            if "symbol" in risultati:
                sym_tpl = config.get("symbol_output_dir")
                if sym_tpl:
                    dest_dir = risolvi_percorso(sym_tpl, progetto["nome"], versione)
                    fn_tpl = config.get("symbol_filename", "{project_name}.kicad_sym")
                    fn = fn_tpl.replace("{project_name}", progetto["nome"])
                    copia_in_kicad(risultati["symbol"], dest_dir, fn)
                else:
                    print("⚠️  config: manca 'symbol_output_dir'")

        except Exception as e:
            print(f"❌ Errore: {e}")
        print()


if __name__ == "__main__":
    main()
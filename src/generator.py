import os
import json

from KicadModTree import Footprint, Pad, Text, RectLine, Circle
from KicadModTree import KicadFileHandler


# ============================================================
#  UTILITÀ COMUNI
# ============================================================

def _carica_layout(layout_path):
    """Legge layout.json e restituisce il dizionario board."""
    if not os.path.isfile(layout_path):
        raise FileNotFoundError(f"layout.json non trovato: {layout_path}")

    with open(layout_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "board" not in data:
        raise ValueError("layout.json: manca la chiave 'board'")

    return data["board"]


def _prepara_output_dir(layout_path):
    project_dir = os.path.dirname(os.path.abspath(layout_path))
    output_dir = os.path.join(project_dir, "build")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _aggiungi_contorno(kicad_mod, board, name):
    """Aggiunge riferimento, valore, serigrafia e courtyard (comuni a tutti i footprint)."""
    dims = board.get("dimensions", {})
    pcb_w = float(dims.get("width", 60.0))
    pcb_h = float(dims.get("height", 30.0))

    kicad_mod.append(Text(
        type='reference', text='REF**',
        at=[0, -pcb_h / 2 - 2], layer='F.SilkS'
    ))
    kicad_mod.append(Text(
        type='value', text=name,
        at=[0, pcb_h / 2 + 2], layer='F.Fab'
    ))
    kicad_mod.append(RectLine(
        start=[-pcb_w / 2, -pcb_h / 2],
        end=[pcb_w / 2, pcb_h / 2],
        layer='F.SilkS', width=0.15
    ))
    kicad_mod.append(RectLine(
        start=[-pcb_w / 2 - 0.25, -pcb_h / 2 - 0.25],
        end=[pcb_w / 2 + 0.25, pcb_h / 2 + 0.25],
        layer='F.CrtYd', width=0.05
    ))


# ============================================================
#  HELPER PER POSIZIONAMENTO PAD
# ============================================================

def _posizioni_pad(n_left, n_right, pitch, offset, rotation):
    """
    Restituisce due liste di coordinate (x, y) per i pad dei lati sinistro e destro.
    rotation=0  → colonne verticali (passo in Y, offset in X)
    rotation=90 → righe orizzontali (passo in X, offset in Y)
    """
    n_max = max(n_left, n_right)
    start = -((n_max - 1) * pitch) / 2

    left_pos, right_pos = [], []
    for i in range(n_max):
        if rotation == 90:
            left_pos.append((start + i * pitch, -offset))
            right_pos.append((start + i * pitch, +offset))
        else:
            left_pos.append((-offset, start + i * pitch))
            right_pos.append((+offset, start + i * pitch))
    return left_pos, right_pos


# ============================================================
#  GENERATORI DI FOOTPRINT (uno per tipo)
# ============================================================

def _fp_tht_dual_row(board, fp_cfg, kicad_mod):
    """Due file di pad THT (verticale o orizzontale)."""
    pitch    = float(fp_cfg["pitch_y"])
    offset   = float(fp_cfg["offset_x"])
    pad_dia  = float(fp_cfg["pad_diameter"])
    drill    = float(fp_cfg["drill"])
    rotation = int(fp_cfg.get("rotation", 0))

    pins = board["pins"]
    left_pins  = [p for p in pins if p.get("side", "left") == "left"]
    right_pins = [p for p in pins if p.get("side") == "right"]

    left_pos, right_pos = _posizioni_pad(
        len(left_pins), len(right_pins), pitch, offset, rotation
    )

    for (x, y), pin in zip(left_pos, left_pins):
        kicad_mod.append(Pad(
            number=pin["number"], type=Pad.TYPE_THT,
            shape=Pad.SHAPE_CIRCLE,
            at=[x, y], size=[pad_dia, pad_dia], drill=drill,
            layers=Pad.LAYERS_THT
        ))

    for (x, y), pin in zip(right_pos, right_pins):
        kicad_mod.append(Pad(
            number=pin["number"], type=Pad.TYPE_THT,
            shape=Pad.SHAPE_CIRCLE,
            at=[x, y], size=[pad_dia, pad_dia], drill=drill,
            layers=Pad.LAYERS_THT
        ))

    # Indicatore pin 1
    if left_pos:
        x0, y0 = left_pos[0]
        kicad_mod.append(Circle(
            center=[x0, y0], radius=1.5, layer='F.SilkS', width=0.15
        ))


def _fp_smd_dual_row(board, fp_cfg, kicad_mod):
    """Due file di pad SMD rettangolari (verticale o orizzontale)."""
    pitch    = float(fp_cfg["pitch_y"])
    offset   = float(fp_cfg["offset_x"])
    pad_w    = float(fp_cfg.get("pad_width", 1.5))
    pad_h    = float(fp_cfg.get("pad_height", 1.0))
    rotation = int(fp_cfg.get("rotation", 0))

    pins = board["pins"]
    left_pins  = [p for p in pins if p.get("side", "left") == "left"]
    right_pins = [p for p in pins if p.get("side") == "right"]

    left_pos, right_pos = _posizioni_pad(
        len(left_pins), len(right_pins), pitch, offset, rotation
    )

    for (x, y), pin in zip(left_pos, left_pins):
        kicad_mod.append(Pad(
            number=pin["number"], type=Pad.TYPE_SMT,
            shape=Pad.SHAPE_RECT,
            at=[x, y], size=[pad_w, pad_h],
            layers=Pad.LAYERS_SMT
        ))

    for (x, y), pin in zip(right_pos, right_pins):
        kicad_mod.append(Pad(
            number=pin["number"], type=Pad.TYPE_SMT,
            shape=Pad.SHAPE_RECT,
            at=[x, y], size=[pad_w, pad_h],
            layers=Pad.LAYERS_SMT
        ))

    if left_pos:
        x0, y0 = left_pos[0]
        kicad_mod.append(Circle(
            center=[x0, y0], radius=1.5, layer='F.SilkS', width=0.15
        ))


def _fp_tht_castellated(board, fp_cfg, kicad_mod):
    """Pad a castello: fori passanti con pad ovale allungato (verticale o orizzontale)."""
    pitch    = float(fp_cfg["pitch_y"])
    offset   = float(fp_cfg["offset_x"])
    pad_dia  = float(fp_cfg["pad_diameter"])
    drill    = float(fp_cfg["drill"])
    rotation = int(fp_cfg.get("rotation", 0))

    pins = board["pins"]
    left_pins  = [p for p in pins if p.get("side", "left") == "left"]
    right_pins = [p for p in pins if p.get("side") == "right"]

    left_pos, right_pos = _posizioni_pad(
        len(left_pins), len(right_pins), pitch, offset, rotation
    )

    # Forma del pad ovale: dipende dall'orientamento
    if rotation == 90:
        size = [pad_dia * 1.5, pad_dia]     # ovale orizzontale
    else:
        size = [pad_dia, pad_dia * 1.5]     # ovale verticale

    for (x, y), pin in zip(left_pos, left_pins):
        kicad_mod.append(Pad(
            number=pin["number"], type=Pad.TYPE_THT,
            shape=Pad.SHAPE_OVAL,
            at=[x, y], size=size, drill=drill,
            layers=Pad.LAYERS_THT
        ))

    for (x, y), pin in zip(right_pos, right_pins):
        kicad_mod.append(Pad(
            number=pin["number"], type=Pad.TYPE_THT,
            shape=Pad.SHAPE_OVAL,
            at=[x, y], size=size, drill=drill,
            layers=Pad.LAYERS_THT
        ))

    if left_pos:
        x0, y0 = left_pos[0]
        kicad_mod.append(Circle(
            center=[x0, y0], radius=1.5, layer='F.SilkS', width=0.15
        ))


# --- Dispatcher per tipo ---
_FOOTPRINT_GENERATORS = {
    "tht_dual_row":    _fp_tht_dual_row,
    "smd_dual_row":    _fp_smd_dual_row,
    "tht_castellated": _fp_tht_castellated,
}


# ============================================================
#  GENERATORE FOOTPRINT (.kicad_mod)
# ============================================================

def _genera_footprint(board, output_dir):
    """
    Genera uno o più file .kicad_mod in base all'array 'footprints'.
    Fallback retrocompatibile: se 'footprints' non c'è, usa 'pads' come singolo footprint.
    Restituisce la lista dei percorsi generati.
    """
    footprints_cfg = board.get("footprints")

    # Fallback: vecchio formato con singolo "pads"
    if not footprints_cfg:
        if "pads" in board:
            footprints_cfg = [{
                "name": board["name"],
                "type": "tht_dual_row",
                "pitch_y": board["pads"]["pitch_y"],
                "offset_x": board["pads"]["offset_x"],
                "pad_diameter": board["pads"].get("diameter", board["pads"].get("pad_diameter")),
                "drill": board["pads"]["drill"],
            }]
        else:
            raise ValueError("layout.json: manca 'footprints' o 'pads'")

    output_paths = []
    description = board.get("description", board["name"])
    tags = board.get("tags", [])

    for fp_cfg in footprints_cfg:
        fp_name = fp_cfg.get("name", board["name"])
        fp_type = fp_cfg.get("type", "tht_dual_row")

        if fp_type not in _FOOTPRINT_GENERATORS:
            print(f"⚠️  Tipo footprint sconosciuto: {fp_type} (salto {fp_name})")
            continue

        kicad_mod = Footprint(fp_name)
        kicad_mod.setDescription(description)
        kicad_mod.setTags(" ".join(tags))

        # Contorno comune (serigrafia + courtyard)
        _aggiungi_contorno(kicad_mod, board, fp_name)

        # Pad specifici del tipo
        _FOOTPRINT_GENERATORS[fp_type](board, fp_cfg, kicad_mod)

        # Salvataggio
        output_path = os.path.join(output_dir, f"{fp_name}.kicad_mod")
        KicadFileHandler(kicad_mod).writeFile(output_path)
        rot_info = f", rotation={fp_cfg.get('rotation', 0)}"
        print(f"✅ Footprint [{fp_type}{rot_info}] generato: {output_path}")
        output_paths.append(output_path)

    return output_paths


# ============================================================
#  GENERATORE SIMBOLO (.kicad_sym)
# ============================================================

# Tipo pin KiCad (S-expression) <-> tipo del layout.json
_PIN_TYPE_MAP = {
    "power_in":      "power_in",
    "power_out":     "power_out",
    "input":         "input",
    "output":        "output",
    "bidirectional": "bidirectional",
    "passive":       "passive",
    "open_collector":"open_collector",
    "open_emitter":  "open_emitter",
    "no_connect":    "no_connect",
    "unspecified":   "unspecified",
}


def _genera_simbolo_s_expr(board, footprint_ref=""):
    """
    Genera la stringa S-expression del simbolo KiCad.
    :param footprint_ref: stringa tipo "NICKNAME:FOOTPRINT_NAME" da scrivere
                          nella proprietà Footprint del simbolo.
    """
    name = board["name"]
    pins = board["pins"]

    left_pins  = [p for p in pins if p.get("side", "left") == "left"]
    right_pins = [p for p in pins if p.get("side") == "right"]

    n_max = max(len(left_pins), len(right_pins))

    # --- Geometria (leggibile dal layout.json, con default sensati) ---
    sym_cfg = board.get("symbol", {})
    grid     = 2.54
    pin_len  = float(sym_cfg.get("pin_length", 2.54))
    name_off = float(sym_cfg.get("name_offset", 1.016))

    # Larghezza: dal JSON se presente, altrimenti calcolata dal nome più lungo
    if "body_width" in sym_cfg:
        body_w = float(sym_cfg["body_width"])
    else:
        max_name_len = max((len(str(p["name"])) for p in pins), default=4)
        body_w = max(15.24, (max_name_len + 2) * 1.27)
        body_w = round(body_w / grid) * grid

    # Altezza: dal JSON se presente, altrimenti calcolata dal numero di pin
    if "body_height" in sym_cfg:
        body_h = float(sym_cfg["body_height"])
    else:
        body_h = (n_max + 1) * grid

    half_w = body_w / 2
    half_h = body_h / 2
    top_y = (n_max - 1) * grid / 2

    lines = []
    lines.append("(kicad_symbol_lib (version 20211014) (generator kicad_generator)")
    lines.append(f'  (symbol "{name}"')
    lines.append(f'    (pin_names (offset {name_off}))')
    lines.append('    (in_bom yes) (on_board yes)')

    # --- Proprietà ---
    lines.append(f'    (property "Reference" "U" (id 0) (at 0 {half_h + 2.54:.2f} 0)')
    lines.append('      (effects (font (size 1.27 1.27))))')
    lines.append(f'    (property "Value" "{name}" (id 1) (at 0 {-half_h - 2.54:.2f} 0)')
    lines.append('      (effects (font (size 1.27 1.27))))')
    lines.append(f'    (property "Footprint" "{footprint_ref}" (id 2) (at 0 0 0)')
    lines.append('      (effects (font (size 1.27 1.27)) hide))')
    lines.append(f'    (property "Datasheet" "" (id 3) (at 0 0 0)')
    lines.append('      (effects (font (size 1.27 1.27)) hide))')

    # --- Sottosimbolo grafico "_0_1" (rettangolo) ---
    lines.append(f'    (symbol "{name}_0_1"')
    lines.append(f'      (rectangle (start {-half_w:.2f} {half_h:.2f})')
    lines.append(f'        (end {half_w:.2f} {-half_h:.2f})')
    lines.append('        (stroke (width 0.254) (type default))')
    lines.append('        (fill (type background)))')
    lines.append('    )')

    # --- Sottosimbolo "_1_1" (pin) ---
    lines.append(f'    (symbol "{name}_1_1"')

    def emetti_pin(pin, x_pin, y, angle):
        num = pin["number"]
        pname = pin["name"]
        ptype = _PIN_TYPE_MAP.get(pin.get("type", "bidirectional"), "bidirectional")
        lines.append(f'      (pin {ptype} line (at {x_pin:.2f} {y:.2f} {angle}) (length {pin_len:.2f})')
        lines.append(f'        (name "{pname}" (effects (font (size 1.27 1.27))))')
        lines.append(f'        (number "{num}" (effects (font (size 1.27 1.27))))')
        lines.append('      )')

    # Pin lato sinistro: puntano a destra (angle 0)
    for i, pin in enumerate(left_pins):
        y = top_y - i * grid
        emetti_pin(pin, x_pin=-half_w - pin_len, y=y, angle=0)

    # Pin lato destro: puntano a sinistra (angle 180)
    for i, pin in enumerate(right_pins):
        y = top_y - i * grid
        emetti_pin(pin, x_pin=half_w + pin_len, y=y, angle=180)

    lines.append('    )')   # chiude _1_1
    lines.append('  )')     # chiude symbol
    lines.append(')')       # chiude kicad_symbol_lib

    return "\n".join(lines) + "\n"


def _genera_simbolo(board, output_dir, footprint_ref=""):
    name = board["name"]
    s_expr = _genera_simbolo_s_expr(board, footprint_ref=footprint_ref)
    output_path = os.path.join(output_dir, f"{name}.kicad_sym")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(s_expr)
    print(f"✅ Simbolo generato: {output_path}")
    if footprint_ref:
        print(f"   → Associato al footprint: {footprint_ref}")
    return output_path


# ============================================================
#  ORCHESTRATORE
# ============================================================

def genera_tutto(layout_path, genera_fp=True, genera_sym=True, library_nickname=None):
    """
    Genera footprint e/o simbolo dal layout.json.

    :param layout_path: percorso del layout.json
    :param genera_fp: se True, genera i .kicad_mod
    :param genera_sym: se True, genera il .kicad_sym
    :param library_nickname: nome della libreria KiCad (es. "ESP32_S3_ETH_DEVBOARD").
                             Se fornito, il simbolo punterà automaticamente
                             al primo footprint come "<library_nickname>:<footprint_name>".
    :return: dict con i percorsi dei file generati
    """
    board = _carica_layout(layout_path)
    output_dir = _prepara_output_dir(layout_path)

    risultati = {"footprints": [], "symbol": None}

    # Determina il nome del primo footprint da usare come riferimento nel simbolo
    footprints_cfg = board.get("footprints", [])
    if footprints_cfg:
        first_fp_name = footprints_cfg[0].get("name", board["name"])
    else:
        first_fp_name = board["name"]

    footprint_ref = ""
    if library_nickname:
        footprint_ref = f"{library_nickname}:{first_fp_name}"

    if genera_fp:
        risultati["footprints"] = _genera_footprint(board, output_dir)

    if genera_sym:
        risultati["symbol"] = _genera_simbolo(
            board, output_dir, footprint_ref=footprint_ref
        )

    return risultati


# Compatibilità con il vecchio nome (restituisce il primo footprint)
def genera_footprint(layout_path):
    risultato = genera_tutto(layout_path, genera_fp=True, genera_sym=False)
    footprints = risultato.get("footprints", [])
    return footprints[0] if footprints else None
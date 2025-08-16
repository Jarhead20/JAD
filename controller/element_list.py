# elements/parser.py
import json
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from controller.channels import channels

from elements.gauge import RoundGauge, LinearGauge
from elements.text import TextElement
from elements.gear import GearElement
from elements.image import ImageElement

def _qcolor(c):
    if isinstance(c, QColor): return c
    if isinstance(c, (tuple, list)): return QColor(*c)
    return QColor(c)

def _align(s):
    from PySide6.QtCore import Qt
    m = {
        "left": Qt.AlignLeft | Qt.AlignVCenter,
        "right": Qt.AlignRight | Qt.AlignVCenter,
        "top": Qt.AlignTop | Qt.AlignHCenter,
        "bottom": Qt.AlignBottom | Qt.AlignHCenter,
        "center": Qt.AlignCenter,
    }
    return m.get(str(s).lower(), Qt.AlignCenter)

class ElementList:
    def __init__(self):
        self._elements = []
        self._transform_guards = []  # keep references to lambdas so they don't get GC'd

    def get_elements(self):
        return self._elements

    def add_element(self, element):
        self._elements.append(element)

    def parse(self, path, parent=None):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1) Setup channel transforms (derived channels)
        self._setup_channel_transforms(data.get("channels", {}))

        # 2) Instantiate elements
        for item in data.get("elements", []):
            t = str(item.get("type", "text")).lower()
            x = int(item.get("x", 0)); y = int(item.get("y", 0))
            w = int(item.get("width", 200)); h = int(item.get("height", 100))
            centered = bool(item.get("centered", False))

            if t == "text":
                e = TextElement(
                    x, y, w, h, centered,
                    item.get("text", ""),
                    color=_qcolor(item.get("color", "white")),
                    bg_color=_qcolor(item.get("bg_color", "black")),
                    align=_align(item.get("align", "center")),
                    font_family=item.get("font_family", "DejaVu Sans"),
                    font_px=int(item.get("font_px", 24)),
                    bold=bool(item.get("bold", False)),
                    italic=bool(item.get("italic", False)),
                    wrap=bool(item.get("wrap", True)),
                    # channel bindings:
                    channel=item.get("channel"),
                    fmt=item.get("fmt", "{value}"),
                    parent=parent
                )

            elif t == "round_gauge":
                e = RoundGauge(
                    x=x, y=y, width=w, height=h,
                    centered=centered,
                    label=item.get("label", "Label"),
                    bar_color=_qcolor(item.get("bar_color", Qt.green)),
                    track_color=_qcolor(item.get("track_color", Qt.gray)),
                    bg_color=_qcolor(item.get("bg_color", Qt.black)),
                    text_color=_qcolor(item.get("text_color", Qt.white)),
                    redline_color=_qcolor(item.get("redline_color", Qt.red)),
                    font_size=int(item.get("font_size", 14)),
                    max_val=float(item.get("max_val", 9.0)),
                    redline=item.get("redline", None),
                    thickness=int(item.get("thickness", 24)),
                    start_angle=float(item.get("start_angle", 225)),
                    span_angle=float(item.get("span_angle", -270)),
                    minor_per_segment=int(item.get("minor_per_segment", 4)),
                    # channel bindings:
                    channel=item.get("channel"),
                    scale=float(item.get("scale", 1.0)),
                    offset=float(item.get("offset", 0.0)),
                    parent=parent
                )

            elif t == "linear_gauge":
                e = LinearGauge(
                    x=x, y=y, width=w, height=h,
                    centered=centered,
                    label=item.get("label", "Label"),
                    bar_color=_qcolor(item.get("bar_color", Qt.green)),
                    track_color=_qcolor(item.get("track_color", Qt.gray)),
                    bg_color=_qcolor(item.get("bg_color", Qt.black)),
                    text_color=_qcolor(item.get("text_color", Qt.white)),
                    redline_color=_qcolor(item.get("redline_color", Qt.red)),
                    font_size=int(item.get("font_size", 14)),
                    max_val=float(item.get("max_val", 100.0)),
                    redline=item.get("redline", None),
                    thickness=int(item.get("thickness", 24)),
                    horizontal=bool(item.get("horizontal", True)),
                    tick_step=float(item.get("tick_step", 10)),
                    minor_per_major=int(item.get("minor_per_major", 4)),
                    corner_radius=int(item.get("corner_radius", 8)),
                    # channel bindings:
                    channel=item.get("channel"),
                    scale=float(item.get("scale", 1.0)),
                    offset=float(item.get("offset", 0.0)),
                    parent=parent
                )

            elif t == "gear":
                # center handling like text/round/linear
                gx, gy = (x, y)  # GearElement uses center coords via TextElement
                e = GearElement(
                    gx, gy, w, h,
                    bool(item.get("centered", True)),
                    channel=item.get("channel", "gear"),
                    color=_qcolor(item.get("color", "white")),
                    bg_color=_qcolor(item.get("bg_color", "black")),
                    font_family=item.get("font_family", "DejaVu Sans"),
                    font_px=int(item.get("font_px", 72)),
                    bold=bool(item.get("bold", True)),
                    italic=bool(item.get("italic", False)),
                    align=_align(item.get("align", "center")),
                    wrap=bool(item.get("wrap", False)),
                    parent=parent
                )
                e.show()
                self._elements.append(e)
            elif t == "image":
                e = ImageElement(
                    x=x, y=y, width=w, height=h,
                    centered=centered,
                    path=item.get("path", ""),
                    mode=item.get("mode", "contain"),          # contain | cover | stretch
                    align=item.get("align", "center"),         # left/right/top/bottom/center...
                    opacity=float(item.get("opacity", 1.0)),
                    rotation=float(item.get("rotation", 0.0)),
                    bg_color=item.get("bg_color", "transparent"),
                    parent=parent
                )
                e.show()
                self._elements.append(e)
            else:
                print(f"[parser] Unknown element type: {t}")
                continue

            e.setParent(parent); e.show()
            self._elements.append(e)
        return data.get("page", {})

    # --- transforms: derive channels from other channels ---
    def _setup_channel_transforms(self, spec: dict):
        """
        spec = {
          "rpm_k":   {"source":"rpm", "scale":0.001, "offset":0, "clamp":[0,9], "ema":0.2},
          "fuel_pct":{"source":"fuel_l","ratio_to":"fuel_capacity_l","clamp":[0,1], "ema":0.2}
        }
        Recomputes target whenever source (or ratio_to) changes.
        """
        ema_prev = {}

        def recompute(target: str, cfg: dict):
            src = cfg.get("source", target)
            v = channels.get(src)
            if v is None:
                return
            try:
                v = float(v)
            except Exception:
                return

            # ratio
            ratio_key = cfg.get("ratio_to")
            if ratio_key:
                denom = channels.get(ratio_key)
                if denom not in (None, 0, 0.0):
                    v = v / float(denom)
                else:
                    return  # can't compute yet

            # affine
            v = float(cfg.get("offset", 0.0)) + v * float(cfg.get("scale", 1.0))

            # clamp
            clamp = cfg.get("clamp")
            if isinstance(clamp, (list, tuple)) and len(clamp) == 2:
                lo, hi = float(clamp[0]), float(clamp[1])
                v = max(lo, min(hi, v))

            # ema smoothing
            alpha = cfg.get("ema")
            if isinstance(alpha, (int, float)) and 0.0 < alpha < 1.0:
                prev = ema_prev.get(target)
                if prev is None:
                    ema_prev[target] = v
                else:
                    v = prev + alpha * (v - prev)
                    ema_prev[target] = v

            channels.set(target, v)

        # connect listeners
        for target, cfg in spec.items():
            src = cfg.get("source", target)
            ratio_key = cfg.get("ratio_to")

            def on_changed(ch_key, _val, target=target, cfg=cfg, src=src, ratio_key=ratio_key):
                if ch_key == src or (ratio_key and ch_key == ratio_key):
                    recompute(target, cfg)

            channels.changed.connect(on_changed)
            # keep a reference to avoid GC of the closure
            self._transform_guards.append(on_changed)

            # try an initial compute with whatever is in the store now
            recompute(target, cfg)

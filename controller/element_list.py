# elements/parser.py
import json
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from controller.channels import channels

from elements.gauge import RoundGauge, LinearGauge
from elements.text import TextElement
from elements.gear import GearElement
from elements.image import ImageElement
from elements.readout import Readout
from elements.geometry import GeometryElement
from elements.group import Group
from elements.gg import GGDiagram
from elements.image_gauge import ImageGauge

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

        self._elements = []  # reset for this page

        # 2) Build elements (top-level only; groups will own their children)
        for item in data.get("elements", []):
            w = self._parse_item(item, parent=parent)
            if w is not None:
                self._elements.append(w)

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
    def _parse_item(self, item: dict, parent=None):
        t = str(item.get("type", "text")).lower()
        x = int(item.get("x", 0)); y = int(item.get("y", 0))
        w = int(item.get("width", 200)); h = int(item.get("height", 100))
        centered = bool(item.get("centered", False))

        # ----- GROUP -----
        if t == "group":
            g = Group(x, y, w, h, centered=centered,
                    bg_color=_qcolor(item.get("bg_color", "transparent")),
                    parent=parent)
            g.setVisible(bool(item.get("visible", True)))
            g.set_visible_when(item.get("visible_when", None))
            # build children relative to the group
            for child in item.get("children", []):
                cw = self._parse_item(child, parent=g)
                if cw is not None:
                    g.add_child(cw)
            return g

        # ----- TEXT -----
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
                channel=item.get("channel"),
                fmt=item.get("fmt", "{value}"),
                parent=parent
            )

        # ----- ROUND GAUGE -----
        elif t == "round_gauge":
            e = RoundGauge(
                x=x, y=y, width=w, height=h, centered=centered,
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
                channel=item.get("channel"),
                scale=float(item.get("scale", 1.0)),
                offset=float(item.get("offset", 0.0)),
                parent=parent
            )

        # ----- LINEAR GAUGE -----
        elif t == "linear_gauge":
            e = LinearGauge(
                x=x, y=y, width=w, height=h, centered=centered,
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
                channel=item.get("channel"),
                scale=float(item.get("scale", 1.0)),
                offset=float(item.get("offset", 0.0)),
                padding=int(item.get("padding", 0)),
                track_align=item.get("track_align", "center"),
                parent=parent
            )

        # ----- GEAR -----
        elif t == "gear":
            e = GearElement(
                x, y, w, h, bool(item.get("centered", True)),
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

        # ----- IMAGE -----
        elif t == "image":
            e = ImageElement(
                x=x, y=y, width=w, height=h, centered=centered,
                path=item.get("path", ""),
                mode=item.get("mode", "contain"),
                align=item.get("align", "center"),
                opacity=float(item.get("opacity", 1.0)),
                rotation=float(item.get("rotation", 0.0)),
                bg_color=item.get("bg_color", "transparent"),
                parent=parent
            )

        # ----- READOUT -----
        elif t == "readout":
            e = Readout(
                x=x, y=y, width=w, height=h, centered=centered,
                label=item.get("label", "LABEL"),
                channel=item.get("channel"),
                fmt=item.get("fmt", "{value}"),
                units=item.get("units", ""),
                scale=float(item.get("scale", 1.0)),
                offset=float(item.get("offset", 0.0)),
                label_color=item.get("label_color", "#9aa0a6"),
                value_color=item.get("value_color", "#ffffff"),
                bg_color=item.get("bg_color", "transparent"),
                label_font_family=item.get("label_font_family", "DejaVu Sans"),
                value_font_family=item.get("value_font_family", "DejaVu Sans"),
                label_font_px=int(item.get("label_font_px", 18)),
                value_font_px=int(item.get("value_font_px", 42)),
                label_bold=bool(item.get("label_bold", True)),
                value_bold=bool(item.get("value_bold", True)),
                label_italic=bool(item.get("label_italic", False)),
                value_italic=bool(item.get("value_italic", False)),
                align=item.get("align", "center"),
                padding=int(item.get("padding", 8)),
                spacing=int(item.get("spacing", 4)),
                label_ratio=float(item.get("label_ratio", 0.40)),
                parent=parent
            )

        # ----- GEOMETRY -----
        elif t == "geometry":
            e = GeometryElement(
                x=x, y=y, width=w, height=h, centered=centered,
                shape=item.get("shape", "rect"),
                fill_color=item.get("fill_color", "transparent"),
                stroke_color=item.get("stroke_color", "white"),
                stroke_width=float(item.get("stroke_width", 2.0)),
                corner_radius=float(item.get("corner_radius", 12.0)),
                start_angle=float(item.get("start_angle", 0.0)),
                span_angle=float(item.get("span_angle", 360.0)),
                ring_width=item.get("ring_width", None),
                line_dir=item.get("line_dir", "h"),
                rotation=float(item.get("rotation", 0.0)),
                opacity=float(item.get("opacity", 1.0)),
                channel=item.get("channel"),
                scale=float(item.get("scale", 1.0)),
                offset=float(item.get("offset", 0.0)),
                max_val=float(item.get("max_val", 1.0)),
                bg_color=item.get("bg_color", "transparent"),
                parent=parent
            )

        elif t in ("gg", "gg_diagram"):
            e = GGDiagram(
                x, y, w, h, centered,
                bg_color=_qcolor(item.get("bg_color", "transparent")),
                lat_ch=item.get("lat_ch", "acc_lat_g"),
                long_ch=item.get("long_ch", "acc_long_g"),
                radius_g=float(item.get("radius_g", 2.5)),
                padding=int(item.get("padding", 10)),
                rings=int(item.get("rings", 4)),
                show_square=bool(item.get("show_square", False)),
                show_labels=bool(item.get("show_labels", True)),
                grid_color=item.get("grid_color", "#2b2f36"),
                axis_color=item.get("axis_color", "#8a8f98"),
                trail_color=item.get("trail_color", "#2fc1ff"),
                point_color=item.get("point_color", "#ffffff"),
                point_radius_px=int(item.get("point_radius_px", 5)),
                trail_len=int(item.get("trail_len", 240)),
                ema=item.get("ema", 0.2),
                invert_lat=bool(item.get("invert_lat", False)),
                invert_long=bool(item.get("invert_long", False)),
                reset_channel=item.get("reset_channel"),
                parent=parent
            )

        elif t in ("image_gauge", "tinted_image"):
            e = ImageGauge(
                x, y, w, h, centered,
                path=item.get("path", ""),
                channel=item.get("channel"),
                min_color=item.get("min_color", "#18c964"),
                mid_color=item.get("mid_color"),            # optional
                max_color=item.get("max_color", "#ff3b30"),
                invert=bool(item.get("invert", False)),
                mode=item.get("mode", "contain"),
                align=item.get("align", "center"),
                opacity=float(item.get("opacity", 1.0)),
                rotation=float(item.get("rotation", 0.0)),
                scale=float(item.get("scale", 1.0)),
                offset=float(item.get("offset", 0.0)),
                ema=item.get("ema", None),
                bg_color=item.get("bg_color", "transparent"),
                black_point=float(item.get("black_point", 0.15)),
                white_point=float(item.get("white_point", 0.95)),
                gamma=float(item.get("gamma", 1.0)),
                parent=parent
            )

        else:
            print(f"[parser] Unknown element type: {t}")
            return None

        # Common post-creation for non-group widgets
        e.setVisible(bool(item.get("visible", True)))
        e.set_visible_when(item.get("visible_when", None))
        e.show()
        return e


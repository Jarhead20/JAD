from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget
from controller.channels import channels

class Element(QWidget):
    """
    Minimal positioned widget with a background color and helper methods.
    Requires x, y, width, height, bg_color.
    """
    def __init__(self, x: int, y: int, width: int, height: int, centered=False,
                 bg_color=Qt.black, parent: QWidget | None = None):
        super().__init__(parent)
        self._bg_color = QColor(str(bg_color)) if not isinstance(bg_color, QColor) else bg_color
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, self._bg_color.alpha() > 0)
        self._centered = centered
        if(self._centered):
            self.setGeometry(int(x-(width/2)), int(y-(height/2)), int(width), int(height))
        else:
            self.setGeometry(int(x), int(y), int(width), int(height))


        self._rule = None            # normalized rule to evaluate
        self._reset_rule = None
        self._latch_enabled = False
        self._latched = False
        self._last_visible = None

    # ----- Helpers -----
    def set_bg(self, color):
        self._bg_color = color
        self.update()

    def bg(self):
        return self._bg_color

    def set_pos(self, x: int, y: int):
        self.setGeometry(int(x), int(y), self.width(), self.height())

    def set_size(self, w: int, h: int):
        self.setGeometry(self.x(), self.y(), int(w), int(h))

    def set_geometry(self, x: int, y: int, w: int, h: int):
        self.setGeometry(int(x), int(y), int(w), int(h))

    def add(self, child: QWidget, *, x: int | None = None, y: int | None = None,
            w: int | None = None, h: int | None = None):
        """Adopt child and optionally place it."""
        child.setParent(self)
        if None not in (x, y, w, h):
            child.setGeometry(int(x), int(y), int(w), int(h))
        child.show()
        return child

    def center_xy(self) -> tuple[int, int]:
        c = self.rect().center()
        return c.x(), c.y()

    def refresh(self):
        self.update()

    def update_val(self, store):
        pass

    def set_visible_when(self, spec: dict | None):
        """Accepts either a plain rule or a wrapper:
           - { ...rule... }
           - { "latch": true/false, "when": { ...rule... }, "reset_when": { ...rule... }? }
        """
        # defaults
        self._rule = None
        self._reset_rule = None
        self._latch_enabled = False
        self._latched = False
        self._last_visible = None

        if not spec:
            return

        if isinstance(spec, dict) and ("when" in spec or "latch" in spec or "reset_when" in spec):
            self._latch_enabled = bool(spec.get("latch", False))
            # normalize: if "when" is missing, treat remaining keys (minus latch/reset_when) as the rule
            rule = spec.get("when")
            if rule is None:
                rule = {k: v for k, v in spec.items() if k not in ("latch", "reset_when", "when")}
            self._rule = rule
            self._reset_rule = spec.get("reset_when")
        else:
            # plain rule
            self._rule = spec

    def evaluate_visibility(self, store):
        if self._rule is None and not self._latch_enabled:
            vis = True
        elif self._latch_enabled:
            # handle reset first
            if self._reset_rule and _eval_condition(self._reset_rule, store):
                self._latched = False
            # latch when rule becomes true
            if self._rule and _eval_condition(self._rule, store):
                self._latched = True
            vis = self._latched
        else:
            vis = _eval_condition(self._rule, store)

        if vis != self._last_visible:
            self._last_visible = vis
            self.setVisible(vis)

    def paintEvent(self, _):
        p = QPainter(self)
        if self._bg_color.isValid() and self._bg_color.alpha() > 0:
            p.fillRect(self.rect(), self._bg_color)
        p.end()

def _eval_condition(spec: dict, store) -> bool:
    """
    spec examples:
      {"ch":"fuel_pct", "op":"<", "value":0.1}
      {"ch":"gear", "in":[0,1]}            # membership
      {"between":[0.2,0.8], "ch":"rpm_norm"}
      {"all":[ {...}, {"not": {...}} ]}
      {"any":[ {...}, {...} ]}
      {"exists":"rpm"}
      # transforms:
      {"ch":"rpm", "ratio_to":"max_rpm", "op":">", "value":0.9, "scale":1.0, "offset":0.0}
      # shorthand ops:
      {"ch":"rpm", ">=": 5000}
    """
    def get(name):
        return store.get(name, None)

    def eval_rule(rule) -> bool:
        # groups
        if "all" in rule: return all(eval_rule(r) for r in rule["all"])
        if "any" in rule: return any(eval_rule(r) for r in rule["any"])
        if "not" in rule: return not eval_rule(rule["not"])
        if "exists" in rule: return get(rule["exists"]) is not None

        # base rule
        ch = rule.get("ch")
        if ch is None: return False
        v = get(ch)
        if v is None: return False

        # transform
        try:
            v = float(v)
        except Exception:
            pass

        ratio_to = rule.get("ratio_to")
        if ratio_to:
            denom = get(ratio_to)
            if not denom: return False
            try:
                v = float(v) / float(denom)
            except Exception:
                return False

        if "scale" in rule or "offset" in rule:
            try:
                v = float(rule.get("offset", 0.0)) + float(v) * float(rule.get("scale", 1.0))
            except Exception:
                return False

        # between
        if "between" in rule:
            lo, hi = rule["between"]
            try:
                return float(lo) <= float(v) <= float(hi)
            except Exception:
                return False

        # membership
        if "in" in rule:
            return v in rule["in"]

        # operators
        # allow either {"op":">", "value":10} or shorthand {">":10}
        op = rule.get("op")
        cmp_val = rule.get("value", None)
        if op is None:
            for k in ("<", "<=", ">", ">=", "==", "!="):
                if k in rule:
                    op, cmp_val = k, rule[k]
                    break
        if op is None:
            return False

        # numeric compare if both numeric, else string compare
        def as_num(x):
            try: return float(x)
            except Exception: return None

        a_num, b_num = as_num(v), as_num(cmp_val)
        if a_num is not None and b_num is not None:
            a, b = a_num, b_num
        else:
            a, b = str(v), str(cmp_val)

        return {
            "<":  lambda A,B: A <  B,
            "<=": lambda A,B: A <= B,
            ">":  lambda A,B: A >  B,
            ">=": lambda A,B: A >= B,
            "==": lambda A,B: A == B,
            "!=": lambda A,B: A != B,
        }[op](a, b)

    return bool(eval_rule(spec))

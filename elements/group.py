# elements/group.py
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from elements.element import Element

class Group(Element):
    """
    A container element.
    - Children use coordinates relative to this group's rect.
    - Visibility on the group hides/shows all children.
    - Optional 'translate' lets you offset the group via channels.
    """
    def __init__(self, x, y, width, height, centered=False,
                 bg_color=Qt.transparent, parent: QWidget | None = None):
        super().__init__(x, y, width, height, centered, bg_color, parent)
        self._children: list[QWidget] = []
        self._translate_spec = None
        # remember original anchor for channel-driven translation
        self._x0, self._y0 = self.x(), self.y()

    # --- children management ---
    def add_child(self, w: QWidget):
        w.setParent(self)
        self._children.append(w)
        w.show()

    def children_elements(self):
        return list(self._children)

    # --- optional channel-driven translate ---
    def set_translate(self, spec: dict | None):
        """spec:
           { "dx": 0, "dy": 0 }  // static
           or
           { "dx_ch":"offx", "dy_ch":"offy", "scale_x":1.0, "scale_y":1.0,
             "offset_x":0.0, "offset_y":0.0 }
        """
        self._translate_spec = spec or None
        self._x0, self._y0 = self.x(), self.y()

    def update_from_channels(self, store):
        # apply group translation if configured
        s = self._translate_spec
        if not s:
            return
        dx = float(s.get("dx", 0.0))
        dy = float(s.get("dy", 0.0))
        if "dx_ch" in s:
            vx = store.get(s["dx_ch"], 0.0)
            try: vx = float(vx)
            except: vx = 0.0
            dx = s.get("offset_x", 0.0) + s.get("scale_x", 1.0) * vx
        if "dy_ch" in s:
            vy = store.get(s["dy_ch"], 0.0)
            try: vy = float(vy)
            except: vy = 0.0
            dy = s.get("offset_y", 0.0) + s.get("scale_y", 1.0) * vy
        self.move(int(self._x0 + dx), int(self._y0 + dy))

    # tick children recursively (Page will call propagate_tick on top-levels)
    def propagate_tick(self, store):
        for c in self._children:
            upd = getattr(c, "update_val", None)
            if upd: upd(store)
            vis = getattr(c, "evaluate_visibility", None)
            if vis: vis(store)
            prop = getattr(c, "propagate_tick", None)
            if prop: prop(store)

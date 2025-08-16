from controller.page import Page

class PageCycler:
    def __init__(self, root, paths):
        self.root = root
        self.paths = list(paths)
        self.idx = 0
        self.current = None
        if self.paths:
            self._show_index(0)

    def _show_index(self, i: int):
        if not self.paths:
            return
        i %= len(self.paths)
        path = self.paths[i]

        # Create Page, then parent it
        w = Page(path)                  # <-- no parent kwarg
        w.setParent(self.root)          # <-- parent after construction
        w.setGeometry(self.root.rect())
        w.show()

        if self.current:
            self.current.deleteLater()
        self.current = w
        self.idx = i

    def next_page(self):
        self._show_index(self.idx + 1)

    def current_path(self):
        return self.paths[self.idx] if self.paths else None

    def reload_current(self):
        if self.paths:
            self._show_index(self.idx)

    def set_pages(self, new_paths):
        self.paths = list(new_paths)
        if not self.paths:
            if self.current:
                self.current.deleteLater()
                self.current = None
            self.idx = 0
            return
        cur = self.current_path()
        self.idx = self.paths.index(cur) if cur in self.paths else 0
        self._show_index(self.idx)
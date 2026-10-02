import math


class LivingSpatialIndex:
    """Exact grid index for mutable living-agent positions.

    The engine owns synchronization. Membership rebuilds preserve the original
    population order so equal-distance ties match the historical linear scan.
    """

    def __init__(self, cell_size=100.0):
        if cell_size <= 0:
            raise ValueError('cell_size must be positive')
        self.cell_size = float(cell_size)
        self.cells = {}
        self.item_cells = {}
        self.ranks = {}
        self.items = {}
        self.rebuilds = 0
        self.updates = 0
        self.queries = 0
        self.candidates = 0

    def _cell(self, item):
        return (
            math.floor(float(item['x']) / self.cell_size),
            math.floor(float(item['y']) / self.cell_size),
        )

    def rebuild(self, items):
        self.cells = {}
        self.item_cells = {}
        self.ranks = {}
        self.items = {}
        for rank, item in enumerate(items):
            item_id = item['id']
            cell = self._cell(item)
            self.cells.setdefault(cell, []).append(item)
            self.item_cells[item_id] = cell
            self.ranks[item_id] = rank
            self.items[item_id] = item
        self.rebuilds += 1

    def update(self, item):
        item_id = item['id']
        old_cell = self.item_cells.get(item_id)
        if old_cell is None:
            return False
        new_cell = self._cell(item)
        if new_cell == old_cell:
            return False
        bucket = self.cells.get(old_cell)
        if bucket is not None:
            self.cells[old_cell] = [candidate for candidate in bucket if candidate['id'] != item_id]
            if not self.cells[old_cell]:
                self.cells.pop(old_cell, None)
        self.cells.setdefault(new_cell, []).append(item)
        self.item_cells[item_id] = new_cell
        self.updates += 1
        return True

    def nearest(self, origin, max_distance, predicate=None):
        if max_distance <= 0:
            return None
        self.queries += 1
        ox = float(origin['x'])
        oy = float(origin['y'])
        minimum_x = math.floor((ox - max_distance) / self.cell_size)
        maximum_x = math.floor((ox + max_distance) / self.cell_size)
        minimum_y = math.floor((oy - max_distance) / self.cell_size)
        maximum_y = math.floor((oy + max_distance) / self.cell_size)
        best = None
        best_d2 = float(max_distance) * float(max_distance)
        best_rank = math.inf

        for x in range(minimum_x, maximum_x + 1):
            for y in range(minimum_y, maximum_y + 1):
                for item in self.cells.get((x, y), ()):
                    self.candidates += 1
                    if predicate and not predicate(item):
                        continue
                    dx = ox - float(item['x'])
                    dy = oy - float(item['y'])
                    d2 = dx * dx + dy * dy
                    rank = self.ranks[item['id']]
                    if d2 < best_d2 or (best is not None and d2 == best_d2 and rank < best_rank):
                        best = item
                        best_d2 = d2
                        best_rank = rank
        return best

    def status(self):
        average = round(self.candidates / self.queries, 2) if self.queries else 0.0
        return {
            'cellSize': self.cell_size,
            'cells': len(self.cells),
            'size': len(self.item_cells),
            'rebuilds': self.rebuilds,
            'updates': self.updates,
            'queries': self.queries,
            'candidates': self.candidates,
            'averageCandidates': average,
        }


class SpatialCollectionCache:
    """Signature-aware immutable views backed by exact spatial indexes."""

    def __init__(self, cell_size=100.0):
        self.cell_size = float(cell_size)
        self.signature = None
        self.views = {}
        self.indexes = {}
        self.rebuilds = 0

    def refresh(self, signature, groups):
        if signature == self.signature:
            return False
        views = {}
        indexes = {}
        for name, items in groups.items():
            view = tuple(items)
            index = LivingSpatialIndex(cell_size=self.cell_size)
            index.rebuild(view)
            views[name] = view
            indexes[name] = index
        self.signature = signature
        self.views = views
        self.indexes = indexes
        self.rebuilds += 1
        return True

    def view(self, name):
        return self.views.get(name, ())

    def owns(self, name, items):
        return items is self.views.get(name)

    def nearest(self, name, origin, max_distance, predicate=None):
        index = self.indexes.get(name)
        if index is None:
            return None
        return index.nearest(origin, max_distance, predicate)

    def status(self):
        return {
            'rebuilds': self.rebuilds,
            'groups': {
                name: {
                    'size': len(self.views.get(name, ())),
                    **index.status(),
                }
                for name, index in self.indexes.items()
            },
        }

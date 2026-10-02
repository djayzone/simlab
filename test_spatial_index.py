import random
import unittest

from spatial_index import LivingSpatialIndex, SpatialCollectionCache


def linear_nearest(origin, items, max_distance, predicate=None):
    best = None
    best_d2 = max_distance * max_distance
    for item in items:
        if predicate and not predicate(item):
            continue
        dx = origin['x'] - item['x']
        dy = origin['y'] - item['y']
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best = item
            best_d2 = d2
    return best


class LivingSpatialIndexTests(unittest.TestCase):
    def test_matches_linear_scan_for_random_queries_and_predicates(self):
        rng = random.Random(42)
        items = [
            {
                'id': index,
                'x': rng.uniform(0, 1200),
                'y': rng.uniform(0, 760),
                'age': rng.uniform(0, 80),
            }
            for index in range(300)
        ]
        index = LivingSpatialIndex(cell_size=100)
        index.rebuild(items)

        predicates = (
            None,
            lambda item: item['age'] >= 18,
            lambda item: item['id'] % 3 == 0,
        )
        for _ in range(120):
            origin = {'x': rng.uniform(0, 1200), 'y': rng.uniform(0, 760)}
            distance = rng.choice((28, 80, 90, 95, 115, 220))
            for predicate in predicates:
                expected = linear_nearest(origin, items, distance, predicate)
                actual = index.nearest(origin, distance, predicate)
                self.assertIs(actual, expected)

    def test_update_tracks_cell_changes(self):
        items = [
            {'id': 1, 'x': 10.0, 'y': 10.0},
            {'id': 2, 'x': 250.0, 'y': 10.0},
        ]
        index = LivingSpatialIndex(cell_size=100)
        index.rebuild(items)
        origin = {'x': 220.0, 'y': 10.0}
        self.assertIs(index.nearest(origin, 80), items[1])

        items[0]['x'] = 205.0
        self.assertTrue(index.update(items[0]))
        self.assertIs(index.nearest(origin, 80), items[0])

    def test_equal_distance_keeps_original_population_order(self):
        first = {'id': 10, 'x': 40.0, 'y': 50.0}
        second = {'id': 20, 'x': 60.0, 'y': 50.0}
        items = [first, second]
        index = LivingSpatialIndex(cell_size=20)
        index.rebuild(items)
        self.assertIs(index.nearest({'x': 50.0, 'y': 50.0}, 20), first)

    def test_outside_radius_is_not_returned(self):
        item = {'id': 1, 'x': 100.0, 'y': 0.0}
        index = LivingSpatialIndex(cell_size=50)
        index.rebuild([item])
        self.assertIsNone(index.nearest({'x': 0.0, 'y': 0.0}, 100))


class SpatialCollectionCacheTests(unittest.TestCase):
    def test_refresh_reuses_same_views_for_same_signature(self):
        food = [{'id': 1, 'x': 10.0, 'y': 10.0}]
        water = [{'id': 2, 'x': 90.0, 'y': 10.0}]
        cache = SpatialCollectionCache(cell_size=100)
        self.assertTrue(cache.refresh((1, 2, 2), {'food': food, 'water': water}))
        food_view = cache.view('food')
        self.assertFalse(cache.refresh((1, 2, 2), {'food': (), 'water': ()}))
        self.assertIs(food_view, cache.view('food'))

    def test_changed_signature_rebuilds_membership(self):
        first = {'id': 1, 'x': 10.0, 'y': 10.0}
        second = {'id': 2, 'x': 20.0, 'y': 10.0}
        cache = SpatialCollectionCache(cell_size=100)
        cache.refresh((1, 1, 1), {'food': [first]})
        self.assertIs(cache.nearest('food', {'x': 0.0, 'y': 0.0}, 30), first)
        cache.refresh((1, 1, 2), {'food': [second]})
        self.assertIs(cache.nearest('food', {'x': 0.0, 'y': 0.0}, 30), second)


if __name__ == '__main__':
    unittest.main()

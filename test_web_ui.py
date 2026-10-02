from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class WebUiStructureTests(unittest.TestCase):
    def setUp(self):
        self.index = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.styles = (ROOT / 'styles.css').read_text(encoding='utf-8')
        self.mobile = (ROOT / 'mobile_ux.css').read_text(encoding='utf-8')

    def test_runtime_hooks_are_preserved(self):
        required_ids = (
            'world', 'inspector', 'knowledge', 'events', 'toggle', 'reset',
            'inject', 'artifactType', 'artifactCount', 'persistence-status',
            'stat-pop', 'stat-year', 'stat-birth', 'stat-death', 'stat-age',
            'stat-food', 'speed-label',
        )
        for element_id in required_ids:
            self.assertIn(f'id="{element_id}"', self.index)

    def test_game_shell_replaces_scroll_dashboard(self):
        for token in (
            'game-hud', 'game-shell', 'game-dock', 'observer-panel',
            'lab-panel', 'settings-panel', 'journal-panel', 'event-ticker',
            'selection-hud',
        ):
            self.assertIn(token, self.index)
        self.assertIn('html,body{margin:0;width:100%;height:100%;overflow:hidden', self.styles)
        self.assertIn('position:absolute;z-index:35', self.styles)

    def test_game_modes_have_keyboard_contracts(self):
        for shortcut in ('data-shortcut="1"', 'data-shortcut="2"', 'data-shortcut="3"', 'data-shortcut="4"'):
            self.assertIn(shortcut, self.index)
        self.assertIn('title="Pause / reprendre (Espace)"', self.index)
        self.assertIn('title="Plein écran (F)"', self.index)
        app = (ROOT / 'app.js').read_text(encoding='utf-8')
        self.assertIn("event.key==='Escape'", app)
        self.assertIn("data-shortcut", self.index)
        self.assertIn("requestFullscreen", app)
        self.assertIn("openPanel('observer-panel')", app)

    def test_mobile_uses_game_bottom_dock_and_sheets(self):
        self.assertIn('.game-dock{', self.mobile)
        self.assertIn('.game-panel{', self.mobile)
        self.assertIn('bottom:calc(73px + var(--safe-bottom))', self.mobile)
        self.assertNotIn('mobile-nav', (ROOT / 'mobile_ux.js').read_text(encoding='utf-8'))


    def test_dynamic_mechanics_are_visible_in_game_ui(self):
        app = (ROOT / 'app.js').read_text(encoding='utf-8')
        hot = (ROOT / 'hot_mechanics_engine.py').read_text(encoding='utf-8')
        self.assertIn("artifactCatalog", hot)
        self.assertIn("Object.keys(world.artifactCatalog||{})", app)
        self.assertIn("function artifactMeta(key)", app)
        self.assertIn("artifactMeta(artifact.type).glyph", app)
        self.assertIn("artifactMeta(k).label", app)

    def test_communities_and_diplomacy_are_visible_in_game_ui(self):
        app = (ROOT / 'app.js').read_text(encoding='utf-8')
        social = (ROOT / 'social_engine.py').read_text(encoding='utf-8')
        self.assertIn("communityRelations", social)
        self.assertIn("function communityColor(id,alpha=1)", app)
        self.assertIn("function diplomacyLabel(state)", app)
        self.assertIn("world.communityRelations||[]", app)
        self.assertIn("agent.communityId", app)
        self.assertIn("Communauté & diplomatie", app)
        self.assertIn("a.community?.relations", app)

    def test_accessibility_and_motion_contracts(self):
        self.assertIn('aria-live="polite"', self.index)
        self.assertIn('aria-label="Modes de jeu"', self.index)
        self.assertIn('@media(prefers-reduced-motion:reduce)', self.styles)
        self.assertIn('@media(prefers-reduced-motion:reduce)', self.mobile)


if __name__ == '__main__':
    unittest.main()

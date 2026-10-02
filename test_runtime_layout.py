import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
RUNTIME_MODULES = (
    'engine_bootstrap.py',
    'agent_compat.py',
    'http_server.py',
    'runtime_api.py',
    'simulation_runtime.py',
    'spatial_index.py',
)


class RuntimeLayoutTests(unittest.TestCase):
    def test_runtime_modules_are_valid_python(self):
        for filename in RUNTIME_MODULES:
            source = (ROOT / filename).read_text(encoding='utf-8')
            ast.parse(source, filename=filename)

    def test_engine_configmap_contains_runtime_contract(self):
        manifest = (ROOT / 'kustomization.yaml').read_text(encoding='utf-8')
        for filename in RUNTIME_MODULES:
            self.assertIn(f'- {filename}', manifest)
        self.assertNotIn('- engine_server.py', manifest)

    def test_http_transport_does_not_import_engine_internals(self):
        source = (ROOT / 'http_server.py').read_text(encoding='utf-8')
        tree = ast.parse(source, filename='http_server.py')
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertIn('simulation_runtime', imports)
        self.assertNotIn('engine', imports)
        self.assertNotIn('hot_mechanics_engine', imports)


if __name__ == '__main__':
    unittest.main()

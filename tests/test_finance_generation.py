import logging
from types import SimpleNamespace

import main as push_main
from sources.finance.source import FinanceSource


def test_generate_only_forwards_force_to_source(monkeypatch):
    captured = {}

    class FakeSource:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeEngine:
        def register_source(self, _name, source):
            self.source = source

        def run_source_only(self, _name):
            return 'output/finance/latest.html'

    monkeypatch.setattr(push_main, 'get_engine', lambda *_args, **_kwargs: FakeEngine())
    monkeypatch.setitem(push_main.MODULES, 'finance_test', {'class': FakeSource})

    push_main.gen_modules(['finance_test'], force=True)

    assert captured['force'] is True


def test_finance_source_forwards_force_to_each_indicator():
    calls = []

    class FakeIndicator:
        name = 'cpi'

        def run(self, force=False):
            calls.append(force)
            return {
                'url': 'https://assets.example.test/finance/cpi/latest.png',
                'date': '2026-06-01',
                'name': self.name,
                'value': '1.0',
            }

    source = object.__new__(FinanceSource)
    source.force = True
    source.manager = SimpleNamespace(archive=None)
    source.indicators = [FakeIndicator()]
    source.logger = logging.getLogger('test.finance.generation')
    source.render_template = lambda _name, _data: '<html></html>'

    source.run()

    assert calls == [True]

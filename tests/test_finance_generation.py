import logging
from types import SimpleNamespace

import pandas as pd

import main as push_main
from sources.finance.plot import Plotter
from sources.finance.source import BLOCKED_INDICATOR_CLASSES, FinanceSource


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


def test_finance_source_never_registers_blocked_indicators(monkeypatch):
    monkeypatch.setenv('FINANCE_ENABLE_EXPERIMENTAL', '1')
    monkeypatch.setattr('sources.finance.source.DataManager', lambda: SimpleNamespace(archive=None, df_cache={}))
    monkeypatch.setattr('sources.finance.source.Plotter', object)

    source = FinanceSource()

    assert not any(type(indicator) in BLOCKED_INDICATOR_CLASSES for indicator in source.indicators)


def test_mobile_macro_canvas_is_taller_and_equal_split():
    plotter = Plotter()
    fig, axes = plotter.create_ratio_axes([3, 1])
    try:
        assert tuple(fig.get_size_inches()) == (12.0, 15.0)
        assert abs(axes[0].get_position().height - axes[1].get_position().height) < 0.01
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


def test_diverging_gradient_closes_both_sides_of_zero():
    plotter = Plotter()
    fig, ax = plotter.create_single_ax()
    dates = pd.date_range('2026-01-01', periods=5, freq='ME')
    try:
        images = plotter.fill_diverging_gradient(ax, dates, pd.Series([2, 1, -1, -2, 1]))
        assert len(images) >= 2
        assert all(image.get_zorder() == 1 for image in images)
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)

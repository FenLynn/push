from core import ContentType, Message
import main as push_main


class FakeSource:
    def __init__(self, **kwargs):
        pass

    def run(self):
        return Message(title='test', content='test', type=ContentType.TEXT)


class FakeEngine:
    def register_source(self, name, source):
        pass

    def run_with_message(self, message, source_name, channel_names=None):
        return False


class FakeScheduler:
    def __init__(self):
        self.failures = []

    def plan_day(self):
        pass

    def should_run_today(self, module):
        return True

    def record_start(self, module):
        pass

    def record_failure(self, module, detail):
        self.failures.append((module, detail))


def test_pushplus_rejection_is_a_failed_run(monkeypatch):
    scheduler = FakeScheduler()
    monkeypatch.setitem(push_main.MODULES, 'delivery_test', {'class': FakeSource})
    monkeypatch.setattr(push_main, 'get_engine', lambda *args, **kwargs: FakeEngine())
    monkeypatch.setattr(push_main, 'get_scheduler', lambda: scheduler)

    assert push_main.run_modules(['delivery_test'], force=True) is False
    assert scheduler.failures
    assert '0/1' in scheduler.failures[0][1]

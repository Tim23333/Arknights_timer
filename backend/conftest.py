"""Release test-owned Qt windows while Python callbacks are still alive.

The desktop tests share QApplication, but closing a window only hides it.
Without explicit deferred deletion, native windows and timer callbacks can
survive their test and run during interpreter teardown on Windows.
"""
import pytest


@pytest.fixture(autouse=True)
def release_test_windows():
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    previous = set(app.topLevelWidgets()) if app is not None else set()
    yield
    app = QApplication.instance()
    if app is None:
        return
    app.processEvents()
    for window in set(app.topLevelWidgets()) - previous:
        window.close()
        window.deleteLater()
    # Outside app.exec(), processEvents() doesn't deliver DeferredDelete.
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

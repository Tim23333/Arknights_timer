"""Explicit checkpoint helpers for hosts that keep callbacks outside JSON."""


def checkpoint(session):
    return session.checkpoint()


def restore(session, data):
    session.restore(data)
    return session

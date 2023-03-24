import sys


def warn(*args, **kwargs):
    print("WARN:", *args, file=sys.stderr, **kwargs)


def err(*args, **kwargs):
    print("ERR:", *args, file=sys.stderr, **kwargs)


def info(*args, **kwargs):
    print("INFO:", *args, file=sys.stderr, **kwargs)

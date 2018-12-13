from genpersist import Node, operation
import pytest

class C(Node):
    def __init__(self):
        self.a = 1
        self.b = None

def test__basic_confluence():
    with operation():
        c = C()

    assert c.a == 1
    assert c.b is None

def test__independent_confluence():
    with operation():
        c = C()

    with operation():
        d = C()

    assert c.a == 1
    assert c.b is None
    assert d.a == 1
    assert d.b is None

@pytest.fixture
def c():
    with operation():
        return C()

@pytest.fixture
def d():
    with operation():
        return C()

def test__basic_reference(c, d):
    c0 = c
    with operation(c) as c:
        c.b = d

    assert c0.a == 1
    assert c0.b is None
    assert c.a == 1
    assert c.b.a == 1
    assert c.b.b == None
    assert d.a == 1
    assert d.b == None

def test__reference_mutate_indirect(c, d):
    c0 = c
    with operation(c) as c:
        c.b = d
        c.b.a = 2

    assert c.a == 1
    assert c.b.a == 2
    assert c.b.b == None
    assert d.a == 1
    assert d.b is None
    assert c0.a == 1
    assert c0.b is None

def test__self_reference(c):
    c0 = c

    with operation(c) as c:
        c.b = c0
        c.a = 6

    assert c.a == 6
    assert c.b.a == 1
    assert c.b.b is None

    assert c0.a == 1
    assert c0.b is None

def test__reference_nested_mutate_operation(c, d):
    with operation(c) as c:
        c.b = d

    with operation(d) as d:
        d.b = c
        d.b.b.a = 5

    assert c.a == 1
    assert c.b.a == 1
    assert c.b.b == None
    assert d.a == 1
    assert d.b.b.a == 5
    assert d.b.b.b is None


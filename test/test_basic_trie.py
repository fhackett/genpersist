from confluence import Trie, Node, operation, refdup
import pytest

def test__trie_basic():
    t = Trie()

    assert t == Trie()

    t['abc'] = 5

    assert t.longest_prefix_item('abc') == ('abc', 5)
    assert t.longest_prefix_item('abcd') == ('abc', 5)
    assert t.longest_prefix_item('ab') == (None, None)
    assert t.longest_prefix_item('abcde') == ('abc', 5)

    t['ab'] = 4

    assert t.longest_prefix_item('abc') == ('abc', 5)
    assert t.longest_prefix_item('abcd') == ('abc', 5)
    assert t.longest_prefix_item('ab') == ('ab', 4)
    assert t.longest_prefix_item('a') == (None, None)
    assert t.longest_prefix_item('') == (None, None)

    t[''] = 3

    assert t.longest_prefix_item('abc') == ('abc', 5)
    assert t.longest_prefix_item('abcd') == ('abc', 5)
    assert t.longest_prefix_item('ab') == ('ab', 4)
    assert t.longest_prefix_item('a') == ('', 3)
    assert t.longest_prefix_item('') == ('', 3)

class C(Node):
    def __init__(self):
        self.a = 1
        self.b = None

def test__basic_confluence():
    c = C()

    assert c.a == 1
    assert c.b is None

def test__independent_confluence():
    c = C()
    d = C()

    assert d.a == 1
    assert d.b is None

@pytest.fixture
def c():
    return C()

@pytest.fixture
def d():
    return C()

def test__basic_reference(c, d):
    c.b = d

    assert c.a == 1
    assert c.b.a == 1
    assert c.b.b == None

def test__reference_mutate_no_operation(c, d):
    c.b = d

    c.b.a = 2

    assert c.a == 1
    assert c.b.a == 1
    assert c.b.b == None
    assert d.a == 1

def test__reference_mutate_operation(c, d):
    c.b = d

    with operation(c):
        c.b.a = 2

    assert c.a == 1
    assert c.b.a == 2
    assert c.b.b == None
    assert d.a == 1

def test__self_reference(c):
    c2 = refdup(c)

    with operation(c):
        c.b = c2
        c.b.a = 6

    assert c.a == 6
    assert c.b.a == 6
    assert c.b.b.a == 6

    assert c2.a == 1
    assert c2.b == None

def test__reference_nested_mutate_operation(c, d):
    c.b = d

    with operation(d):
        d.b = c
        d.b.b.a = 5

    assert c.a == 1
    assert c.b.a == 1
    assert c.b.b == None
    assert d.a == 1
    assert d.b.b.a == 5


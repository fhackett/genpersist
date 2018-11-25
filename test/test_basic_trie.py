from confluence import Trie, Node

def test__basic():
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

def test__trie_scenario1():
    t = Trie()

    t[(0,)] = 1

def test__basic_confluence():
    class C(Node):
        print('C')
        def __init__(self):
            print('init')
            self.a = 1
            self.b = None

    c = C()

    assert c.a == 1
    assert c.b is None

    d = C()

    assert d.a == 1
    assert d.b is None

    c.b = d

    print(c)

    assert c.a == 1
    assert c.b.a == 1
    assert c.b.b == None

    c.b.a = 2

    assert c.a == 1
    assert c.b.a == 2
    assert c.b.b == None
    assert d.a == 2


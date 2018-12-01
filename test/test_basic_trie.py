from genpersist import Trie

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


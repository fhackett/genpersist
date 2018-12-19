from genpersist import Trie

def test__trie_basic():
    t = Trie()

    assert t == Trie()

    t[(1,2,3)] = 5

    assert t.longest_prefix_item((1,2,3)) == ((1,2,3), 5)
    assert t.longest_prefix_item((1,2,3,4)) == ((1,2,3), 5)
    assert t.longest_prefix_item((1,2)) == (None, None)
    assert t.longest_prefix_item((1,2,3,4,5)) == ((1,2,3), 5)

    t[(1,2)] = 4

    assert t.longest_prefix_item((1,2,3)) == ((1,2,3), 5)
    assert t.longest_prefix_item((1,2,3,4)) == ((1,2,3), 5)
    assert t.longest_prefix_item((1,2)) == ((1,2), 4)
    assert t.longest_prefix_item((1,)) == (None, None)
    assert t.longest_prefix_item(()) == (None, None)

    t[()] = 3

    assert t.longest_prefix_item((1,2,3)) == ((1,2,3), 5)
    assert t.longest_prefix_item((1,2,3,4)) == ((1,2,3), 5)
    assert t.longest_prefix_item((1,2)) == ((1,2), 4)
    assert t.longest_prefix_item((1,)) == ((), 3)
    assert t.longest_prefix_item(()) == ((), 3)


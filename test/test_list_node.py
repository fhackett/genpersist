
from genpersist import ListNode, operation

def lens(n):
    p = n._root
    while p is not None:
        yield p.len
        p = p.nxt

def test__append_iterate():

    with operation():
        n = ListNode()
        assert list(lens(n)) == []
        assert list(n._iter_from(0)) == []
        n.append(1)
        assert list(lens(n)) == [1]
        assert list(n._iter_from(0)) == [1]
        n.append(2)
        assert list(lens(n)) == [2,1]
        assert list(n._iter_from(0)) == [1,2]
        n.append(3)
        assert list(lens(n)) == [3,2,1]
        assert list(n._iter_from(0)) == [1,2,3]
        n.append(4)
        assert list(lens(n)) == [4,3,2,1]
        assert list(n._iter_from(0)) == [1,2,3,4]
        n.append(5)
        assert list(lens(n)) == [5,4,3,2,1]
        assert list(n._iter_from(0)) == [1,2,3,4,5]

    assert list(n._iter_from(0)) == [1,2,3,4,5]
    assert list(n._iter_from(3)) == [4,5]
    assert list(n._iter_from(5)) == []

def test__getitem():

    with operation():
        n = ListNode([1])
        assert list(n[i] for i in range(len(n))) == [1]
        n.append(2)
        assert list(n[i] for i in range(len(n))) == [1,2]
        n.append(3)
        assert list(n[i] for i in range(len(n))) == [1,2,3]
        n.append(4)
        assert list(n[i] for i in range(len(n))) == [1,2,3,4]
        n.append(5)
        assert list(n[i] for i in range(len(n))) == [1,2,3,4,5]

    assert list(n[i] for i in range(len(n))) == [1,2,3,4,5]

def test__pop():
    with operation():
        n = ListNode([1,2,3,4,5])

        assert n.pop() == 5

        assert list(n) == [1,2,3,4]
        
        assert n.pop(2) == 3

        assert list(n) == [1,2,4]

    assert list(n) == [1,2,4]


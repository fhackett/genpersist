
from genpersist import ListNode, operation

def test__append_iterate():

    with operation():
        n = ListNode()
        assert list(n._iter_from(0)) == []
        n.append(1)
        assert list(n._iter_from(0)) == [1]
        n.append(2)
        assert list(n._iter_from(0)) == [1,2]
        n.append(3)
        assert list(n._iter_from(0)) == [1,2,3]
        n.append(4)
        assert list(n._iter_from(0)) == [1,2,3,4]
        n.append(5)
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


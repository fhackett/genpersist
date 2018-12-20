import pytest
from genpersist import ListNode, CopyList, operation

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

@pytest.fixture(params=[ListNode, CopyList])
def LN(request):
    return request.param

def test__getitem(LN):

    with operation():
        n = LN([1])
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

def test__pop(LN):
    with operation():
        n = LN([1,2,3,4,5])

        assert n.pop() == 5

        assert list(n) == [1,2,3,4]
        
        assert n.pop(2) == 3

        assert list(n) == [1,2,4]

    assert list(n) == [1,2,4]

    with operation(n) as nn:
        nn.pop(1)
        assert list(nn) == [1,4]
        assert list(n) == [1,2,4]

    assert list(nn) == [1,4]
    assert list(n) == [1,2,4]


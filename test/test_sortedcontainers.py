from genpersist import Node, operation
from sortedcontainers import SortedList

class WrappedSortedList(SortedList, Node):
    def __new__(cls, *args, **kwargs):
        return super(SortedList, cls).__new__(cls, *args, **kwargs)

def test__sorted_list_add():

    with operation():
        w = WrappedSortedList([5,1,2,3,4])

    assert list(w) == [1,2,3,4,5]

    with operation(w) as ww:
        ww.add(22)

    assert list(w) == [1,2,3,4,5]
    assert list(ww) == [1,2,3,4,5,22]

    with operation(w) as www:
        www.add(2.5)

    assert list(w) == [1,2,3,4,5]
    assert list(ww) == [1,2,3,4,5,22]
    assert list(www) == [1,2,2.5,3,4,5]

def test__sorted_list_discard():

    with operation():
        w = WrappedSortedList([5,1,2,3,4])

    assert list(w) == [1,2,3,4,5]

    with operation(w) as ww:
        ww.discard(2)

    assert list(w) == [1,2,3,4,5]
    assert list(ww) == [1,3,4,5]


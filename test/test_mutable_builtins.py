import pytest
from genpersist import Node, operation

class C(Node):
    pass

class D: pass

def test__converting_assignment():
    with operation():
        c1 = C()
        d = D()
        d.y = 4
        c1.d = d
        d.x = 3

    assert (c1.d.x, c1.d.y) == (3, 4)

    d.x = 8

    assert (c1.d.x, c1.d.y) == (3, 4)

    with operation(c1) as c2:
        c2.d.x = 5

    assert (c1.d.x, c1.d.y) == (3, 4)
    assert (c2.d.x, c2.d.y) == (5, 4)

def test__version_list():
    with operation():
        c1 = C()
        c1.lst = []

    with operation(c1) as c2:
        c2.lst.append(5)

    assert c1.lst == []
    assert c2.lst == [5]

def test__list_element_is_node():
    with operation():
        c1 = C()
        c1.lst = []

    with operation(c1) as c2:
        c2.lst.append(c1)

    with operation(c1) as c22:
        c22.lst.append(5)

    with operation(c2) as c3:
        c3.lst[0].lst.append(2)

    assert c1.lst == []
    assert c2.lst[0].lst == []
    assert len(c2.lst) == 1
    assert c3.lst[0].lst == [2]

def test__list_modify_after_assign():
    with operation():
        c1 = C()
        l = []
        c1.lst = l
        l.append(5)

    assert c1.lst == [5]


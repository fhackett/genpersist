import pytest
from genpersist import Node, operation

class C(Node): pass

def test__assign_tuple():
    with operation():
        c = C()
        c.tpl = ()

    assert c.tpl == ()

def test__assign_tuple_with_elements():
    with operation():
        c = C()
        c.x = (1,2)
        d = C()
        d.x = (3,4)

    assert c.x == (1,2)
    assert d.x == (3,4)

    with operation(c, d) as (c1, d1):
        c1.x = (c, d, d1)

    assert c.x == (1,2)
    assert d.x == (3,4)

    assert d1.x == (3,4)
    assert tuple(e.x for e in c1.x) == ((1,2), (3,4), (3,4))

    with operation(c1, d1) as (c2, d2):
        d2.x = (5,6)

    assert c.x == (1,2)
    assert d.x == (3,4)

    assert d1.x == (3,4)
    assert tuple(e.x for e in c1.x) == ((1,2), (3,4), (3,4))
 
    assert d2.x == (5,6)
    assert tuple(e.x for e in c2.x) == ((1,2), (3,4), (5,6))

class D: pass

def test__self_referential():
    with operation():
        d = D()
        d.x = (1, d)
        c = D()
        c.d = d

    # it's a cycle, did we crash?
    assert c.d.x[0] == 1 and c.d.x[1].x[0] == 1

def test__tuple_of_tuples():
    with operation():
        c = C()
        c.x = (1, (2, (3, (4, ()))))
    
    assert c.x == (1, (2, (3, (4, ()))))


@pytest.mark.xfail
def test__tuple_of_tuples_wrapped():
    with operation():
        c = C()
        c.x = ()
        print(c.x)
        c.x = (4, c.x)
        print(c.x)
        c.x = (3, c.x)
        print(c.x)
        c.x = (2, c.x)
        print(c.x)
        c.x = (1, c.x)
        print(c.x)
        
        assert c.x == (1, (2, (3, (4, ()))))

    assert c.x == (1, (2, (3, (4, ()))))



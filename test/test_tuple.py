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


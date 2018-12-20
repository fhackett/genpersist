# genpersist

WARNING: work in progress. Fairly functional, but you may sometimes run into stubs.

You can run the tests with py.test.

To make instances of a class persistent, have that class inherit from `genpersist.Node`.
The class will look and act exactly as it would have before, except you are not allowed
to instantiate it or write to its fields in any way outside of an `operation`. Reading
and methods that only read are fine at all times.

So, if you want to actually use your class you're probably wondering what an `operation` is.
It is a context manager.

You call it like this (assuming C is some random class with the appropriate fields):
```
from genpersist import operation

with operation():
    c  = C()
    c.a = 3
```

This allows you to instantiate your persistent classes and mutate them in any way you like.
Each time you do this it counts as one step in history.

Let's say we want to change `c` again:

```
with operation(c) as c2:
    c2.a += 1

assert c.a == 3
assert c2.a == 4
```

If you pass an object to `operation` you get a new handle to it that you can change.
This example shows that you can still access the old version with fields unchanged.
You might think this is just some kind of clone operation, but unlike cloning it is
copy on write. You only store what has changed.

Now let's say we want to make some temporal paradoxes: we want to hold a reference to our past
self.

```
with operation():
    c1 = C()
    c1.x = None

with operation(c1) as c2:
    c2.x = c1

assert c2.x.x is None
```

It Just Works(tm) - any reference to a past node can be assigned, such that you will get that
version when you access the field. If you actually wanted to create a reference cycle, use the
value that came from `operation`.

Now, let's try something a little adventurous: lists

```
with operation():
    c1 = C()
    l = [1]
    c1.x = l
    l.extend((2,3,4,5))

assert l == [1,2,3,4,5]
assert c1.x == [1,2,3,4,5]

l.clear()

assert l == []
assert c1.x == [1,2,3,4,5]
```

As a special case (TODO: same for dict and set), plain `list` objects are converted to a special
list-like type when you assign them to a persistent object. Notice however that if you then
mutate the list within the same operation the results will be reflected in the persistent version.
When the operation is done however, your list is frozen. Changing `l` again does nothing.

You can actually do the same to any "plain old Python" class as well (notice how D does not
inherit from Node):

```
class D: pass

with operation():
    c1 = C()
    d = D()
    d.a = 1
    c1.x = D()
    d.b = 2

d.c = 3

assert c1.x.a == 1
assert c1.x.b == 2
assert not hasattr(c1.x, 'c')
```

In this case the conversion is automatic. If you want this kind of thing to work for something
unusual, say, a builtin genpersist hasn't covered or some custom thing written in C then
you'll have to write your own wrapper. There is a system, but the underbelly may not be
pretty. TODO: make prettier, provide docs on how to use

More features/polish/docs to come.


# genpersist

WARNING: work in progress, needs more testing and features

For now, you can run the tests with py.test.

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
    c2.x = snapshot(c1)

assert c2.x.x is None
```

OK, so not quite as obvious as just `c2.x = c1`, but making that work would break some of the
underlying assumptions of the library. The best we can do is `snapshot`, which basically means
"give me a new version of c1 that is exactly the same as c1 in every way". Due to the way we
handle versions, this makes it so `snapshot(c1)` is `c1` from an alternate future, not the past
... and that means we shouldn't see the newer version (which happens to be `c2`) when we access
`c2.x`.

More features/polish/docs to come.


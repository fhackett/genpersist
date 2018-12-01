import pytest
from confluence import Node, operation, snapshot

class LinkedList(Node):
    class ListNode(Node):
        def __init__(self, value, nxt=None):
            self.value = value
            self.next = nxt

    def __init__(self, elements=()):
        self.root = None
        for element in elements:
            if self.root is None:
                prev = LinkedList.ListNode(element)
                self.root = prev
            else:
                prev.next = LinkedList.ListNode(element)
                prev = prev.next

    def __setitem__(self, n, val):
        initial_n = n
        curr = self.root
        while n > 0 and curr is not None:
            n -= 1
            curr = curr.next
        if n == 0 and curr is not None:
            curr.value = val
        else:
            raise IndexError(initial_n)

    def __getitem__(self, n):
        initial_n = n
        curr = self.root
        while n > 0 and curr is not None:
            n -= 1
            curr = curr.next
        if n == 0 and curr is not None:
            return curr.value
        else:
            raise IndexError(initial_n)
    
    def append(self, other):
        if self.root is None:
            self.root = other.root
        else:
            prev = self.root
            while prev.next is not None:
                prev = prev.next
            prev.next = other.root
    
    def __iter__(self):
        curr = self.root
        while curr is not None:
            yield curr.value
            curr = curr.next

def test__past_self_append():
    # node: the use of snapshot() here is required in order to link
    # with a previous version that shared its entire history with you
    # this is required for consistency, since over time links to past
    # but congruent versions are automatically updated to reflect subsequent
    # changes. if you don't want that, use snapshot()
    with operation():
        lst = LinkedList([1])
    
    assert list(lst) == [1]

    with operation(lst) as lst2:
        lst2.append(snapshot(lst))

    assert list(lst2) == [1,1]

    with operation(lst2) as lst3:
        lst3.append(snapshot(lst2))

    assert list(lst3) == [1,1,1,1]

    with operation(lst) as lst22:
        lst22[0] = 5
        lst22.append(lst3)

    assert list(lst22) == [5,1,1,1,1]


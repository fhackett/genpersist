import pytest

from sortedcontainers import SortedList
from genpersist import Node, operation

import timeit
import random

class WrappedSortedList(SortedList, Node):
    def __new__(cls, *args, **kwargs):
        return super(SortedList, cls).__new__(cls, *args, **kwargs)

@pytest.fixture(params=[10, 100, 1000, 10000, 100000, 1000000])
def sortedlist_element_count(request):
    return request.param

@pytest.fixture(params=[1000000])
def sortedlist_range(request):
    return request.param

def sortedlist_addremove_vanilla(element_count):
    l = SortedList(random.sample(range(element_count), element_count))
    def fn():
        y = random.randrange(element_count)
        l.add(y)
        l.discard(y)
    yield fn

def sortedlist_addremove_many_ops(element_count):
    with operation():
        l = WrappedSortedList(random.sample(range(element_count), element_count))
    def fn():
        with operation(l) as ll:
            y = random.randrange(element_count)
            ll.add(y)
            ll.discard(y)
    yield fn

def sortedlist_addremove_one_op(element_count):
    with operation():
        l = WrappedSortedList(random.sample(range(element_count), element_count))
    
    with operation(l) as ll:
        def fn():
                y = random.randrange(element_count)
                ll.add(y)
                ll.discard(y)
        yield fn

@pytest.fixture(params=[
    sortedlist_addremove_vanilla,
    sortedlist_addremove_many_ops,
    sortedlist_addremove_one_op])
def sortedlist_addremove_test_function(sortedlist_element_count, request):
    yield from request.param(sortedlist_element_count)

def test__bench__sortedlist_addremove(benchmark, sortedlist_addremove_test_function):
    benchmark(sortedlist_addremove_test_function)


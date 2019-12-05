import unittest
import yappi
import asyncio
import threading
from utils import YappiUnitTestCase, find_stat_by_name, burn_cpu, burn_io


class SingleThreadTests(YappiUnitTestCase):

    def test_recursive_coroutine(self):

        @asyncio.coroutine
        def a(n):
            if n <= 0:
                return
            yield from asyncio.sleep(0.1)
            burn_cpu(0.1)
            yield from a(n - 1)
            yield from a(n - 2)

        yappi.set_clock_type("cpu")
        yappi.start()
        asyncio.get_event_loop().run_until_complete(a(3))
        yappi.stop()

        r1 = '''
        ..p/yappi/tests/test_asyncio.py:11 a  9/1    0.000124  0.400667  0.044519
        ../yappi/tests/utils.py:126 burn_cpu  4      0.000000  0.400099  0.100025
        ..thon3.7/asyncio/tasks.py:582 sleep  4      0.000098  0.000444  0.000111
        '''
        stats = yappi.get_func_stats()
        self.assert_traces_almost_equal(r1, stats)

    def test_async_context_managers(self):
        pass

    def test_naive_generators(self):
        pass

    def test_async_generators(self):
        pass

    def test_basic_old_style(self):

        @asyncio.coroutine
        def a():
            yield from asyncio.sleep(0.1)
            burn_io(0.1)
            yield from asyncio.sleep(0.1)
            burn_io(0.1)
            yield from asyncio.sleep(0.1)
            burn_cpu(0.3)

        yappi.set_clock_type("wall")
        yappi.start(builtins=True)
        asyncio.get_event_loop().run_until_complete(a())
        asyncio.get_event_loop().run_until_complete(a())
        yappi.stop()

        r1 = '''
        ..p/yappi/tests/test_asyncio.py:43 a  2      0.000118  1.604049  0.802024
        ..thon3.7/asyncio/tasks.py:582 sleep  6      0.602749  0.603239  0.100540
        ../yappi/tests/utils.py:126 burn_cpu  2      0.576313  0.600026  0.300013
        ..p/yappi/tests/utils.py:135 burn_io  4      0.000025  0.400666  0.100166
        time.sleep                            4      0.400641  0.400641  0.100160
        '''
        stats = yappi.get_func_stats()

        self.assert_traces_almost_equal(r1, stats)

        yappi.clear_stats()
        yappi.set_clock_type("cpu")
        yappi.start(builtins=True)
        asyncio.get_event_loop().run_until_complete(a())
        asyncio.get_event_loop().run_until_complete(a())
        yappi.stop()
        stats = yappi.get_func_stats()
        r1 = '''
        ..p/yappi/tests/test_asyncio.py:43 a  2      0.000117  0.601170  0.300585
        ../yappi/tests/utils.py:126 burn_cpu  2      0.000000  0.600047  0.300024
        ..thon3.7/asyncio/tasks.py:582 sleep  6      0.000159  0.000801  0.000134
        time.sleep                            4      0.000169  0.000169  0.000042
        '''
        self.assert_traces_almost_equal(r1, stats)


class MultiThreadTests(YappiUnitTestCase):

    def test_basic(self):

        @asyncio.coroutine
        def a():
            yield from asyncio.sleep(0.1)
            burn_cpu(0.2)

        @asyncio.coroutine
        def b():
            yield from a()

        @asyncio.coroutine
        def recursive_a(n):
            if not n:
                return
            burn_io(0.1)
            yield from asyncio.sleep(0.1)
            yield from recursive_a(n - 1)

        def tag_cbk():
            cthread = threading.current_thread()
            try:
                return cthread._tag
            except:
                return -1

        yappi.set_clock_type("wall")
        threading.current_thread()._tag = 0
        yappi.set_tag_callback(tag_cbk)

        def _thread_event_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        _TCOUNT = 5
        _ctag = 1

        ts = []
        for i in range(_TCOUNT):
            _loop = asyncio.new_event_loop()
            t = threading.Thread(target=_thread_event_loop, args=(_loop, ))
            t._tag = _ctag
            t._loop = _loop
            t.start()

            ts.append(t)
            _ctag += 1

        @asyncio.coroutine
        def driver():
            futs = []
            for i in range(_TCOUNT):
                fut = asyncio.run_coroutine_threadsafe(a(), ts[i]._loop)
                futs.append(fut)
                fut = asyncio.run_coroutine_threadsafe(
                    recursive_a(5), ts[i]._loop
                )
                futs.append(fut)
                fut = asyncio.run_coroutine_threadsafe(b(), ts[i]._loop)
                futs.append(fut)
            for fut in futs:
                fut.result()

        yappi.start()
        asyncio.get_event_loop().run_until_complete(driver())
        yappi.stop()
        yappi.get_func_stats().print_all()
        t1 = '''
        ..ts/test_asyncio.py:100 recursive_a  30/5   0.000597  7.550892  0.251696
        ..thon3.7/asyncio/tasks.py:582 sleep  35     7.085052  7.087429  0.202498
        tests/test_asyncio.py:91 a            10     0.000089  5.573958  0.557396
        tests/utils.py:135 burn_io            25     0.000132  3.671073  0.146843
        tests/test_asyncio.py:96 b            5      0.000023  3.375634  0.675127
        tests/utils.py:126 burn_cpu           10     2.264558  2.365662  0.236566
        '''

    def test_recursive_coroutine(self):
        pass

    def test_same_coroutine_call_from_different_threads(self):
        pass


if __name__ == '__main__':
    unittest.main()

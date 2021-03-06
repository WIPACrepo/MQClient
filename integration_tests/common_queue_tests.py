"""Run integration tests for given backend, on Queue class."""

import logging
from multiprocessing.dummy import Pool as ThreadPool
from typing import Any, List

import pytest  # type: ignore

# local imports
from MQClient import Queue
from MQClient.backend_interface import Backend

from .utils import DATA_LIST, _log_recv, _log_recv_multiple, _log_send

logging.getLogger().setLevel(logging.DEBUG)


class PubSubQueue:
    """Integration test suite for Queue objects."""

    backend = None  # type: Backend

    def test_10(self, queue_name: str) -> None:
        """Test one pub, one sub."""
        pub_sub = Queue(self.backend, name=queue_name)
        pub_sub.send(DATA_LIST[0])
        _log_send(DATA_LIST[0])

        with pub_sub.recv_one() as d:
            _log_recv(d)
            assert d == DATA_LIST[0]

        for d in DATA_LIST:
            pub_sub.send(d)
            _log_send(d)

        with pub_sub.recv(timeout=1) as gen:
            for i, d in enumerate(gen):
                _log_recv(d)
                assert d == DATA_LIST[i]

    def test_11(self, queue_name: str) -> None:
        """Test an individual pub and an individual sub."""
        pub = Queue(self.backend, name=queue_name)
        pub.send(DATA_LIST[0])
        _log_send(DATA_LIST[0])

        sub = Queue(self.backend, name=queue_name)
        with sub.recv_one() as d:
            _log_recv(d)
            assert d == DATA_LIST[0]

        for d in DATA_LIST:
            pub.send(d)
            _log_send(d)

        with sub.recv(timeout=1) as gen:
            for i, d in enumerate(gen):
                _log_recv(d)
                assert d == DATA_LIST[i]

    def test_12(self, queue_name: str) -> None:
        """Failure-test one pub, two subs (one subscribed to wrong queue)."""
        pub = Queue(self.backend, name=queue_name)
        pub.send(DATA_LIST[0])
        _log_send(DATA_LIST[0])

        sub_fail = Queue(self.backend, name=f"{queue_name}-fail")
        with pytest.raises(Exception) as excinfo:
            with sub_fail.recv_one() as d:
                _log_recv(d)
            assert "No message available" in str(excinfo.value)

        sub = Queue(self.backend, name=queue_name)
        with sub.recv_one() as d:
            _log_recv(d)
            assert d == DATA_LIST[0]

    def test_20(self, queue_name: str) -> None:
        """Test one pub, multiple subs, ordered/alternatingly."""
        pub = Queue(self.backend, name=queue_name)

        # for each send, create and receive message via a new sub
        for data in DATA_LIST:
            pub.send(data)
            _log_send(data)

            sub = Queue(self.backend, name=queue_name)
            with sub.recv_one() as d:
                _log_recv(d)
                assert d == data
            # sub.close() -- no longer needed

    def _test_21(self, queue_name: str, num_subs: int) -> None:
        """Test one pub, multiple subs, unordered (front-loaded sending)."""
        pub = Queue(self.backend, name=queue_name)
        for data in DATA_LIST:
            pub.send(data)
            _log_send(data)

        def recv_thread(_: int) -> List[Any]:
            sub = Queue(self.backend, name=queue_name)
            with sub.recv(timeout=1) as gen:
                recv_data_list = list(gen)
            _log_recv_multiple(recv_data_list)
            return recv_data_list

        with ThreadPool(num_subs) as p:
            received_data = p.map(recv_thread, range(num_subs))
        received_data = [item for sublist in received_data for item in sublist]

        assert len(DATA_LIST) == len(received_data)
        for data in DATA_LIST:
            assert data in received_data

    def test_21_fewer(self, queue_name: str) -> None:
        """Test one pub, multiple subs, unordered (front-loaded sending).

        Fewer subs than messages.
        """
        self._test_21(queue_name, len(DATA_LIST) // 2)

    def test_21_same(self, queue_name: str) -> None:
        """Test one pub, multiple subs, unordered (front-loaded sending).

        Same number of subs as messages.
        """
        self._test_21(queue_name, len(DATA_LIST))

    def test_21_more(self, queue_name: str) -> None:
        """Test one pub, multiple subs, unordered (front-loaded sending).

        More subs than messages.
        """
        self._test_21(queue_name, len(DATA_LIST) ** 2)

    def test_22(self, queue_name: str) -> None:
        """Test one pub, multiple subs, unordered (front-loaded sending).

        Use the same number of subs as number of messages.
        """
        pub = Queue(self.backend, name=queue_name)
        for data in DATA_LIST:
            pub.send(data)
            _log_send(data)

        def recv_thread(_: int) -> Any:
            sub = Queue(self.backend, name=queue_name)
            with sub.recv_one() as d:
                recv_data = d
            # sub.close() -- no longer needed
            _log_recv(recv_data)
            return recv_data

        with ThreadPool(len(DATA_LIST)) as p:
            received_data = p.map(recv_thread, range(len(DATA_LIST)))

        assert len(DATA_LIST) == len(received_data)
        for data in DATA_LIST:
            assert data in received_data

    def test_23(self, queue_name: str) -> None:
        """Failure-test one pub, and too many subs.

        More subs than messages with `recv_one()` will raise an
        exception.
        """
        pub = Queue(self.backend, name=queue_name)
        for data in DATA_LIST:
            pub.send(data)
            _log_send(data)

        def recv_thread(_: int) -> Any:
            sub = Queue(self.backend, name=queue_name)
            with sub.recv_one() as d:
                recv_data = d
            # sub.close() -- no longer needed
            _log_recv(recv_data)

        with ThreadPool(len(DATA_LIST)) as p:
            p.map(recv_thread, range(len(DATA_LIST)))

        # Extra Sub
        with pytest.raises(Exception) as excinfo:
            recv_thread(0)
            assert "No message available" in str(excinfo.value)

    def test_30(self, queue_name: str) -> None:
        """Test multiple pubs, one sub, ordered/alternatingly."""
        sub = Queue(self.backend, name=queue_name)

        for data in DATA_LIST:
            pub = Queue(self.backend, name=queue_name)
            pub.send(data)
            _log_send(data)

            with sub.recv(timeout=1) as gen:
                received_data = list(gen)
            _log_recv_multiple(received_data)

            assert len(received_data) == 1
            assert data == received_data[0]

    def test_31(self, queue_name: str) -> None:
        """Test multiple pubs, one sub, unordered (front-loaded sending)."""
        for data in DATA_LIST:
            pub = Queue(self.backend, name=queue_name)
            pub.send(data)
            _log_send(data)

        sub = Queue(self.backend, name=queue_name)
        with sub.recv(timeout=1) as gen:
            received_data = list(gen)
        _log_recv_multiple(received_data)

        assert len(DATA_LIST) == len(received_data)
        for data in DATA_LIST:
            assert data in received_data

    def test_40(self, queue_name: str) -> None:
        """Test multiple pubs, multiple subs, ordered/alternatingly.

        Use the same number of pubs as subs.
        """
        for data in DATA_LIST:
            pub = Queue(self.backend, name=queue_name)
            pub.send(data)
            _log_send(data)

            sub = Queue(self.backend, name=queue_name)
            with sub.recv(timeout=1) as gen:
                received_data = list(gen)
            _log_recv_multiple(received_data)

            assert len(received_data) == 1
            assert data == received_data[0]

    def test_41(self, queue_name: str) -> None:
        """Test multiple pubs, multiple subs, unordered (front-loaded sending).

        Use the same number of pubs as subs.
        """
        for data in DATA_LIST:
            pub = Queue(self.backend, name=queue_name)
            pub.send(data)
            _log_send(data)

        received_data = []
        for _ in range(len(DATA_LIST)):
            sub = Queue(self.backend, name=queue_name)
            with sub.recv_one() as d:
                _log_recv(d)
                received_data.append(d)
            # sub.close() -- no longer needed

        assert len(DATA_LIST) == len(received_data)
        for data in DATA_LIST:
            assert data in received_data

    def test_42(self, queue_name: str) -> None:
        """Test multiple pubs, multiple subs, unordered (front-loaded sending).

        Use the more pubs than subs.
        """
        for data in DATA_LIST:
            pub = Queue(self.backend, name=queue_name)
            pub.send(data)
            _log_send(data)

        received_data = []
        for i in range(len(DATA_LIST)):
            if i % 2 == 0:
                sub = Queue(self.backend, name=queue_name)
            with sub.recv_one() as d:
                _log_recv(d)
                received_data.append(d)
            # sub.close() -- no longer needed

        assert len(DATA_LIST) == len(received_data)
        for data in DATA_LIST:
            assert data in received_data

    def test_43(self, queue_name: str) -> None:
        """Test multiple pubs, multiple subs, unordered (front-loaded sending).

        Use the fewer pubs than subs.
        """
        for i, data in enumerate(DATA_LIST):
            if i % 2 == 0:
                pub = Queue(self.backend, name=queue_name)
            pub.send(data)
            _log_send(data)

        received_data = []
        for _ in range(len(DATA_LIST)):
            sub = Queue(self.backend, name=queue_name)
            with sub.recv_one() as d:
                _log_recv(d)
                received_data.append(d)
            # sub.close() -- no longer needed

        assert len(DATA_LIST) == len(received_data)
        for data in DATA_LIST:
            assert data in received_data

    def test_50(self, queue_name: str) -> None:
        """Test_20 with variable prefetching.

        One pub, multiple subs.
        """
        pub = Queue(self.backend, name=queue_name)

        for i in range(1, len(DATA_LIST) * 2):
            # for each send, create and receive message via a new sub
            for data in DATA_LIST:
                pub.send(data)
                _log_send(data)

                sub = Queue(self.backend, name=queue_name, prefetch=i)
                with sub.recv_one() as d:
                    _log_recv(d)
                    assert d == data
                # sub.close() -- no longer needed

    def test_51(self, queue_name: str) -> None:
        """Test one pub, multiple subs, with prefetching.

        Prefetching should have no visible affect.
        """
        for data in DATA_LIST:
            pub = Queue(self.backend, name=queue_name)
            pub.send(data)
            _log_send(data)

        received_data = []

        # this should not eat up the whole queue
        sub = Queue(self.backend, name=queue_name, prefetch=20)
        with sub.recv_one() as d:
            _log_recv(d)
            received_data.append(d)
        with sub.recv_one() as d:
            _log_recv(d)
            received_data.append(d)
        # sub.close() -- no longer needed

        sub2 = Queue(self.backend, name=queue_name, prefetch=2)
        with sub2.recv(timeout=1) as gen:
            for _, d in enumerate(gen):
                _log_recv(d)
                received_data.append(d)

        assert len(DATA_LIST) == len(received_data)
        for data in DATA_LIST:
            assert data in received_data

    def test_60(self, queue_name: str) -> None:
        """Test recv() fail and recovery, with one recv() call."""
        pub = Queue(self.backend, name=queue_name)
        for d in DATA_LIST:
            pub.send(d)
            _log_send(d)

        class TestException(Exception):  # pylint: disable=C0115
            pass

        sub = Queue(self.backend, name=queue_name)
        recv_gen = sub.recv(timeout=1)
        with recv_gen as gen:
            for i, d in enumerate(gen):
                if i == 2:
                    raise TestException()
                _log_recv(d)
                assert d == DATA_LIST[i]

        # continue where we left off
        with recv_gen as gen:
            for i, d in enumerate(gen, start=2):
                _log_recv(d)
                assert d == DATA_LIST[i]

    def test_61(self, queue_name: str) -> None:
        """Test recv() fail and recovery, with multiple recv() calls."""
        pub = Queue(self.backend, name=queue_name)
        for d in DATA_LIST:
            pub.send(d)
            _log_send(d)

        class TestException(Exception):  # pylint: disable=C0115
            pass

        sub = Queue(self.backend, name=queue_name)
        with sub.recv(timeout=1) as gen:
            for i, d in enumerate(gen):
                if i == 2:
                    raise TestException()
                _log_recv(d)
                assert d == DATA_LIST[i]

        # continue where we left off
        with sub.recv(timeout=1) as gen:
            for i, d in enumerate(gen, start=2):
                _log_recv(d)
                assert d == DATA_LIST[i]

    def test_62(self, queue_name: str) -> None:
        """Test recv() fail and recovery, with error propagation."""
        pub = Queue(self.backend, name=queue_name)
        for d in DATA_LIST:
            pub.send(d)
            _log_send(d)

        class TestException(Exception):  # pylint: disable=C0115
            pass

        sub = Queue(self.backend, name=queue_name)
        sub._propagate_recv_error = True  # pylint: disable=W0212
        excepted = False
        try:
            with sub.recv(timeout=1) as gen:
                for i, d in enumerate(gen):
                    if i == 2:
                        raise TestException()
                    _log_recv(d)
                    assert d == DATA_LIST[i]
        except TestException:
            excepted = True
        assert excepted

        # continue where we left off
        with sub.recv(timeout=1) as gen:
            for i, d in enumerate(gen, start=2):
                _log_recv(d)
                assert d == DATA_LIST[i]

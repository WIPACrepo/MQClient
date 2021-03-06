"""Parent class for backend unit tests."""

import logging
import pickle
import uuid
from typing import Any, List

import pytest  # type: ignore

# local imports
from MQClient import Queue
from MQClient.backend_interface import Backend
from MQClient.backends import rabbitmq

logging.getLogger().setLevel(logging.DEBUG)


class BackendUnitTest:
    """Unit test suite interface for specified backend."""

    backend = None  # type: Backend
    con_patch = ''

    @pytest.fixture  # type: ignore
    def mock_con(self, mocker: Any) -> Any:
        """Patch mock_con."""
        return mocker.patch(self.con_patch)

    @staticmethod
    @pytest.fixture  # type: ignore
    def queue_name() -> str:
        """Get random queue name."""
        name = uuid.uuid4().hex
        logging.info(f"NAME :: {name}")
        return name

    @staticmethod
    def _get_mock_nack(mock_con: Any) -> Any:
        """Return mock 'nack' function call."""
        raise NotImplementedError()

    @staticmethod
    def _get_mock_ack(mock_con: Any) -> Any:
        """Return mock 'ack' function call."""
        raise NotImplementedError()

    @staticmethod
    def _get_mock_close(mock_con: Any) -> Any:
        """Return mock 'close' function call."""
        raise NotImplementedError()

    @staticmethod
    def _enqueue_mock_messages(mock_con: Any, data: List[bytes], ids: List[int],
                               append_none: bool = True) -> None:
        """Place messages on the mock queue."""
        raise NotImplementedError()

    def test_create_pub_queue(self, mock_con: Any, queue_name: str) -> None:
        """Test creating pub queue."""
        raise NotImplementedError()

    def test_create_sub_queue(self, mock_con: Any, queue_name: str) -> None:
        """Test creating sub queue."""
        raise NotImplementedError()

    def test_send_message(self, mock_con: Any, queue_name: str) -> None:
        """Test sending message."""
        raise NotImplementedError()

    def test_get_message(self, mock_con: Any, queue_name: str) -> None:
        """Test getting message."""
        raise NotImplementedError()

    def test_ack_message(self, mock_con: Any, queue_name: str) -> None:
        """Test acking message."""
        q = self.backend.create_sub_queue("localhost", queue_name)
        q.ack_message(12)
        self._get_mock_ack(mock_con).assert_called_with(12)

    def test_reject_message(self, mock_con: Any, queue_name: str) -> None:
        """Test rejecting message."""
        q = self.backend.create_sub_queue("localhost", queue_name)
        q.reject_message(12)
        self._get_mock_nack(mock_con).assert_called_with(12)

    def test_message_generator_0(self, mock_con: Any, queue_name: str) -> None:
        """Test message generator."""
        q = self.backend.create_sub_queue("localhost", queue_name)
        num_msgs = 100

        fake_data = ['baz-{i}'.encode('utf-8') for i in range(num_msgs)]
        fake_ids = [i * 10 for i in range(num_msgs)]
        self._enqueue_mock_messages(mock_con, fake_data, fake_ids)

        for i, msg in enumerate(q.message_generator()):
            logging.debug(i)
            if i > 0:  # see if previous msg was acked
                prev_id = (i - 1) * 10
                self._get_mock_ack(mock_con).assert_called_with(prev_id)
            assert msg is not None
            assert msg.msg_id == fake_ids[i]
            assert msg.data == fake_data[i]

        last_id = (num_msgs - 1) * 10
        self._get_mock_ack(mock_con).assert_called_with(last_id)
        self._get_mock_close(mock_con).assert_called()

    def test_message_generator_1(self, mock_con: Any, queue_name: str) -> None:
        """Test message generator."""
        q = self.backend.create_sub_queue("localhost", queue_name)

        fake_data = [b'foo, bar', b'baz']
        fake_ids = [12, 20]
        self._enqueue_mock_messages(mock_con, fake_data, fake_ids, append_none=False)

        m = None
        for i, x in enumerate(q.message_generator()):
            m = x
            if i == 0:
                break

        assert m is not None
        assert m.msg_id == 12
        assert m.data == b'foo, bar'
        self._get_mock_ack(mock_con).assert_called_with(12)
        self._get_mock_close(mock_con).assert_called()

    def test_message_generator_2(self, mock_con: Any, queue_name: str) -> None:
        """Test message generator."""
        q = self.backend.create_sub_queue("localhost", queue_name)

        self._enqueue_mock_messages(mock_con, [b'foo, bar'], [12])

        m = None
        for i, x in enumerate(q.message_generator()):
            assert i < 1
            m = x
        assert m is not None
        assert m.msg_id == 12
        assert m.data == b'foo, bar'
        self._get_mock_ack(mock_con).assert_called_with(12)
        self._get_mock_close(mock_con).assert_called()

    def test_message_generator_upstream_error(self, mock_con: Any, queue_name: str) -> None:
        """Failure-test message generator.

        Generator should raise Exception originating upstream (a.k.a.
        from package code).
        """
        raise NotImplementedError()

    def test_message_generator_no_auto_ack(self, mock_con: Any, queue_name: str) -> None:
        """Test message generator.

        Generator should not ack messages.
        """
        q = self.backend.create_sub_queue("localhost", queue_name)

        fake_data = [b'baz-0', b'baz-1', b'baz-2']
        fake_ids = [0, 1, 2]
        self._enqueue_mock_messages(mock_con, fake_data, fake_ids)

        gen = q.message_generator(auto_ack=False)
        i = 0
        for msg in gen:
            logging.debug(i)
            if i > 0:  # see if previous msg was acked
                self._get_mock_ack(mock_con).assert_not_called()

            assert msg is not None
            assert msg.msg_id == i
            assert msg.data == fake_data[i]

            i += 1

    def test_message_generator_propagate_error(self, mock_con: Any, queue_name: str) -> None:
        """Failure-test message generator.

        Generator should raise Exception, nack, and close. Unlike in an
        integration test, nacked messages are not put back on the queue.
        """
        q = self.backend.create_sub_queue("localhost", queue_name)

        fake_data = [b'baz-0', b'baz-1', b'baz-2']
        fake_ids = [0, 1, 2]
        self._enqueue_mock_messages(mock_con, fake_data, fake_ids, append_none=False)

        gen = q.message_generator()  # propagate_error=True
        i = 0
        for msg in gen:
            logging.debug(i)
            assert i < 3
            if i > 0:  # see if previous msg was acked
                self._get_mock_ack(mock_con).assert_called_with(i - 1)

            assert msg is not None
            assert msg.msg_id == i
            assert msg.data == fake_data[i]

            if i == 2:
                with pytest.raises(Exception):
                    gen.throw(Exception)
                self._get_mock_nack(mock_con).assert_called_with(i)
                self._get_mock_close(mock_con).assert_called()

            i += 1

    def test_message_generator_suppress_error(self, mock_con: Any, queue_name: str) -> None:
        """Failure-test message generator.

        Generator should not raise Exception. Unlike in an integration
        test, nacked messages are not put back on the queue.
        """
        q = self.backend.create_sub_queue("localhost", queue_name)
        num_msgs = 11
        if num_msgs % 2 == 0:
            raise RuntimeError("`num_msgs` must be odd, so last message is nacked")

        fake_data = [f'baz-{i}'.encode('utf-8') for i in range(num_msgs)]
        fake_ids = [i * 10 for i in range(num_msgs)]
        self._enqueue_mock_messages(mock_con, fake_data, fake_ids)

        gen = q.message_generator(propagate_error=False)
        i = 0
        # odds are acked and evens are nacked
        for msg in gen:
            logging.debug(i)
            if i > 0:
                prev_id = (i - 1) * 10
                if i % 2 == 0:  # see if previous EVEN msg was acked
                    self._get_mock_ack(mock_con).assert_called_with(prev_id)
                else:  # see if previous ODD msg was NOT acked
                    with pytest.raises(AssertionError):
                        self._get_mock_ack(mock_con).assert_called_with(prev_id)

            assert msg is not None
            assert msg.msg_id == i * 10
            assert msg.data == fake_data[i]

            if i % 2 == 0:
                gen.throw(Exception)
                self._get_mock_nack(mock_con).assert_called_with(i * 10)

            i += 1
        self._get_mock_close(mock_con).assert_called()

    def test_message_generator_consumer_exception_fail(self, mock_con: Any, queue_name: str) -> None:
        """Failure-test message generator.

        Not so much a test, as an example of why MessageGeneratorContext
        is needed.
        """
        q = self.backend.create_sub_queue("localhost", queue_name)

        self._enqueue_mock_messages(mock_con, [b'baz'], [0], append_none=False)

        excepted = False
        try:
            for msg in q.message_generator(propagate_error=False):
                logging.debug(msg)
                raise Exception
        except Exception:
            excepted = True  # MessageGeneratorContext would've suppressed the Exception
        assert excepted

        # MessageGeneratorContext would've guaranteed both of these
        with pytest.raises(AssertionError):
            self._get_mock_close(mock_con).assert_not_called()
        with pytest.raises(AssertionError):
            self._get_mock_nack(mock_con).assert_called_with(0)

    def test_queue_recv_consumer(self, mock_con: Any, queue_name: str) -> None:
        """Test Queue.recv()."""
        q = Queue(self.backend, address="localhost", name=queue_name)

        fake_data = [pickle.dumps('baz', protocol=4)]
        self._enqueue_mock_messages(mock_con, fake_data, [0])

        with q.recv() as gen:
            for msg in gen:
                logging.debug(msg)
                assert msg
                assert msg == pickle.loads(fake_data[0])

        self._get_mock_close(mock_con).assert_called()
        self._get_mock_ack(mock_con).assert_called_with(0)

    def test_queue_recv_comsumer_exception_0(self, mock_con: Any, queue_name: str) -> None:
        """Failure-test Queue.recv().

        When an Exception is raised in `with` block, the Queue should:
        - NOT close (pub) on exit
        - nack the message
        - suppress the Exception
        """
        q = Queue(self.backend, address="localhost", name=queue_name)

        fake_data = [pickle.dumps('baz-0', protocol=4), pickle.dumps('baz-1', protocol=4)]
        fake_ids = [0, 1]
        self._enqueue_mock_messages(mock_con, fake_data, fake_ids, append_none=False)

        class TestException(Exception):  # pylint: disable=C0115
            pass

        with q.recv() as gen:  # propagate_error=False
            for i, msg in enumerate(gen):
                assert i == 0
                logging.debug(msg)
                raise TestException

        self._get_mock_close(mock_con).assert_not_called()
        self._get_mock_nack(mock_con).assert_called_with(0)

    def test_queue_recv_comsumer_exception_1(self, mock_con: Any, queue_name: str) -> None:
        """Failure-test Queue.recv().

        The Queue.recv()'s context manager should be reusable after
        suppressing an Exception.
        """
        q = Queue(self.backend, address="localhost", name=queue_name)
        num_msgs = 12

        fake_data = [pickle.dumps(f'baz-{i}', protocol=4) for i in range(num_msgs)]
        fake_ids = [i * 10 for i in range(num_msgs)]
        self._enqueue_mock_messages(mock_con, fake_data, fake_ids)

        class TestException(Exception):  # pylint: disable=C0115
            pass

        g = q.recv()
        with g as gen:  # propagate_error=False
            for msg in gen:
                logging.debug(msg)
                raise TestException

        self._get_mock_close(mock_con).assert_not_called()
        self._get_mock_nack(mock_con).assert_called_with(0)

        logging.info("Round 2")

        # continue where we left off
        with g as gen:  # propagate_error=False
            self._get_mock_ack(mock_con).assert_not_called()
            for i, msg in enumerate(gen, start=1):
                logging.debug(f"{i} :: {msg}")
                if i > 1:  # see if previous msg was acked
                    prev_id = (i - 1) * 10
                    self._get_mock_ack(mock_con).assert_called_with(prev_id)

            last_id = (num_msgs - 1) * 10
            self._get_mock_ack(mock_con).assert_called_with(last_id)

        self._get_mock_close(mock_con).assert_called()

    def test_queue_recv_comsumer_exception_2(self, mock_con: Any, queue_name: str) -> None:
        """Failure-test Queue.recv().

        Same as test_queue_recv_comsumer_exception_1() but with multiple
        recv() calls.
        """
        q = Queue(self.backend, address="localhost", name=queue_name)
        num_msgs = 12

        fake_data = [pickle.dumps(f'baz-{i}', protocol=4) for i in range(num_msgs)]
        fake_ids = [i * 10 for i in range(num_msgs)]
        self._enqueue_mock_messages(mock_con, fake_data, fake_ids)

        class TestException(Exception):  # pylint: disable=C0115
            pass

        with q.recv() as gen:  # propagate_error=False
            for msg in gen:
                logging.debug(msg)
                raise TestException

        self._get_mock_close(mock_con).assert_not_called()
        self._get_mock_nack(mock_con).assert_called_with(0)

        logging.info("Round 2")

        # continue where we left off
        with q.recv() as gen:  # propagate_error=False
            self._get_mock_ack(mock_con).assert_not_called()
            for i, msg in enumerate(gen, start=1):
                logging.debug(f"{i} :: {msg}")
                if i > 1:  # see if previous msg was acked
                    prev_id = (i - 1) * 10
                    self._get_mock_ack(mock_con).assert_called_with(prev_id)

            last_id = (num_msgs - 1) * 10
            self._get_mock_ack(mock_con).assert_called_with(last_id)

        self._get_mock_close(mock_con).assert_called()

    def test_queue_recv_comsumer_exception_3(self, mock_con: Any, queue_name: str) -> None:
        """Failure-test Queue.recv().

        Same as test_queue_recv_comsumer_exception_2() but with error
        propagation.
        """
        q = Queue(self.backend, address="localhost", name=queue_name)
        q._propagate_recv_error = True  # pylint: disable=W0212
        num_msgs = 12

        fake_data = [pickle.dumps(f'baz-{i}', protocol=4) for i in range(num_msgs)]
        fake_ids = [i * 10 for i in range(num_msgs)]
        self._enqueue_mock_messages(mock_con, fake_data, fake_ids)

        class TestException(Exception):  # pylint: disable=C0115
            pass

        with pytest.raises(TestException):
            with q.recv() as gen:  # propagate_error=True
                for msg in gen:
                    logging.debug(msg)
                    raise TestException

        self._get_mock_close(mock_con).assert_called()
        self._get_mock_nack(mock_con).assert_called_with(0)

        logging.info("Round 2")

        # Hack -- rabbitmq deletes its connection (mock_con) when close()
        # is called, so we need to re-enqueue messages to avoid getting
        # the entire original list.
        # ***Note***: this hack isn't needed in non-mocking tests, see
        # common_queue_tests.py integration tests #60+.
        if isinstance(q.backend, rabbitmq.Backend):
            self._enqueue_mock_messages(mock_con, fake_data[1:], fake_ids[1:])

        # continue where we left off
        with q.recv() as gen:  # propagate_error=True
            self._get_mock_ack(mock_con).assert_not_called()
            for i, msg in enumerate(gen, start=1):
                logging.debug(f"{i} :: {msg}")
                if i > 1:  # see if previous msg was acked
                    prev_id = (i - 1) * 10
                    self._get_mock_ack(mock_con).assert_called_with(prev_id)

            last_id = (num_msgs - 1) * 10
            self._get_mock_ack(mock_con).assert_called_with(last_id)

        self._get_mock_close(mock_con).assert_called()

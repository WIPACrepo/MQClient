"""Unit Tests for Pulsar Backend."""

from typing import Any, List

import pytest  # type: ignore

# local imports
from MQClient.backends import apachepulsar

from .common_unit_tests import BackendUnitTest


class TestUnitApachePulsar(BackendUnitTest):
    """Unit test suite interface for Apache Pulsar backend."""

    backend = apachepulsar.Backend()
    con_patch = 'pulsar.Client'

    @staticmethod
    def _get_mock_nack(mock_con: Any) -> Any:
        """Return mock 'nack' function call."""
        return mock_con.return_value.subscribe.return_value.negative_acknowledge

    @staticmethod
    def _get_mock_ack(mock_con: Any) -> Any:
        """Return mock 'ack' function call."""
        return mock_con.return_value.subscribe.return_value.acknowledge

    @staticmethod
    def _get_mock_close(mock_con: Any) -> Any:
        """Return mock 'close' function call."""
        return mock_con.return_value.close

    @staticmethod
    def _enqueue_mock_messages(mock_con: Any, data: List[bytes], ids: List[int],
                               append_none: bool = True) -> None:
        """Place messages on the mock queue."""
        if append_none:
            data += [None]  # type: ignore
            ids += [None]  # type: ignore
        mock_con.return_value.subscribe.return_value.receive.return_value.data.side_effect = data
        mock_con.return_value.subscribe.return_value.receive.return_value.message_id.side_effect = ids

    def test_create_pub_queue(self, mock_con: Any, queue_name: str) -> None:
        """Test creating pub queue."""
        q = self.backend.create_pub_queue("localhost", queue_name)
        assert q.topic == queue_name
        mock_con.return_value.create_producer.assert_called()

    def test_create_sub_queue(self, mock_con: Any, queue_name: str) -> None:
        """Test creating sub queue."""
        q = self.backend.create_sub_queue("localhost", queue_name, prefetch=213)
        assert q.topic == queue_name
        assert q.prefetch == 213
        mock_con.return_value.subscribe.assert_called()

    def test_send_message(self, mock_con: Any, queue_name: str) -> None:
        """Test sending message."""
        q = self.backend.create_pub_queue("localhost", queue_name)
        q.send_message(b"foo, bar, baz")
        mock_con.return_value.create_producer.return_value.send.assert_called_with(b'foo, bar, baz')

    def test_get_message(self, mock_con: Any, queue_name: str) -> None:
        """Test getting message."""
        q = self.backend.create_sub_queue("localhost", queue_name)
        mock_con.return_value.subscribe.return_value.receive.return_value.data.return_value = b'foo, bar'
        mock_con.return_value.subscribe.return_value.receive.return_value.message_id.return_value = 12
        m = q.get_message()

        assert m is not None
        assert m.msg_id == 12
        assert m.data == b'foo, bar'

    def test_message_generator_upstream_error(self, mock_con: Any, queue_name: str) -> None:
        """Failure-test message generator.

        Generator should raise Exception originating upstream (a.k.a.
        from pulsar-package code).
        """
        q = self.backend.create_sub_queue("localhost", queue_name)

        mock_con.return_value.subscribe.return_value.receive.side_effect = Exception()
        with pytest.raises(Exception):
            _ = list(q.message_generator())
        self._get_mock_close(mock_con).assert_called()

        # `propagate_error` attribute has no affect (b/c it deals w/ *downstream* errors)
        mock_con.return_value.subscribe.return_value.receive.side_effect = Exception()
        with pytest.raises(Exception):
            _ = list(q.message_generator(propagate_error=False))
        self._get_mock_close(mock_con).assert_called()

"""Run integration tests for given backend, on backend_interface classes.

Verify functionality that is abstracted away from the Queue class.
"""

import copy
import itertools
import logging
import pickle
from typing import List, Optional

# local imports
from MQClient.backend_interface import Backend, Message

from .utils import DATA_LIST, _log_recv, _log_send

logging.getLogger().setLevel(logging.DEBUG)


def _log_recv_message(recv_msg: Optional[Message]) -> None:
    recv_data = None
    if recv_msg:
        recv_data = pickle.loads(recv_msg.data)
    _log_recv(f"{recv_msg} -> {recv_data}")


class PubSubBackendInterface:
    """Integration test suite for backend_interface objects.

    Only test things that cannot be tested via the Queue class.
    """

    backend = None  # type: Backend
    timeout = 1

    def test_00(self, queue_name: str) -> None:
        """Sanity test."""
        pub = self.backend.create_pub_queue('localhost', queue_name)
        sub = self.backend.create_sub_queue('localhost', queue_name)

        # send
        for msg in DATA_LIST:
            raw_data = pickle.dumps(msg, protocol=4)
            pub.send_message(raw_data)
            _log_send(msg)

        # receive
        for i in itertools.count():
            logging.info(i)
            assert i <= len(DATA_LIST)
            recv_msg = sub.get_message()
            _log_recv_message(recv_msg)

            # check received message
            if i == len(DATA_LIST):
                assert not recv_msg  # None signifies end of stream
                break
            assert recv_msg
            assert DATA_LIST[i] == pickle.loads(recv_msg.data)

    def test_10(self, queue_name: str) -> None:
        """Test nacking, front-loaded sending.

        Order is not guaranteed on redelivery.
        """
        pub = self.backend.create_pub_queue('localhost', queue_name)
        sub = self.backend.create_sub_queue('localhost', queue_name)

        # send
        for msg in DATA_LIST:
            raw_data = pickle.dumps(msg, protocol=4)
            pub.send_message(raw_data)
            _log_send(msg)

        # receive -- nack each message, once, and anticipate its redelivery
        nacked_msgs = []  # type: List[Message]
        redelivered_msgs = []  # type: List[Message]
        for i in itertools.count():
            logging.info(i)
            # all messages have been acked and redelivered
            if len(redelivered_msgs) == len(DATA_LIST):
                redelivered_data = [pickle.loads(m.data) for m in redelivered_msgs]
                assert all((d in DATA_LIST) for d in redelivered_data)
                break

            recv_msg = sub.get_message()
            _log_recv_message(recv_msg)

            if not recv_msg:
                logging.info('waiting...')
                continue
            assert pickle.loads(recv_msg.data) in DATA_LIST

            # message was redelivered
            if recv_msg in nacked_msgs:
                logging.info('REDELIVERED!')
                nacked_msgs.remove(recv_msg)
                redelivered_msgs.append(recv_msg)
                continue
            # nack message
            nacked_msgs.append(recv_msg)
            sub.reject_message(recv_msg.msg_id)
            logging.info('NACK!')

    def test_11(self, queue_name: str) -> None:
        """Test nacking, mixed sending and receiving.

        Order is not guaranteed on redelivery.
        """
        pub = self.backend.create_pub_queue('localhost', queue_name)
        sub = self.backend.create_sub_queue('localhost', queue_name)

        data_to_send = copy.deepcopy(DATA_LIST)
        nacked_msgs = []  # type: List[Message]
        redelivered_msgs = []  # type: List[Message]
        for i in itertools.count():
            logging.info(i)
            # all messages have been acked and redelivered
            if len(redelivered_msgs) == len(DATA_LIST):
                redelivered_data = [pickle.loads(m.data) for m in redelivered_msgs]
                assert all((d in DATA_LIST) for d in redelivered_data)
                break

            # send a message
            if data_to_send:
                msg = data_to_send[0]
                raw_data = pickle.dumps(msg, protocol=4)
                pub.send_message(raw_data)
                _log_send(msg)
                data_to_send.remove(msg)

            # get a message
            recv_msg = sub.get_message()
            _log_recv_message(recv_msg)

            if not recv_msg:
                logging.info('waiting...')
                continue
            assert pickle.loads(recv_msg.data) in DATA_LIST

            # message was redelivered
            if recv_msg in nacked_msgs:
                logging.info('REDELIVERED!')
                nacked_msgs.remove(recv_msg)
                redelivered_msgs.append(recv_msg)
                continue
            # nack message
            nacked_msgs.append(recv_msg)
            sub.reject_message(recv_msg.msg_id)
            logging.info('NACK!')

    def test_20(self, queue_name: str) -> None:
        """Sanity test message generator."""
        pub = self.backend.create_pub_queue('localhost', queue_name)
        sub = self.backend.create_sub_queue('localhost', queue_name)

        # send
        for msg in DATA_LIST:
            raw_data = pickle.dumps(msg, protocol=4)
            pub.send_message(raw_data)
            _log_send(msg)

        # receive
        last = 0
        for i, recv_msg in enumerate(sub.message_generator(timeout=self.timeout)):
            logging.info(i)
            _log_recv_message(recv_msg)
            assert recv_msg
            assert pickle.loads(recv_msg.data) in DATA_LIST
            last = i

        assert last == len(DATA_LIST) - 1

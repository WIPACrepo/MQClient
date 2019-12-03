import logging
import typing

import pika  # type: ignore

from ..backend_interface import RawQueue, MessageID, Message

# Private Classes

class RabbitMQ(RawQueue):
    def __init__(self, address: str, queue: str) -> None:
        self.address = address
        self.queue = queue
        self.connection = None
        self.channel = None
        self.consumer_id = None
        self.prefetch = 1

    def connect(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.address))
        self.channel = self.connection.channel()

    def close(self):
        if self.connection and (not self.connection.is_closed) and (not self.connection.is_closing):
            self.connection.close()

class RabbitMQPub(RabbitMQ):
    def connect(self):
        super(RabbitMQPub, self).connect()
        # Turn on delivery confirmations
        self.channel.queue_declare(queue=self.queue, durable=False)
        self.channel.confirm_delivery()

class RabbitMQSub(RabbitMQ):
    def __init__(self, *args, **kwargs) -> None:
        super(RabbitMQSub, self).__init__(*args, **kwargs)
        self.consumer_id = None
        self.prefetch = 1

    def connect(self):
        super(RabbitMQSub, self).connect()
        self.channel.basic_qos(prefetch_count=self.prefetch, global_qos=True)

# Interface Methods

def create_pub_queue(address: str, name: str) -> RabbitMQPub:
    """
    Create a publishing queue

    Args:
        address (str): address of queue
        name (str): name of queue on address

    Returns:
        RawQueue: queue
    """
    q = RabbitMQPub(address, name)
    q.connect()
    return q

def create_sub_queue(address: str, name: str, prefetch: int = 1) -> RabbitMQSub:
    """Create a subscription queue

    Args:
        address (str): address of queue
        name (str): name of queue on address

    Returns:
        RawQueue: queue
    """
    q = RabbitMQSub(address, name)
    q.prefetch = prefetch
    q.connect()
    return q

def send_message(queue: RabbitMQPub, msg: bytes) -> None:
    """
    Send a message on a queue

    Args:
        address (str): address of queue
        name (str): name of queue on address

    Returns:
        RawQueue: queue
    """
    if not queue.channel:
        raise RuntimeError("queue is not connected")
    queue.channel.basic_publish(exchange='',
                                routing_key=queue.queue,
                                body=msg)

def get_message(queue: RabbitMQSub) -> typing.Optional[Message]:
    """Get a message from a queue"""
    if not queue.channel:
        raise RuntimeError("queue is not connected")
    method_frame, header_frame, body = queue.channel.basic_get(queue.queue)
    if method_frame:
        return Message(method_frame.delivery_tag, body)

def ack_message(queue: RabbitMQSub, msg_id: MessageID) -> None:
    """
    Ack a message from the queue.

    Note that RabbitMQ acks messages in-order, so acking message
    3 of 3 in-progress messages will ack them all.

    Args:
        queue (RabbitMQSub): queue object
        msg_id (MessageID): message id
    """
    if not queue.channel:
        raise RuntimeError("queue is not connected")
    queue.channel.basic_ack(msg_id)

def message_generator(queue: RabbitMQSub, timeout: int, auto_ack: bool = True,
                      propagate_error: bool = True) -> typing.Generator[Message, None, None]:
    """
    A generator yielding a Message.

    Args:
        queue (RabbitMQSub): queue object
        timeout (int): timeout in seconds for inactivity
        auto_ack (bool): Ack each message after successful processing
        propagate_error (bool): should errors from downstream code kill the generator?
    """
    if not queue.channel:
        raise RuntimeError("queue is not connected")
    try:
        for method_frame, header_frame, body in queue.channel.consume(queue.queue, inactivity_timeout=timeout):
            if not method_frame:
                break # out of messages
            try:
                yield Message(method_frame.delivery_tag, body)
            except Exception as e:
                queue.channel.basic_nack(method_frame.delivery_tag)
                if propagate_error:
                    raise
                else:
                    logging.warn('error downstream: %r', e, exc_info=True)
            else:
                if auto_ack:
                    queue.channel.basic_ack(method_frame.delivery_tag)
    finally:
        queue.channel.cancel()

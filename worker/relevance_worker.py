import json
import logging

import pika
from pydantic import ValidationError

from core.config import settings
from worker.schema.job import RelevanceJob

RELEVANCE_QUEUE = "agent:relevance"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

logger = logging.getLogger(__name__)

_graph = None  # ponytail: singleton, graph compile once


def get_graph():
    global _graph
    if _graph is None:
        from relevance.graph import build_relevance_graph

        _graph = build_relevance_graph()
    return _graph


def connect_rabbitmq() -> pika.BlockingConnection:
    url = settings.rabbitmq_url
    sep = "&" if "?" in url else "?"
    if "heartbeat" not in url:
        url = f"{url}{sep}heartbeat=600&blocked_connection_timeout=600"
    parameters = pika.URLParameters(url)
    parameters.heartbeat = 600
    parameters.blocked_connection_timeout = 600
    return pika.BlockingConnection(parameters)


def _safe_ack_nack(ch, method, ack: bool):
    try:
        if ch.is_open:
            if ack:
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            logger.warning("Channel closed, skip %s delivery_tag=%s", "ack" if ack else "nack", method.delivery_tag)
    except Exception as e:
        logger.warning("Ack/nack failed (connection lost) delivery_tag=%s error=%s", method.delivery_tag, e)


def handle_message(ch, method, properties, body):
    logger.info("Received raw body=%r", body)
    try:
        payload = json.loads(body)
        job = RelevanceJob.model_validate(payload)  # base fields gate here; missing -> nack
        state = {
            "payload_type": job.payload_type.value,
            "reference_no": job.reference_no,
            "company": job.company.value,
            "extra": job.model_extra or {},
        }
        logger.info("Validated job reference_no=%s company=%s payload_type=%s", job.reference_no, job.company, job.payload_type)
        graph = get_graph()
        result = graph.invoke(state)
        if result.get("status") == "failed":
            logger.error("Relevance job failed ref=%s error=%s", job.reference_no, result.get("error"))
            _safe_ack_nack(ch, method, ack=False)
            return
        logger.info("Relevance done ref=%s type=%s", job.reference_no, job.payload_type)
        _safe_ack_nack(ch, method, ack=True)
    except ValidationError as e:
        logger.error("Validation failed body=%r errors=%s", body, e.errors())
        _safe_ack_nack(ch, method, ack=False)
    except Exception:
        logger.exception("Failed to process job body=%r", body)
        _safe_ack_nack(ch, method, ack=False)


def main():
    connection = connect_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue=RELEVANCE_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RELEVANCE_QUEUE, on_message_callback=handle_message)
    logger.info("Connected to RabbitMQ")
    logger.info("Waititing for jobs on: %s", RELEVANCE_QUEUE)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Stopping worker...")
        try:
            channel.stop_consuming()
        except Exception:
            pass
    finally:
        try:
            if connection.is_open:
                connection.close()
        except Exception as e:
            logger.warning("Connection close failed (already closed): %s", e)


if __name__ == "__main__":
    main()
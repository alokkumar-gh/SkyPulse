import json
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Awaitable
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger("skypulse.kafka_bus")

TOPIC_RAW = "skypulse.raw"
TOPIC_NORMALIZED = "skypulse.normalized"
TOPIC_PENDING_AI = "skypulse.pending_ai"
TOPIC_AI_PROCESSED = "skypulse.ai_processed"
TOPIC_VERIFICATION_UPDATES = "skypulse.verification_updates"
TOPIC_ANOMALIES = "skypulse.anomalies"
TOPIC_EVENTS = "skypulse.events"
TOPIC_PROPAGATION = "skypulse.propagation"
TOPIC_FAILED = "skypulse.failed"
TOPIC_DEAD_LETTER = "skypulse.dead-letter"


def _json_serializer(obj: Any) -> bytes:
    if isinstance(obj, BaseModel):
        return obj.model_dump_json().encode("utf-8")
    if isinstance(obj, datetime):
        return obj.isoformat().encode("utf-8")
    return json.dumps(obj, default=str).encode("utf-8")


class KafkaBusProducer:
    """
    Kafka / Redpanda message producer with automatic retries and in-memory fallback
    when the broker is offline.
    """

    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS
        self._producer = None
        self._is_connected = False
        self._fallback_queues: Dict[str, asyncio.Queue] = {}

    @property
    def is_live(self) -> bool:
        return self._is_connected

    @property
    def fallback_queues(self) -> Dict[str, asyncio.Queue]:
        return self._fallback_queues

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=_json_serializer,
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                request_timeout_ms=3000,
                retry_backoff_ms=200,
            )
            await asyncio.wait_for(self._producer.start(), timeout=3.0)
            self._is_connected = True
            logger.info("KafkaBusProducer connected to %s", self.bootstrap_servers)
        except Exception as e:
            logger.info("Kafka/Redpanda broker unavailable (%s). Using in-memory bus.", e)
            self._producer = None
            self._is_connected = False

    async def stop(self) -> None:
        if self._producer and self._is_connected:
            try:
                await self._producer.stop()
            except Exception as e:
                logger.warning("Error stopping Kafka producer: %s", e)
        self._is_connected = False

    async def publish(
        self,
        topic: str,
        message: Any,
        key: Optional[str] = None,
        retries: int = 3,
    ) -> bool:
        """Publish a message to Kafka, routing to in-memory queue if broker unavailable."""
        payload = message.model_dump() if isinstance(message, BaseModel) else message

        if self._producer and self._is_connected:
            for attempt in range(retries):
                try:
                    await self._producer.send_and_wait(topic, value=payload, key=key)
                    return True
                except Exception as e:
                    logger.warning("Kafka publish attempt %d failed: %s", attempt + 1, e)
                    await asyncio.sleep(0.1 * (2 ** attempt))

        # In-memory queue fallback
        if topic not in self._fallback_queues:
            self._fallback_queues[topic] = asyncio.Queue(maxsize=5000)

        try:
            if self._fallback_queues[topic].full():
                self._fallback_queues[topic].get_nowait()
            await self._fallback_queues[topic].put((key, payload))
            return True
        except Exception as e:
            logger.error("Failed to enqueue fallback message on topic %s: %s", topic, e)
            return False

    def get_fallback_queue(self, topic: str) -> asyncio.Queue:
        if topic not in self._fallback_queues:
            self._fallback_queues[topic] = asyncio.Queue(maxsize=5000)
        return self._fallback_queues[topic]


class KafkaBusConsumer:
    """
    Kafka / Redpanda message consumer with consumer group coordination,
    retry limits, and dead-letter routing.
    """

    def __init__(
        self,
        topic: str,
        group_id: str,
        bootstrap_servers: Optional[str] = None,
        dead_letter_topic: str = TOPIC_DEAD_LETTER,
        max_retries: int = 3,
        producer: Optional[KafkaBusProducer] = None,
    ):
        self.topic = topic
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS
        self.dead_letter_topic = dead_letter_topic
        self.max_retries = max_retries
        self.producer = producer or kafka_producer
        self._consumer = None
        self._is_connected = False
        self._is_running = False

    @property
    def is_live(self) -> bool:
        return self._is_connected

    async def start(self) -> None:
        self._is_running = True
        try:
            from aiokafka import AIOKafkaConsumer
            self._consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                request_timeout_ms=3000,
            )
            await asyncio.wait_for(self._consumer.start(), timeout=3.0)
            self._is_connected = True
            logger.info("KafkaBusConsumer joined group '%s' for topic '%s'", self.group_id, self.topic)
        except Exception as e:
            logger.info("Kafka consumer unavailable (%s). Falling back to in-memory subscriber.", e)
            self._consumer = None
            self._is_connected = False

    async def stop(self) -> None:
        self._is_running = False
        if self._consumer and self._is_connected:
            try:
                await self._consumer.stop()
            except Exception as e:
                logger.warning("Error stopping consumer: %s", e)
        self._is_connected = False

    async def consume_one(
        self,
        handler: Callable[[Dict[str, Any]], Awaitable[None]],
        timeout_seconds: float = 1.0,
    ) -> bool:
        """Consume one message, invoke handler, route to dead-letter on persistent failure."""
        if self._consumer and self._is_connected:
            try:
                msg = await asyncio.wait_for(self._consumer.getone(), timeout=timeout_seconds)
                await self._process_with_retries(msg.value, handler)
                return True
            except asyncio.TimeoutError:
                return False
            except Exception as e:
                logger.error("Consumer loop error: %s", e)
                return False

        # In-memory queue fallback
        q = self.producer.get_fallback_queue(self.topic)
        try:
            key, payload = await asyncio.wait_for(q.get(), timeout=timeout_seconds)
            await self._process_with_retries(payload, handler)
            q.task_done()
            return True
        except asyncio.TimeoutError:
            return False

    async def _process_with_retries(
        self,
        payload: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        retries = 0
        while retries < self.max_retries:
            try:
                await handler(payload)
                return
            except Exception as exc:
                retries += 1
                logger.warning("Handler failed (attempt %d/%d): %s", retries, self.max_retries, exc)
                if retries < self.max_retries:
                    await asyncio.sleep(0.1 * (2 ** retries))
                else:
                    # Exceeded retries -> route to Dead Letter Queue
                    logger.error("Routing failed message to dead-letter queue '%s'", self.dead_letter_topic)
                    dead_letter_payload = {
                        "failed_topic": self.topic,
                        "group_id": self.group_id,
                        "error": str(exc),
                        "failed_at": datetime.now().isoformat(),
                        "original_payload": payload,
                    }
                    await self.producer.publish(self.dead_letter_topic, dead_letter_payload)


kafka_producer = KafkaBusProducer()

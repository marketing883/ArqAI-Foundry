"""
Message Bus for Agent-to-Agent Communication

Provides:
- Pub/Sub messaging
- Request/Response patterns
- Broadcast capabilities
- Message persistence and retry
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

import structlog

from arqai_foundry.core.enums import MessagePriority
from arqai_foundry.core.exceptions import AgentCommunicationError
from arqai_foundry.core.models import AgentMessage

logger = structlog.get_logger(__name__)

# Type alias for message handlers
MessageHandler = Callable[[AgentMessage], Coroutine[Any, Any, Any]]


class MessageBus:
    """
    Message bus for agent-to-agent communication.

    Supports:
    - Topic-based pub/sub
    - Direct agent-to-agent messaging
    - Request/Response patterns
    - Broadcast to all agents in a workflow
    - Message acknowledgment
    - Dead letter queue for failed messages
    """

    def __init__(self):
        # Topic subscriptions: topic -> list of (agent_id, handler)
        self._subscriptions: dict[str, list[tuple[UUID, MessageHandler]]] = defaultdict(list)

        # Direct agent handlers: agent_id -> handler
        self._agent_handlers: dict[UUID, MessageHandler] = {}

        # Message queues: agent_id -> list of messages
        self._queues: dict[UUID, list[AgentMessage]] = defaultdict(list)

        # Pending responses: correlation_id -> Future
        self._pending_responses: dict[UUID, asyncio.Future] = {}

        # Message history (for debugging)
        self._message_history: list[AgentMessage] = []

        # Dead letter queue
        self._dead_letters: list[tuple[AgentMessage, str]] = []

    async def subscribe(
        self,
        agent_id: UUID,
        topic: str,
        handler: MessageHandler,
    ) -> None:
        """Subscribe an agent to a topic."""
        self._subscriptions[topic].append((agent_id, handler))
        logger.debug(
            "agent_subscribed",
            agent_id=str(agent_id),
            topic=topic,
        )

    async def unsubscribe(
        self,
        agent_id: UUID,
        topic: str,
    ) -> None:
        """Unsubscribe an agent from a topic."""
        self._subscriptions[topic] = [
            (aid, handler)
            for aid, handler in self._subscriptions[topic]
            if aid != agent_id
        ]
        logger.debug(
            "agent_unsubscribed",
            agent_id=str(agent_id),
            topic=topic,
        )

    async def register_agent(
        self,
        agent_id: UUID,
        handler: MessageHandler,
    ) -> None:
        """Register an agent's message handler for direct messages."""
        self._agent_handlers[agent_id] = handler
        logger.debug(
            "agent_registered",
            agent_id=str(agent_id),
        )

    async def unregister_agent(self, agent_id: UUID) -> None:
        """Unregister an agent."""
        self._agent_handlers.pop(agent_id, None)

        # Unsubscribe from all topics
        for topic in self._subscriptions:
            self._subscriptions[topic] = [
                (aid, handler)
                for aid, handler in self._subscriptions[topic]
                if aid != agent_id
            ]

        logger.debug(
            "agent_unregistered",
            agent_id=str(agent_id),
        )

    async def publish(
        self,
        from_agent_id: UUID,
        topic: str,
        message_type: str,
        payload: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: UUID | None = None,
    ) -> AgentMessage:
        """
        Publish a message to a topic.

        All subscribers to the topic will receive the message.
        """
        message = AgentMessage(
            correlation_id=correlation_id or uuid4(),
            from_agent_id=from_agent_id,
            to_agent_id=None,  # Broadcast to topic
            topic=topic,
            message_type=message_type,
            payload=payload,
            priority=priority.value,
        )

        self._message_history.append(message)

        logger.info(
            "message_published",
            message_id=str(message.message_id),
            from_agent=str(from_agent_id),
            topic=topic,
            message_type=message_type,
        )

        # Deliver to all subscribers
        subscribers = self._subscriptions.get(topic, [])
        for agent_id, handler in subscribers:
            if agent_id != from_agent_id:  # Don't send to self
                await self._deliver_message(message, agent_id, handler)

        return message

    async def send(
        self,
        from_agent_id: UUID,
        to_agent_id: UUID,
        message_type: str,
        payload: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: UUID | None = None,
    ) -> AgentMessage:
        """
        Send a direct message to another agent.
        """
        message = AgentMessage(
            correlation_id=correlation_id or uuid4(),
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            topic="direct",
            message_type=message_type,
            payload=payload,
            priority=priority.value,
        )

        self._message_history.append(message)

        logger.info(
            "message_sent",
            message_id=str(message.message_id),
            from_agent=str(from_agent_id),
            to_agent=str(to_agent_id),
            message_type=message_type,
        )

        # Deliver to target agent
        handler = self._agent_handlers.get(to_agent_id)
        if handler:
            await self._deliver_message(message, to_agent_id, handler)
        else:
            # Queue for later delivery
            self._queues[to_agent_id].append(message)
            logger.warning(
                "message_queued",
                message_id=str(message.message_id),
                to_agent=str(to_agent_id),
                reason="agent_not_registered",
            )

        return message

    async def request(
        self,
        from_agent_id: UUID,
        to_agent_id: UUID,
        message_type: str,
        payload: dict[str, Any],
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        """
        Send a request and wait for response.

        Uses correlation_id to match request/response.
        """
        correlation_id = uuid4()

        # Create future for response
        response_future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_responses[correlation_id] = response_future

        try:
            # Send request
            await self.send(
                from_agent_id=from_agent_id,
                to_agent_id=to_agent_id,
                message_type=message_type,
                payload=payload,
                priority=MessagePriority.HIGH,
                correlation_id=correlation_id,
            )

            # Wait for response
            response = await asyncio.wait_for(response_future, timeout=timeout_seconds)
            return response

        except asyncio.TimeoutError:
            logger.warning(
                "request_timeout",
                correlation_id=str(correlation_id),
                from_agent=str(from_agent_id),
                to_agent=str(to_agent_id),
            )
            raise AgentCommunicationError(
                f"Request timeout waiting for response from {to_agent_id}",
                details={"correlation_id": str(correlation_id)},
            )
        finally:
            self._pending_responses.pop(correlation_id, None)

    async def respond(
        self,
        to_message: AgentMessage,
        payload: dict[str, Any],
    ) -> AgentMessage:
        """
        Send a response to a request message.
        """
        response = await self.send(
            from_agent_id=to_message.to_agent_id or uuid4(),
            to_agent_id=to_message.from_agent_id,
            message_type=f"{to_message.message_type}_response",
            payload=payload,
            correlation_id=to_message.correlation_id,
        )

        # Resolve pending future if exists
        future = self._pending_responses.get(to_message.correlation_id)
        if future and not future.done():
            future.set_result(payload)

        return response

    async def broadcast(
        self,
        from_agent_id: UUID,
        workflow_id: UUID,
        message_type: str,
        payload: dict[str, Any],
    ) -> AgentMessage:
        """
        Broadcast a message to all agents in a workflow.
        """
        topic = f"workflow:{workflow_id}"
        return await self.publish(
            from_agent_id=from_agent_id,
            topic=topic,
            message_type=message_type,
            payload=payload,
            priority=MessagePriority.HIGH,
        )

    async def _deliver_message(
        self,
        message: AgentMessage,
        agent_id: UUID,
        handler: MessageHandler,
    ) -> None:
        """Deliver a message to an agent's handler."""
        try:
            await handler(message)
            message.acknowledged_at = datetime.utcnow()
            logger.debug(
                "message_delivered",
                message_id=str(message.message_id),
                to_agent=str(agent_id),
            )
        except Exception as e:
            logger.error(
                "message_delivery_failed",
                message_id=str(message.message_id),
                to_agent=str(agent_id),
                error=str(e),
            )
            self._dead_letters.append((message, str(e)))

    async def acknowledge(self, message_id: UUID) -> None:
        """Acknowledge receipt of a message."""
        for msg in self._message_history:
            if msg.message_id == message_id:
                msg.acknowledged_at = datetime.utcnow()
                break

    async def get_queued_messages(
        self,
        agent_id: UUID,
    ) -> list[AgentMessage]:
        """Get queued messages for an agent."""
        messages = self._queues.pop(agent_id, [])
        return messages

    async def get_dead_letters(self) -> list[tuple[AgentMessage, str]]:
        """Get messages that failed delivery."""
        return self._dead_letters.copy()

    async def retry_dead_letters(self) -> int:
        """Retry all dead letter messages."""
        retried = 0
        dead_letters = self._dead_letters.copy()
        self._dead_letters.clear()

        for message, _ in dead_letters:
            if message.to_agent_id:
                handler = self._agent_handlers.get(message.to_agent_id)
                if handler:
                    await self._deliver_message(message, message.to_agent_id, handler)
                    retried += 1
                else:
                    self._dead_letters.append((message, "agent_still_not_registered"))

        return retried

    def get_stats(self) -> dict[str, Any]:
        """Get message bus statistics."""
        return {
            "total_messages": len(self._message_history),
            "pending_responses": len(self._pending_responses),
            "dead_letters": len(self._dead_letters),
            "registered_agents": len(self._agent_handlers),
            "topics": list(self._subscriptions.keys()),
            "queued_messages": sum(len(q) for q in self._queues.values()),
        }

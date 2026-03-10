"""Communication system - handles target-to-target data exchange."""

import random
from app.utils.constants import ACK_SEQUENCE, SYNC_SEQUENCE
from app.utils.helpers import format_binary_display


class CommunicationSystem:
    def __init__(self):
        self.exchange_log: list = []

    def exchange(self, target_a, target_b, threat, sim_logger):
        """Run one communication exchange tick between the two targets."""
        events = []

        # Randomly pick who initiates this tick
        sender, receiver = (target_a, target_b) if random.random() < 0.5 else (target_b, target_a)

        # Sender generates comm
        seq = sender.generate_comm()
        if seq is None:
            events.append(f"{sender.name} is JAMMED - cannot transmit")
            return events

        events.append(f"{sender.name} TX -> {receiver.name}: {format_binary_display(seq, 'DATA')}")
        sim_logger.log_data_stream(sender.name, receiver.name, "DATA", seq)

        # Threat intercepts (if not jammed)
        threat.intercept(sender.name, seq)
        if not threat.is_jammed:
            events.append(f"{threat.name} INTERCEPTED from {sender.name}: {format_binary_display(seq, 'INTCP')}")
            sim_logger.log_event(threat.name, f"Intercepted {sender.name} data: {seq}")

        # Receiver processes (if not jammed)
        if receiver.is_jammed:
            events.append(f"{receiver.name} is JAMMED - cannot receive")
            return events

        receiver.status = "listening"
        events.append(f"{receiver.name} RX <- {sender.name}: {format_binary_display(seq, 'RECV')}")

        # Send ACK back
        ack = ACK_SEQUENCE
        events.append(f"{receiver.name} TX -> {sender.name}: {format_binary_display(ack, 'ACK')}")
        sim_logger.log_data_stream(receiver.name, sender.name, "ACK", ack)

        # Threat intercepts ACK too
        threat.intercept(receiver.name, ack)

        self.exchange_log.append({
            "sender": sender.name,
            "receiver": receiver.name,
            "data": seq,
            "ack": ack,
        })

        return events

    def clear(self):
        self.exchange_log.clear()

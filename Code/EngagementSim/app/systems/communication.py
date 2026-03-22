"""Communication system - range/frequency-aware target-to-target exchange.

Uses per-asset RF link budgets for range/effectiveness calculations.
Handles SYNC beacon handshakes for targets recovering from jamming.
"""

import random
from itertools import combinations
from app.utils.constants import (
    ACK_SEQUENCE, SYNC_SEQUENCE, RENDEZVOUS_CHANNEL,
    haversine, effectiveness, link_budget_range,
)
from app.utils.helpers import format_binary_display


def _source_rf(asset) -> dict:
    """Extract RF params dict for passing to intercept()."""
    return {
        "tx_power_dbm": asset.tx_power_dbm,
        "antenna_gain_dbi": asset.antenna_gain_dbi,
        "center_freq_mhz": asset.center_freq_mhz,
    }


def _comm_range(sender, receiver) -> float:
    return link_budget_range(
        sender.tx_power_dbm, sender.antenna_gain_dbi,
        receiver.antenna_gain_dbi, receiver.rx_sensitivity_dbm,
        sender.center_freq_mhz)


class CommunicationSystem:
    def __init__(self):
        self.exchange_log: list = []

    def exchange_all(self, targets, threats, sim_logger, state):
        events: list[str] = []
        for ta, tb in combinations(targets, 2):
            if ta.comm_group_seed is None or ta.comm_group_seed != tb.comm_group_seed:
                continue
            resync_evts = self._handle_resync(ta, tb, threats, sim_logger, state)
            if resync_evts is not None:
                events.extend(resync_evts)
                continue
            evts = self._exchange_pair(ta, tb, threats, sim_logger, state)
            events.extend(evts)
        return events

    # ----- SYNC beacon handshake --------------------------------------------
    def _handle_resync(self, ta, tb, threats, sim_logger, state):
        resyncing = None
        peer = None
        if ta.resync_pending:
            resyncing, peer = ta, tb
        elif tb.resync_pending:
            resyncing, peer = tb, ta
        else:
            return None

        events = []
        dist = haversine(resyncing.position, peer.position)
        max_range = _comm_range(resyncing, peer)
        eff = effectiveness(dist, max_range)

        events.append(
            f"{resyncing.name} SYNC beacon on ch{RENDEZVOUS_CHANNEL} "
            f"({resyncing.resync_ticks_remaining} ticks remaining)")
        sim_logger.log_event(
            resyncing.name, f"SYNC beacon on ch{RENDEZVOUS_CHANNEL}")

        for threat in threats:
            intercepted = threat.intercept(
                resyncing.name, SYNC_SEQUENCE, resyncing.position,
                source_rf=_source_rf(resyncing),
                channel=RENDEZVOUS_CHANNEL, tick=state.tick_count)
            if intercepted:
                events.append(
                    f"{threat.name} INTERCEPTED SYNC beacon from {resyncing.name}")

        if peer.is_jammed or peer.resync_pending:
            events.append(
                f"{peer.name} cannot ACK SYNC (jammed or also resyncing)")
            return events

        if eff <= 0:
            events.append(
                f"{peer.name} out of range to ACK SYNC "
                f"(dist={dist:.0f}m, max={max_range:.0f}m)")
            return events

        resyncing.ack_resync()
        events.append(
            f"{peer.name} ACK SYNC -> {resyncing.name}: "
            f"{format_binary_display(ACK_SEQUENCE, 'SYNC-ACK')}")
        sim_logger.log_event(peer.name, f"ACK SYNC to {resyncing.name}")

        for threat in threats:
            threat.intercept(peer.name, ACK_SEQUENCE, peer.position,
                             source_rf=_source_rf(peer),
                             channel=RENDEZVOUS_CHANNEL, tick=state.tick_count)
        return events

    # ----- normal data exchange ---------------------------------------------
    def _exchange_pair(self, target_a, target_b, threats, sim_logger, state):
        events: list[str] = []
        sender, receiver = ((target_a, target_b) if random.random() < 0.5
                            else (target_b, target_a))

        state.tick_comms_total += 1

        if sender.channel != receiver.channel:
            events.append(
                f"{sender.name} TX ch{sender.channel} != "
                f"{receiver.name} ch{receiver.channel} - channel mismatch")
            return events

        seq, ok, corrupted = sender.generate_comm(receiver)
        if not ok:
            if sender.is_jammed:
                events.append(f"{sender.name} is JAMMED - cannot transmit")
            elif sender.resync_pending:
                events.append(f"{sender.name} is RESYNCING - cannot transmit")
            else:
                dist = haversine(sender.position, receiver.position)
                max_range = _comm_range(sender, receiver)
                events.append(
                    f"{sender.name} out of comm range to {receiver.name} "
                    f"(dist={dist:.0f}m, max={max_range:.0f}m)")
            return events

        dist_sr = haversine(sender.position, receiver.position)
        max_range_sr = _comm_range(sender, receiver)
        eff_sr = effectiveness(dist_sr, max_range_sr)
        events.append(
            f"{sender.name} TX -> {receiver.name} ch{sender.channel}: "
            f"{format_binary_display(seq, 'DATA')} "
            f"(range={dist_sr:.0f}m, eff={eff_sr:.0%})")
        sim_logger.log_data_stream(sender.name, receiver.name, "DATA", seq)

        # Threats attempt passive intercept
        for threat in threats:
            intercepted = threat.intercept(
                sender.name, seq, sender.position,
                source_rf=_source_rf(sender),
                channel=sender.channel, tick=state.tick_count)
            if intercepted:
                dist_t = haversine(sender.position, threat.position)
                intcpt_range = threat.intercept_range_to(sender)
                eff_t = effectiveness(dist_t, intcpt_range)
                events.append(
                    f"{threat.name} INTERCEPTED {sender.name} ch{sender.channel}: "
                    f"{format_binary_display(seq, 'INTCP')} "
                    f"(range={dist_t:.0f}m, eff={eff_t:.0%})")
                sim_logger.log_event(
                    threat.name,
                    f"Intercepted {sender.name} ch{sender.channel}: {seq}")

        if receiver.is_jammed:
            events.append(f"{receiver.name} is JAMMED - cannot receive")
            return events

        receiver.status = "listening"
        state.tick_comms_ok += 1

        tag = "RECV*" if corrupted != seq else "RECV"
        events.append(
            f"{receiver.name} RX <- {sender.name}: "
            f"{format_binary_display(corrupted, tag)}"
            + (" (degraded)" if corrupted != seq else ""))

        ack = ACK_SEQUENCE
        events.append(
            f"{receiver.name} TX -> {sender.name}: "
            f"{format_binary_display(ack, 'ACK')}")
        sim_logger.log_data_stream(receiver.name, sender.name, "ACK", ack)

        for threat in threats:
            threat.intercept(receiver.name, ack, receiver.position,
                             source_rf=_source_rf(receiver),
                             channel=receiver.channel, tick=state.tick_count)

        self.exchange_log.append({
            "sender": sender.name, "receiver": receiver.name,
            "channel": sender.channel, "data": seq,
            "corrupted": corrupted, "ack": ack,
            "distance": dist_sr, "effectiveness": eff_sr})
        return events

    def clear(self):
        self.exchange_log.clear()

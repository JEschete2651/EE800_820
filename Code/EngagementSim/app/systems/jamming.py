"""Jamming system - RF link-budget-aware jamming and counter-jamming.

Supports arbitrary numbers of threats and targets.
"""

from app.utils.constants import haversine, link_budget_range
from app.utils.helpers import format_binary_display


class JammingSystem:
    def __init__(self):
        self.jam_log: list = []

    # ----- threat jamming ---------------------------------------------------
    def threat_jam_tick(self, threats, targets, sim_logger, state):
        events: list[str] = []
        for threat in threats:
            if not threat.is_jamming or threat.jam_target_name is None:
                continue
            evts = self._single_threat_jam(threat, targets, sim_logger, state)
            events.extend(evts)
        return events

    def _single_threat_jam(self, threat, targets, sim_logger, state):
        events: list[str] = []

        target = next((t for t in targets if t.name == threat.jam_target_name), None)
        if target is None:
            return events

        state.tick_jam_attempts += 1
        tick = state.tick_count
        jam_range = threat.jam_range_to(target)

        # Must detect first
        if not threat.has_detected(target.name):
            detected = threat.scan_for_target(target, tick=tick)
            dist = haversine(threat.position, target.position)
            if detected:
                events.append(
                    f"{threat.name} DETECTED {target.name} on ch{target.channel} "
                    f"(range={dist:.0f}m)")
                sim_logger.log_event(
                    threat.name,
                    f"Detected {target.name} on channel {target.channel} "
                    f"at range {dist:.0f}m")
                eng = threat.get_inference(target.name)
                if eng:
                    eng.infer()
            else:
                events.append(
                    f"{threat.name} scanning for {target.name}... "
                    f"(range={dist:.0f}m)")
            return events

        # Generate jam
        jam_seq, eff = threat.generate_jam(target, tick=tick)

        if jam_seq is None:
            if threat.is_jammed:
                events.append(f"{threat.name} is JAMMED - cannot jam")
            else:
                dist = haversine(threat.position, target.position)
                events.append(
                    f"{threat.name} out of jam range to {target.name} "
                    f"(dist={dist:.0f}m, max={jam_range:.0f}m)")
            return events

        dist = haversine(threat.position, target.position)

        if eff == 0.0:
            det_ch = threat.get_detected_channel(target.name)
            events.append(
                f"{threat.name} JAM -> {target.name} ch{det_ch}: "
                f"{format_binary_display(jam_seq, 'JAM')} MISS (wrong channel, "
                f"target on ch{target.channel})")
            sim_logger.log_event(
                threat.name,
                f"Jam missed {target.name} - channel mismatch "
                f"(expected ch{det_ch}, actual ch{target.channel})")
            del threat.detected_targets[target.name]
            return events

        events.append(
            f"{threat.name} JAM -> {target.name} ch{target.channel}: "
            f"{format_binary_display(jam_seq, 'JAM')} "
            f"(range={dist:.0f}m, eff={eff:.0%})")
        sim_logger.log_data_stream(threat.name, target.name, "JAM", jam_seq)

        was_cjam = target.is_jamming_threat
        became_jammed = target.receive_jam(eff)

        if became_jammed or target.consecutive_jam_hits > 0:
            state.tick_jam_hits += 1

        if not was_cjam and target.is_jamming_threat:
            events.append(f"{target.name} DETECTED jamming - counter-jam AUTO-ENGAGED")
            sim_logger.log_event(target.name, "Detected jamming - counter-jam auto-engaged")

        if became_jammed:
            events.append(
                f"*** {target.name} is now JAMMED! "
                f"(cooldown: {target.jam_cooldown:.1f}s) ***")
            sim_logger.log_event(
                target.name,
                f"JAMMED by {threat.name} after {target.jam_threshold} hits "
                f"(eff={eff:.0%}, cooldown {target.jam_cooldown:.1f}s)")
        else:
            events.append(
                f"{target.name} jam hits: "
                f"{target.consecutive_jam_hits}/{target.jam_threshold} (eff={eff:.0%})")
            sim_logger.log_event(
                target.name,
                f"Jam hit {target.consecutive_jam_hits}/{target.jam_threshold} "
                f"from {threat.name} (eff={eff:.0%})")

        self.jam_log.append({
            "threat": threat.name, "target": target.name,
            "sequence": jam_seq, "effectiveness": eff, "distance": dist})
        return events

    # ----- target counter-jamming -------------------------------------------
    def target_counter_jam_tick(self, targets, threats, sim_logger, state):
        events: list[str] = []

        for target in targets:
            if not target.is_jamming_threat or target.is_jammed:
                if target.is_jammed and target.is_jamming_threat:
                    events.append(f"{target.name} is JAMMED - cannot counter-jam")
                continue

            for threat in threats:
                if not threat.is_jamming:
                    continue
                state.tick_cjam_attempts += 1
                seq, success, eff = target.attempt_jam_threat(threat)
                dist = haversine(target.position, threat.position)

                if eff <= 0:
                    cjam_range = link_budget_range(
                        target.tx_power_dbm, target.antenna_gain_dbi,
                        threat.antenna_gain_dbi, threat.rx_sensitivity_dbm,
                        target.center_freq_mhz)
                    events.append(
                        f"{target.name} COUNTER-JAM out of range to {threat.name} "
                        f"(dist={dist:.0f}m, max={cjam_range:.0f}m)")
                    continue

                events.append(
                    f"{target.name} COUNTER-JAM -> {threat.name}: "
                    f"{format_binary_display(seq, 'CJAM')} "
                    f"({'HIT' if success else 'MISS'}, eff={eff:.0%})")
                sim_logger.log_data_stream(target.name, threat.name, "CJAM", seq)

                if success:
                    state.tick_cjam_hits += 1
                    became_jammed = threat.receive_jam()
                    if became_jammed:
                        events.append(
                            f"*** {threat.name} is now JAMMED by counter-jam! "
                            f"(cooldown: {threat.jam_cooldown:.1f}s) ***")
                        sim_logger.log_event(
                            threat.name,
                            f"JAMMED by {target.name} counter-jam "
                            f"(cooldown {threat.jam_cooldown:.1f}s)")
                    else:
                        events.append(
                            f"{threat.name} counter-jam hits: "
                            f"{threat.consecutive_jam_hits}/{threat.jam_threshold}")
                        sim_logger.log_event(
                            threat.name,
                            f"Counter-jam hit {threat.consecutive_jam_hits}/{threat.jam_threshold} "
                            f"from {target.name}")

        return events

    def clear(self):
        self.jam_log.clear()

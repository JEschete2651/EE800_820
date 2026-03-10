"""Jamming system - handles threat jamming targets and target counter-jamming."""

from app.utils.helpers import format_binary_display


class JammingSystem:
    def __init__(self):
        self.jam_log: list = []

    def threat_jam_tick(self, threat, targets, sim_logger):
        """Process one tick of threat jamming against targets."""
        events = []

        jam_seq = threat.generate_jam()
        if jam_seq is None:
            if threat.is_jammed:
                events.append(f"{threat.name} is JAMMED - cannot jam")
            return events

        # Threat jams the operator-selected target
        target = next(
            (t for t in targets if t.name == threat.jam_target_name), None
        )
        if target is None:
            return events
        events.append(
            f"{threat.name} JAM -> {target.name}: {format_binary_display(jam_seq, 'JAM')}"
        )
        sim_logger.log_data_stream(threat.name, target.name, "JAM", jam_seq)

        was_counter_jamming = target.is_jamming_threat
        became_jammed = target.receive_jam()
        if not was_counter_jamming and target.is_jamming_threat:
            events.append(
                f"{target.name} DETECTED jamming - counter-jam AUTO-ENGAGED"
            )
            sim_logger.log_event(
                target.name, "Detected jamming - counter-jam auto-engaged"
            )
        if became_jammed:
            events.append(
                f"*** {target.name} is now JAMMED! "
                f"(cooldown: {target.jam_cooldown:.1f}s) ***"
            )
            sim_logger.log_event(
                target.name,
                f"JAMMED by {threat.name} after {target.jam_threshold} hits "
                f"(cooldown {target.jam_cooldown:.1f}s)"
            )
        else:
            hits = target.consecutive_jam_hits
            thresh = target.jam_threshold
            events.append(
                f"{target.name} jam hits: {hits}/{thresh}"
            )
            sim_logger.log_event(
                target.name, f"Jam hit {hits}/{thresh} from {threat.name}"
            )

        self.jam_log.append({"sequence": jam_seq, "targets": [target.name]})
        return events

    def target_counter_jam_tick(self, targets, threat, sim_logger):
        """Process target counter-jamming attempts against the threat."""
        events = []

        for target in targets:
            if not target.is_jamming_threat:
                continue
            if target.is_jammed:
                events.append(f"{target.name} is JAMMED - cannot counter-jam")
                continue

            seq, success = target.attempt_jam_threat()
            events.append(
                f"{target.name} COUNTER-JAM -> {threat.name}: "
                f"{format_binary_display(seq, 'CJAM')} "
                f"({'HIT' if success else 'MISS'})"
            )
            sim_logger.log_data_stream(target.name, threat.name, "CJAM", seq)

            if success:
                became_jammed = threat.receive_jam()
                if became_jammed:
                    events.append(
                        f"*** {threat.name} is now JAMMED by counter-jam! "
                        f"(cooldown: {threat.jam_cooldown:.1f}s) ***"
                    )
                    sim_logger.log_event(
                        threat.name,
                        f"JAMMED by {target.name} counter-jam after "
                        f"{threat.jam_threshold} hits (cooldown {threat.jam_cooldown:.1f}s)"
                    )
                else:
                    hits = threat.consecutive_jam_hits
                    thresh = threat.jam_threshold
                    events.append(f"{threat.name} counter-jam hits: {hits}/{thresh}")
                    sim_logger.log_event(
                        threat.name,
                        f"Counter-jam hit {hits}/{thresh} from {target.name}"
                    )

        return events

    def clear(self):
        self.jam_log.clear()

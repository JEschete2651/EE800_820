"""Tests for the jamming system."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
import time
from app.models.target import Target
from app.models.threat import Threat
from app.utils.constants import haversine

# Two LLA positions ~500m apart
CLOSE_POS_A = (32.9500, -106.0700, 1200.0)
CLOSE_POS_B = (32.9540, -106.0700, 1200.0)  # ~440m north

# Two LLA positions far apart (~14km)
FAR_POS = (33.0800, -106.0700, 1200.0)


class TestTargetJamming(unittest.TestCase):
    def test_jam_threshold_triggers_jammed(self):
        t = Target("Test-Target", position=CLOSE_POS_A)
        t.jam_threshold = 3

        for i in range(2):
            result = t.receive_jam(1.0)
            self.assertFalse(result)
            self.assertFalse(t.is_jammed)

        result = t.receive_jam(1.0)
        self.assertTrue(result)
        self.assertTrue(t.is_jammed)
        self.assertEqual(t.status, "jammed")

    def test_low_effectiveness_may_miss(self):
        hits = 0
        trials = 200
        for _ in range(trials):
            t = Target("Test", position=CLOSE_POS_A)
            t.receive_jam(0.1)
            if t.consecutive_jam_hits > 0:
                hits += 1
        self.assertGreater(hits, 0)
        self.assertLess(hits, trials)

    def test_cooldown_resets_jammed_state(self):
        t = Target("Test", position=CLOSE_POS_A)
        t.jam_threshold = 1
        t.jam_cooldown = 0.1

        t.receive_jam(1.0)
        self.assertTrue(t.is_jammed)

        time.sleep(0.15)
        t.update(time.time(), 1)
        self.assertFalse(t.is_jammed)
        # After recovery, target enters resync state
        self.assertEqual(t.status, "resync")
        self.assertTrue(t.resync_pending)

    def test_resync_completes_after_ack(self):
        t = Target("Test", position=CLOSE_POS_A)
        t.jam_threshold = 1
        t.jam_cooldown = 0.1
        t.receive_jam(1.0)

        time.sleep(0.15)
        t.update(time.time(), 1)
        self.assertTrue(t.resync_pending)

        t.ack_resync()
        t.update(time.time(), 2)
        self.assertFalse(t.resync_pending)
        self.assertEqual(t.status, "active")

    def test_resync_timeout(self):
        from app.utils.constants import RESYNC_TICKS
        t = Target("Test", position=CLOSE_POS_A)
        t.begin_resync()
        self.assertTrue(t.resync_pending)

        for i in range(RESYNC_TICKS + 1):
            t.update(time.time(), i + 1)
        self.assertFalse(t.resync_pending)

    def test_auto_counter_jam_on_first_hit(self):
        t = Target("Test", position=CLOSE_POS_A)
        self.assertFalse(t.is_jamming_threat)
        t.receive_jam(1.0)
        self.assertTrue(t.is_jamming_threat)


class TestThreatJamming(unittest.TestCase):
    def test_threat_must_detect_before_jamming(self):
        threat = Threat("Threat", position=CLOSE_POS_B)
        target = Target("Target", position=CLOSE_POS_A)
        threat.start_jamming(target.name)

        seq, eff = threat.generate_jam(target)
        self.assertIsNone(seq)

    def test_threat_jams_after_detection(self):
        threat = Threat("Threat", position=CLOSE_POS_B)
        target = Target("Target", position=CLOSE_POS_A)
        threat.start_jamming(target.name)
        threat.detected_targets[target.name] = {
            "channel": target.channel, "ticks_ago": 0}

        seq, eff = threat.generate_jam(target)
        self.assertIsNotNone(seq)
        self.assertGreater(eff, 0.0)

    def test_jam_out_of_range_returns_none(self):
        threat = Threat("Threat", position=CLOSE_POS_A)
        target = Target("Target", position=FAR_POS)
        threat.start_jamming(target.name)
        threat.detected_targets[target.name] = {
            "channel": target.channel, "ticks_ago": 0}

        dist = haversine(threat.position, target.position)
        jam_range = threat.jam_range_to(target)
        self.assertGreater(dist, jam_range)

        seq, eff = threat.generate_jam(target)
        self.assertIsNone(seq)

    def test_threat_counter_jam_threshold(self):
        threat = Threat("Threat", position=CLOSE_POS_B)
        threat.jam_threshold = 3

        for _ in range(2):
            self.assertFalse(threat.receive_jam())
        self.assertTrue(threat.receive_jam())
        self.assertTrue(threat.is_jammed)


class TestCounterJamRange(unittest.TestCase):
    def test_counter_jam_success_scales_with_range(self):
        close_hits = 0
        far_hits = 0
        trials = 500

        threat = Threat("Threat", position=CLOSE_POS_B)

        for _ in range(trials):
            t_close = Target("Close", position=CLOSE_POS_A)
            t_close.counter_jam_rate = 1.0
            _, success, _ = t_close.attempt_jam_threat(threat)
            if success:
                close_hits += 1

            t_far = Target("Far", position=FAR_POS)
            t_far.counter_jam_rate = 1.0
            _, success, _ = t_far.attempt_jam_threat(threat)
            if success:
                far_hits += 1

        self.assertGreater(close_hits, far_hits)


class TestHopSequence(unittest.TestCase):
    def test_deterministic_sequence(self):
        t1 = Target("T1", position=CLOSE_POS_A)
        t2 = Target("T2", position=CLOSE_POS_B)
        t1.set_hop_sequence(seed=12345)
        t2.set_hop_sequence(seed=12345)
        self.assertEqual(t1.hop_sequence, t2.hop_sequence)

    def test_different_seeds_differ(self):
        t1 = Target("T1", position=CLOSE_POS_A)
        t2 = Target("T2", position=CLOSE_POS_B)
        t1.set_hop_sequence(seed=111)
        t2.set_hop_sequence(seed=222)
        self.assertNotEqual(t1.hop_sequence, t2.hop_sequence)

    def test_hop_sync_survives_jamming(self):
        """Two targets with the same seed stay on the same channel
        even when one is jammed for several ticks."""
        t1 = Target("T1", position=CLOSE_POS_A)
        t2 = Target("T2", position=CLOSE_POS_B)
        seed = 42
        t1.set_hop_sequence(seed=seed)
        t2.set_hop_sequence(seed=seed)
        t1.hop_interval = 2
        t2.hop_interval = 2

        # Jam t1 for ticks 3-7
        t1.is_jammed = True
        t1.jammed_until = time.time() + 999  # won't expire during test

        for tick in range(1, 8):
            t2.update(time.time(), tick)  # t2 hops normally
            # t1 stays jammed, doesn't update

        # Un-jam t1
        t1.is_jammed = False
        t1.resync_pending = False  # skip resync for this test

        # After unjam, t1 should immediately sync to correct channel
        t1.advance_hop(8)
        t2.advance_hop(8)
        self.assertEqual(t1.channel, t2.channel)

        # Continue for more ticks — they should stay in sync
        for tick in range(9, 20):
            t1.advance_hop(tick)
            t2.advance_hop(tick)
            self.assertEqual(t1.channel, t2.channel,
                             f"Desync at tick {tick}")


if __name__ == "__main__":
    unittest.main()

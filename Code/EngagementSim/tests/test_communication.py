"""Tests for the communication system."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
import tempfile
from app.models.target import Target
from app.models.threat import Threat
from app.models.engagement_state import EngagementState
from app.systems.communication import CommunicationSystem
from app.systems.logger import SimLogger
from app.utils.constants import COMM_RANGE, haversine

# Two positions ~440m apart (within COMM_RANGE=5000m)
CLOSE_A = (32.9500, -106.0700, 1200.0)
CLOSE_B = (32.9540, -106.0700, 1200.0)

# Far position (~14km away)
FAR_POS = (33.0800, -106.0700, 1200.0)


class TestCommunication(unittest.TestCase):
    def setUp(self):
        self.log_dir = tempfile.mkdtemp()
        self.logger = SimLogger(self.log_dir)
        self.comm = CommunicationSystem()
        self.state = EngagementState()

    def tearDown(self):
        self.logger.shutdown()

    def test_comms_within_range_succeed(self):
        ta, tb = self.state.targets[0], self.state.targets[1]
        ta.position = CLOSE_A
        tb.position = CLOSE_B
        ta.channel = 1
        tb.channel = 1

        dist = haversine(ta.position, tb.position)
        self.assertLess(dist, COMM_RANGE)

        events = self.comm.exchange_all(
            self.state.targets, self.state.threats, self.logger, self.state)
        event_text = " ".join(events)
        self.assertTrue("TX" in event_text)

    def test_comms_out_of_range_fail(self):
        ta, tb = self.state.targets[0], self.state.targets[1]
        ta.position = CLOSE_A
        tb.position = FAR_POS
        ta.channel = 1
        tb.channel = 1

        events = self.comm.exchange_all(
            self.state.targets, self.state.threats, self.logger, self.state)
        event_text = " ".join(events)
        self.assertTrue("out of comm range" in event_text or
                        "channel mismatch" in event_text)

    def test_channel_mismatch_blocks_comms(self):
        ta, tb = self.state.targets[0], self.state.targets[1]
        ta.position = CLOSE_A
        tb.position = CLOSE_B
        ta.channel = 1
        tb.channel = 3

        events = self.comm.exchange_all(
            self.state.targets, self.state.threats, self.logger, self.state)
        event_text = " ".join(events)
        self.assertIn("channel mismatch", event_text)

    def test_jammed_target_cannot_transmit(self):
        ta, tb = self.state.targets[0], self.state.targets[1]
        ta.is_jammed = True
        tb.is_jammed = True
        ta.channel = 1
        tb.channel = 1
        ta.position = CLOSE_A
        tb.position = CLOSE_B

        events = self.comm.exchange_all(
            self.state.targets, self.state.threats, self.logger, self.state)
        event_text = " ".join(events)
        self.assertIn("JAMMED", event_text)


class TestInferenceEngine(unittest.TestCase):
    def test_basic_inference(self):
        from app.models.threat import HopInferenceEngine
        eng = HopInferenceEngine(min_obs_per_slot=2)
        # Simulate observations with hop_interval=1 (each tick = new hop slot)
        # Feed a repeating pattern: [1, 3, 2, 4] with period 4
        pattern = [1, 3, 2, 4]
        for cycle in range(4):
            for i, ch in enumerate(pattern):
                eng.record(cycle * 4 + i, ch)

        result = eng.infer()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 4)
        self.assertEqual(result, pattern)

    def test_prediction_after_inference(self):
        from app.models.threat import HopInferenceEngine
        eng = HopInferenceEngine(min_obs_per_slot=2)
        # With hop_interval=1 (default estimated), each tick is a slot
        pattern = [2, 5, 3]
        for cycle in range(3):
            for i, ch in enumerate(pattern):
                eng.record(cycle * 3 + i, ch)

        eng.infer()
        self.assertIsNotNone(eng.inferred_sequence)
        # Predict future slots
        self.assertEqual(eng.predict_channel(9), 2)
        self.assertEqual(eng.predict_channel(10), 5)
        self.assertEqual(eng.predict_channel(11), 3)

    def test_inference_with_hop_interval(self):
        """Inference engine should estimate the hop interval and produce
        predictions that match the actual pattern."""
        from app.models.threat import HopInferenceEngine
        eng = HopInferenceEngine(min_obs_per_slot=2)
        pattern = [1, 3, 7, 2]
        hop_interval = 3

        for tick in range(len(pattern) * hop_interval * 3):
            slot = tick // hop_interval
            ch = pattern[slot % len(pattern)]
            eng.record(tick, ch)

        result = eng.infer()
        self.assertIsNotNone(result)

        # Predictions should match the actual pattern for future ticks
        for future_tick in range(40, 60):
            expected_ch = pattern[(future_tick // hop_interval) % len(pattern)]
            predicted = eng.predict_channel(future_tick)
            self.assertEqual(predicted, expected_ch,
                             f"Mismatch at tick {future_tick}")


if __name__ == "__main__":
    unittest.main()

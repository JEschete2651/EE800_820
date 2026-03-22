"""Tests for the simulation engine and engagement state."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
import tempfile
from app.models.engagement_state import EngagementState
from app.simulation.engine import SimulationEngine
from app.systems.logger import SimLogger


class TestEngagementState(unittest.TestCase):
    def test_initial_state(self):
        state = EngagementState()
        self.assertFalse(state.running)
        self.assertFalse(state.paused)
        self.assertEqual(state.tick_count, 0)
        self.assertEqual(len(state.targets), 2)
        self.assertEqual(len(state.threats), 1)

    def test_add_remove_assets(self):
        state = EngagementState()
        t = state.add_target("New-Target", (33.0, -106.0, 1200.0))
        self.assertEqual(len(state.targets), 3)
        self.assertEqual(t.name, "New-Target")

        th = state.add_threat("New-Threat", (33.0, -106.1, 1200.0))
        self.assertEqual(len(state.threats), 2)

        state.remove_asset("New-Target")
        self.assertEqual(len(state.targets), 2)
        state.remove_asset("New-Threat")
        self.assertEqual(len(state.threats), 1)

    def test_asset_by_name(self):
        state = EngagementState()
        a = state.asset_by_name("Target-Alpha")
        self.assertIsNotNone(a)
        self.assertEqual(a.asset_type, "target")

    def test_hop_sequence_shared(self):
        state = EngagementState()
        ta, tb = state.targets[0], state.targets[1]
        self.assertEqual(ta.comm_group_seed, tb.comm_group_seed)
        self.assertEqual(ta.hop_sequence, tb.hop_sequence)

    def test_reset_clears_state(self):
        state = EngagementState()
        state.tick_count = 50
        state.running = True
        state.threats[0].is_jamming = True
        state.targets[0].is_jammed = True
        state.comms_success_history = [0.5, 0.6]

        state.reset()
        self.assertEqual(state.tick_count, 0)
        self.assertFalse(state.running)
        self.assertFalse(state.threats[0].is_jamming)
        self.assertFalse(state.targets[0].is_jammed)
        self.assertEqual(len(state.comms_success_history), 0)

    def test_save_load_round_trip(self):
        state = EngagementState()
        state.add_target("Extra", (33.1, -106.2, 1300.0), comm_group_seed=42)

        data = state.to_dict()
        state2 = EngagementState()
        state2.targets.clear()
        state2.threats.clear()
        state2.load_dict(data)

        self.assertEqual(len(state2.targets), 3)
        self.assertEqual(len(state2.threats), 1)
        extra = state2.asset_by_name("Extra")
        self.assertIsNotNone(extra)
        self.assertAlmostEqual(extra.lat, 33.1)


class TestSimulationEngine(unittest.TestCase):
    def setUp(self):
        self.log_dir = tempfile.mkdtemp()
        self.state = EngagementState()
        self.logger = SimLogger(self.log_dir)
        for a in self.state.all_assets:
            self.logger.register_asset(a.name)
        self.engine = SimulationEngine(self.state, self.logger)

    def tearDown(self):
        self.logger.shutdown()

    def test_tick_increments_count(self):
        self.engine.start()
        self.engine.tick()
        self.assertEqual(self.state.tick_count, 1)

    def test_paused_tick_does_nothing(self):
        self.engine.start()
        self.engine.pause()
        self.engine.tick()
        self.assertEqual(self.state.tick_count, 0)

    def test_step_works_while_paused(self):
        self.engine.start()
        self.engine.pause()
        self.engine.step()
        self.assertEqual(self.state.tick_count, 1)
        self.assertTrue(self.state.paused)

    def test_metrics_recorded_per_tick(self):
        self.engine.start()
        self.engine.tick()
        self.assertEqual(len(self.state.comms_success_history), 1)
        self.engine.tick()
        self.assertEqual(len(self.state.comms_success_history), 2)

    def test_event_callback_fires(self):
        received = []
        self.engine.set_event_callback(lambda events: received.extend(events))
        self.engine.start()
        self.engine.tick()
        self.assertTrue(len(received) > 0)
        self.assertIn("Tick 1", received[0])

    def test_frequency_hopping(self):
        ta = self.state.targets[0]
        ta.hop_interval = 2
        self.engine.start()
        channels_seen = set()
        for _ in range(20):
            self.engine.tick()
            channels_seen.add(ta.channel)
        self.assertGreaterEqual(len(channels_seen), 2)


if __name__ == "__main__":
    unittest.main()

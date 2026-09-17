from __future__ import annotations

import unittest

from gonken_agent.readiness import ComponentReadiness, aggregate_components, readiness_document


class ComponentReadinessTests(unittest.TestCase):
    def c(self, name: str, status: str, required: bool = True, **kwargs):
        return ComponentReadiness(name=name, status=status, code=f"{name.upper().replace('.', '_')}_{status}", required=required, **kwargs)

    def test_required_failure_does_not_hide_independent_ready_component(self) -> None:
        components = {
            "voice.runtime": self.c("voice.runtime", "READY"),
            "environment.sensor": self.c("environment.sensor", "FAILED"),
            "environment.actuator": self.c("environment.actuator", "NOT_COMMISSIONED", required=False),
        }
        result = aggregate_components(components)
        self.assertEqual(result["status"], "INSTALLATION_FAILED_REQUIRED_COMPONENT")
        self.assertEqual(result["blocking"], ["environment.sensor"])
        self.assertEqual(components["voice.runtime"].status, "READY")

    def test_optional_degradation_can_complete_selected_profile(self) -> None:
        result = aggregate_components({
            "voice.runtime": self.c("voice.runtime", "READY"),
            "voice.wake_led": self.c("voice.wake_led", "DEGRADED", required=False),
        })
        self.assertTrue(result["complete"])
        self.assertEqual(result["status"], "INSTALLATION_COMPLETE_WITH_OPTIONAL_DEGRADATION")
        self.assertEqual(result["degraded_optional"], ["voice.wake_led"])

    def test_required_not_commissioned_is_distinct_from_failure(self) -> None:
        result = aggregate_components({
            "environment.sensor": self.c("environment.sensor", "READY"),
            "environment.actuator": self.c("environment.actuator", "NOT_COMMISSIONED"),
        })
        self.assertFalse(result["complete"])
        self.assertEqual(result["status"], "INSTALLATION_INCOMPLETE_COMMISSIONING_REQUIRED")
        self.assertEqual(result["commissioning_required"], ["environment.actuator"])

    def test_current_ready_can_retain_historical_failure_without_becoming_failed(self) -> None:
        component = self.c(
            "voice.input_audio", "READY", last_failure_code="AUDIO_CAPTURE_FAILED", recovered=True
        )
        result = aggregate_components({"voice.input_audio": component})
        self.assertTrue(result["complete"])
        self.assertEqual(component.as_dict()["last_failure_code"], "AUDIO_CAPTURE_FAILED")
        self.assertTrue(component.as_dict()["recovered"])

    def test_document_is_versioned_and_never_claims_physical_acceptance(self) -> None:
        doc = readiness_document(
            selected_profile="voice-only",
            components={"voice.runtime": self.c("voice.runtime", "READY")},
            release_commit="a" * 40,
            release_profile="core-pi-trixie-py313",
            observed_epoch=1,
        )
        self.assertEqual(doc["format"], "gonken-component-readiness-v2")
        self.assertFalse(doc["physical_acceptance_claimed"])
        self.assertEqual(doc["aggregate"]["status"], "INSTALLATION_COMPLETE_SELECTED_PROFILE_READY")

    def test_unknown_status_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.c("bad", "PASS")

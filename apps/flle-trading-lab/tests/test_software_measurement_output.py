"""Keep classroom conclusions readable and subordinate to batch validity."""

import contextlib
import copy
import importlib.util
import io
from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("software_measurement.py")
SPEC = importlib.util.spec_from_file_location("software_measurement_output", SCRIPT)
MEASURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEASURE)


def effect(diff, verdict):
    return {
        "left": "DEQUE_CV/dedicated",
        "right": "FIXED_CV/dedicated",
        "difference_ns": diff,
        "ci95": {"low_ns": diff - 100, "high_ns": diff + 100},
        "verdict": verdict,
    }


def render_effect(item, valid=True):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        MEASURE.print_effect("交棒谁更快", item, comparison_valid=valid)
    return output.getvalue()


def summary(verdict, environment_ok=True):
    profiles = []
    for name in ("DEQUE_CV/dedicated", "FIXED_CV/dedicated"):
        item = {
            "profile": name,
            "pooled_manual_samples": 3200,
            "pooled_auto_control_samples": 640,
            "environment_control_rtt_p50": {"p50_ns": 46000},
        }
        for key in (
            "queue_to_send_p99", "manual_order_rtt_p99", "submit_to_final_p99",
            "auto_queue_to_send_p99", "auto_order_rtt_p99", "auto_submit_to_final_p99",
        ):
            item[key] = {"p99_ns": 24000}
        profiles.append(item)
    return {
        "round_count": 16, "stable_rounds": 16,
        "comparison_verdict": verdict, "profiles": profiles,
        "precondition_samples": 1000, "warmup_per_round": 40, "samples_per_round": 400,
        "queue_effect": effect(-2457, "LEFT_LOWER"),
        "total_effect": effect(-3050, "LEFT_LOWER"),
        "environment_control_check": {
            "difference_ns": 669,
            "ci95": {"low_ns": -1403, "high_ns": 120},
            "comparable": environment_ok,
        },
        "treatment_cpu": 2, "control_cpu": 3,
    }


class ClassroomOutputTest(unittest.TestCase):
    def test_left_lower_has_named_direction_and_positive_duration(self):
        text = render_effect(effect(-2457, "LEFT_LOWER"))
        self.assertIn("原来的格子（独占座位） 的 p99 少 2457 ns", text)
        self.assertIn("结论：原来的格子（独占座位） 更快", text)
        self.assertNotIn("-2457", text)

    def test_right_lower_has_named_direction_and_positive_duration(self):
        text = render_effect(effect(12481, "RIGHT_LOWER"))
        self.assertIn("固定格子（独占座位） 的 p99 少 12481 ns", text)
        self.assertIn("结论：固定格子（独占座位） 更快", text)

    def test_small_observed_difference_is_not_declared_a_winner(self):
        item = effect(732, "NO_DETECTED_DIFFERENCE")
        item["ci95"] = {"low_ns": -188, "high_ns": 1503}
        text = render_effect(item)
        self.assertIn("样本读数：固定格子（独占座位） 的 p99 少 732 ns", text)
        self.assertIn("结论：暂时分不出谁更快", text)
        for term in ("可信范围", "置信", "小于 0", "大于 0", "-188", "1503"):
            self.assertNotIn(term, text)

    def test_equal_point_estimates_do_not_select_either_profile(self):
        text = render_effect(effect(0, "NO_DETECTED_DIFFERENCE"))
        self.assertIn("样本读数：两套的 p99 相同", text)
        self.assertIn("结论：暂时分不出谁更快", text)

    def test_rejected_batch_overrides_every_effect_verdict(self):
        for diff, verdict in ((-2457, "LEFT_LOWER"), (12481, "RIGHT_LOWER"),
                              (732, "NO_DETECTED_DIFFERENCE")):
            with self.subTest(verdict=verdict):
                text = render_effect(effect(diff, verdict), valid=False)
                self.assertIn("结论：本批检查未通过，不能判断谁更快", text)
                self.assertNotIn("结论：原来的格子", text)
                self.assertNotIn("结论：固定格子", text)
                self.assertNotIn("结论：暂时分不出", text)

    def test_summary_cannot_overrule_failure_when_auto_is_stable(self):
        cases = (
            ("REJECTED_INCONSISTENT_PAIR_DIRECTION", True),
            ("REJECTED_ENVIRONMENT_CONTROL_DIFFERENCE", False),
            ("REJECTED_MULTIPLE_GATES", False),
        )
        for verdict, environment_ok in cases:
            with self.subTest(verdict=verdict):
                data = summary(verdict, environment_ok)
                original = copy.deepcopy(data)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    MEASURE.print_classroom_summary(
                        data, {}, pair_gate="5/8", spread_gate="n/a", rx_gate="n/a",
                    )
                text = output.getvalue()
                self.assertIn("这一轮能不能用：不能用", text)
                self.assertIn("AUTO 有没有自己乱跳：16/16 轮都稳", text)
                self.assertEqual(text.count("结论：本批检查未通过，不能判断谁更快"), 2)
                status = "通过" if environment_ok else "未通过"
                self.assertIn(f"AUTO 对照检查：{status}", text)
                for term in ("结论：原来的格子", "结论：固定格子", "还能比", "可信范围"):
                    self.assertNotIn(term, text)
                self.assertEqual(data, original, "Formatting must not alter raw statistics")


if __name__ == "__main__":
    unittest.main()

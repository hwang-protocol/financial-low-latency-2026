import contextlib
import importlib.util
import io
import copy
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "tests/format_lanz_result.py"
if not path.is_file():
    path = (
        ROOT.parents[1]
        / "assets/06-arista-time/format_lanz_result.py"
    )
spec = importlib.util.spec_from_file_location("lanz_display", path)
display = importlib.util.module_from_spec(spec)
spec.loader.exec_module(display)


def event(kind, tc, size):
    return {"entry_type": kind, "intf_name": "Ethernet2", "traffic_class": tc, "queue_size": size}


class LanzDisplayTest(unittest.TestCase):
    def test_deploy_copies_formatter_into_isolated_tests(self):
        labctl_path = ROOT / "scripts/labctl.sh"
        if not labctl_path.is_file():
            self.skipTest("labctl.sh 只在交易实验室树内检查拷贝约定")
        labctl = labctl_path.read_text()
        self.assertIn(
            "assets/06-arista-time/format_lanz_result.py",
            labctl,
        )
        self.assertIn("$RUN_DIR/tests/format_lanz_result.py", labctl)

    def test_pair_stays_with_its_queue_and_skips_incomplete_edges(self):
        first = event("START", 1, 84)
        end = event("END", 1, 91)
        events = [event("END", 1, 64), first, event("START", 2, 75),
                  event("UPDATE", 1, 91), end, event("START", 1, 64)]
        self.assertEqual(display.latest_pair(events), (first, end))
        self.assertIsNone(display.latest_pair([event("END", 1, 64)]))

    def test_eos_excerpt_preserves_real_rows_and_keeps_queries_separate(self):
        command = "show queue-monitor length Ethernet 2"
        text = (f"$ {command}\n{command} | no-more\nReport generated at yesterday\n"
                "* Max queue length during period of congestion\n"
                "Type Time Intf Duration Queue\n"
                " E 0:00:01 ago Et2(1) 29 84*\n"
                " S 0:00:02 ago Et2(1) N/A 84\n"
                " E 0:00:03 ago Et2(1) 28 64*\n"
                "$ show queue-monitor streaming clients\nNumber of clients connected : 1\n")
        sections = display.switch_sections(text)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            display.display_section(command, sections[command], 2)
        result = stream.getvalue()
        self.assertIn(" E 0:00:01 ago Et2(1) 29 84*", result)
        self.assertIn(" S 0:00:02 ago Et2(1) N/A 84", result)
        self.assertIn("* Max queue length during period of congestion", result)
        self.assertNotIn("0:00:03", result)
        self.assertNotIn("Report generated", result)
        self.assertNotIn("clients connected", result)
        self.assertIn(f"$ {command}\n", result)

    def sample_and_eos(self):
        events = []
        for kind, stamp in (("START", 178956311872900), ("END", 178956311872902)):
            row = event(kind, 1, 64)
            row.update(timestamp_raw=stamp, timestamp_us=stamp*10, timestamp_tick_us=10)
            events.append(row)
        sample = {"events": events, "counts_by_queue": {
            "Ethernet2/TC1": {"START": 1, "UPDATE": 0, "END": 1}}}
        eos = ("$ show queue-monitor length statistics\nEt2 1 1\n"
               "$ show queue-monitor length Ethernet 2\n"
               "Report generated at 2026-09-16 12:52:04\n"
               " E 0:00:05.52678 ago Et2(1) 28 64* 0\n"
               " S 0:00:05.52681 ago Et2(1) N/A 64 N/A\n")
        return sample, eos

    def test_switch_alignment_and_utc_scale(self):
        sample, eos = self.sample_and_eos()
        result = display.verify_sample(sample, eos)
        self.assertEqual(result["switch_congestions"], 1)
        self.assertEqual(result["retained_records_matched"], 2)
        self.assertEqual(result["latest_end_utc"], "2026-09-16 12:51:58.729020 UTC")
        self.assertEqual(result["latest_eos_duration_us"], 28)

    def test_rejects_wrong_counts_duplicates_order_queue_and_time(self):
        sample, eos = self.sample_and_eos()
        for fault in ("count", "duplicate", "order", "queue", "unit", "scale"):
            with self.subTest(fault=fault):
                bad = copy.deepcopy(sample)
                if fault == "count": bad["counts_by_queue"]["Ethernet2/TC1"]["END"] = 2
                if fault == "duplicate": bad["events"].append(bad["events"][-1])
                if fault == "order": bad["events"].reverse()
                if fault == "queue": bad["events"][-1]["queue_size"] = 65
                if fault == "unit": bad["events"][-1]["timestamp_tick_us"] = 1
                if fault == "scale": bad["events"][-1]["timestamp_us"] //= 10
                with self.assertRaises(ValueError): display.verify_sample(bad, eos)


if __name__ == "__main__":
    unittest.main()

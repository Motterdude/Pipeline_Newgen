from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401
from pipeline_newgen_rev1.config import RuntimeState
from pipeline_newgen_rev1.runtime.runtime_dirs import choose_runtime_dirs


class RuntimeDirsTests(unittest.TestCase):
    def test_choose_runtime_dirs_uses_gui_saved_dirs_when_not_forced(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            raw = root / "raw"
            out_dir = root / "out"
            raw.mkdir(parents=True, exist_ok=True)
            out_dir.mkdir(parents=True, exist_ok=True)
            state = RuntimeState(raw_input_dir=raw, out_dir=out_dir, dirs_configured_in_gui=True)

            def _unexpected_prompt(_input: Path, _output: Path) -> tuple[Path, Path]:
                raise AssertionError("prompt should not be called")

            resolved_input, resolved_out = choose_runtime_dirs(
                initial_input_dir=root / "fallback_raw",
                initial_out_dir=root / "fallback_out",
                runtime_state=state,
                prompt_func=_unexpected_prompt,
                force_prompt=False,
            )

            self.assertEqual(resolved_input, raw.resolve())
            self.assertEqual(resolved_out, out_dir.resolve())

    def test_choose_runtime_dirs_forces_prompt_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fallback_raw = root / "fallback_raw"
            fallback_out = root / "fallback_out"
            fallback_raw.mkdir(parents=True, exist_ok=True)
            fallback_out.mkdir(parents=True, exist_ok=True)
            chosen_raw = root / "chosen_raw"
            chosen_out = root / "chosen_out"
            chosen_raw.mkdir(parents=True, exist_ok=True)
            chosen_out.mkdir(parents=True, exist_ok=True)

            resolved_input, resolved_out = choose_runtime_dirs(
                initial_input_dir=fallback_raw,
                initial_out_dir=fallback_out,
                runtime_state=RuntimeState(dirs_configured_in_gui=True),
                prompt_func=lambda _input, _output: (chosen_raw, chosen_out),
                force_prompt=True,
            )

            self.assertEqual(resolved_input, chosen_raw.resolve())
            self.assertEqual(resolved_out, chosen_out.resolve())


if __name__ == "__main__":
    unittest.main()

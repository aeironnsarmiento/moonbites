from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ENTRYPOINT_SOURCE = (Path(__file__).resolve().parents[1] / "main.py").read_text()


def _run_import(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    return subprocess.run(
        [sys.executable, "-c", "import main; print(main.app)"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_main_entrypoint_imports_app_when_vercel_flattens_backend(tmp_path: Path):
    (tmp_path / "main.py").write_text(ENTRYPOINT_SOURCE)
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("")
    (app_dir / "main.py").write_text("app = 'flattened-app'\n")

    result = _run_import(tmp_path)

    assert result.returncode == 0
    assert result.stdout.strip() == "flattened-app"


def test_main_entrypoint_does_not_mask_dependency_import_errors(tmp_path: Path):
    (tmp_path / "main.py").write_text(ENTRYPOINT_SOURCE)
    backend_app_dir = tmp_path / "backend" / "app"
    backend_app_dir.mkdir(parents=True)
    (tmp_path / "backend" / "__init__.py").write_text("")
    (backend_app_dir / "__init__.py").write_text("")
    (backend_app_dir / "main.py").write_text("import missing_dependency\n")
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("")
    (app_dir / "main.py").write_text("app = 'should-not-mask-error'\n")

    result = _run_import(tmp_path)

    assert result.returncode != 0
    assert "missing_dependency" in result.stderr
    assert "should-not-mask-error" not in result.stdout

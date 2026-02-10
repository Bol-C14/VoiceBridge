from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from voicebridge.postprocess.exporter import export_markdown
from voicebridge.storage.session_store import SessionStore


def export_cmd(args: Any) -> int:
    storage_root: Optional[Path] = Path(args.storage).expanduser() if args.storage else None
    store = SessionStore(storage_root)
    paths = store.session_paths(args.session)
    export_path = export_markdown(store, paths)
    print(str(export_path))
    return 0


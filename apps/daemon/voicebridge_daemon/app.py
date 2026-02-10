from __future__ import annotations

import asyncio
import json
import copy
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse

from voicebridge.config import ConfigError, get_profile, load_profiles, load_settings, save_settings
from voicebridge.config.models import ProfileConfig, Settings
from voicebridge.core.events import Event
from voicebridge.core.logging import get_logger, setup_logging
from voicebridge.postprocess.exporter import export_markdown
from voicebridge.runtime.meeting import MeetingSessionRunner
from voicebridge.storage.session_store import SessionStore


log = get_logger("voicebridge.daemon")


class EventBroadcaster:
    def __init__(self):
        self._queues: List["asyncio.Queue[Dict[str, Any]]"] = []
        self._lock = asyncio.Lock()

    async def register(self) -> "asyncio.Queue[Dict[str, Any]]":
        q: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=2000)
        async with self._lock:
            self._queues.append(q)
        return q

    async def unregister(self, q: "asyncio.Queue[Dict[str, Any]]") -> None:
        async with self._lock:
            self._queues = [x for x in self._queues if x is not q]

    def publish_threadsafe(self, loop: asyncio.AbstractEventLoop, event: Event) -> None:
        payload = event.to_dict()

        def _push():
            # best effort: drop if a client is slow
            for q in list(self._queues):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass

        loop.call_soon_threadsafe(_push)


@dataclass
class DaemonState:
    settings: Settings
    profiles: Dict[str, ProfileConfig]
    store: SessionStore
    broadcaster: EventBroadcaster
    runner: Optional[MeetingSessionRunner] = None


def create_app() -> FastAPI:
    setup_logging()

    try:
        settings = load_settings(allow_missing=True)
        profiles = load_profiles(settings=settings)
    except ConfigError as exc:
        # Still start, but with empty profiles.
        log.error("Config error: %s", exc)
        settings = Settings()
        profiles = {}

    store = SessionStore(settings.storage_dir)
    broadcaster = EventBroadcaster()
    state = DaemonState(settings=settings, profiles=profiles, store=store, broadcaster=broadcaster)

    app = FastAPI(title="VoiceBridge Daemon", version="0.1.0")
    ui_path = Path(__file__).resolve().parent / "static" / "index.html"

    @app.get("/")
    def ui() -> HTMLResponse:
        if not ui_path.exists():
            return HTMLResponse("<h1>VoiceBridge daemon</h1><p>UI missing.</p>")
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"ok": True}

    @app.get("/v1/profiles")
    def list_profiles() -> Dict[str, Any]:
        return {"profiles": sorted(state.profiles.keys())}

    @app.get("/v1/settings")
    def get_settings() -> Dict[str, Any]:
        return {"settings": _public_settings_view(state.settings)}

    @app.post("/v1/settings")
    def update_settings(body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update and persist settings. Keys are stored in plaintext in settings.yml.

        Changes apply to new sessions; an active session keeps its existing service bindings.
        """

        allowed = {
            "openai_api_key",
            "openai_base_url",
            "openai_asr_model",
            "openai_model_translate",
            "openai_model_summary",
            "openai_model_explain",
            "translate_enabled",
            "translate_target_language",
            "storage_dir",
            "asr_mode",
            "asr_default_model",
            "asr_compute_type",
            "vad_max_segment_ms",
            "diarization_enabled",
        }
        for k in body.keys():
            if k not in allowed:
                raise HTTPException(status_code=400, detail=f"Unsupported key: {k}")

        # Update in-memory
        if "openai_api_key" in body:
            key = body.get("openai_api_key")
            state.settings.openai_api_key = None if (key is None or str(key).strip() == "") else str(key).strip()
        if "openai_base_url" in body and body.get("openai_base_url") is not None:
            base_url = str(body["openai_base_url"]).strip()
            if not base_url:
                raise HTTPException(status_code=400, detail="openai_base_url cannot be empty")
            state.settings.openai_base_url = base_url
        if "openai_model_translate" in body and body.get("openai_model_translate") is not None:
            model = str(body["openai_model_translate"]).strip()
            if not model:
                raise HTTPException(status_code=400, detail="openai_model_translate cannot be empty")
            state.settings.openai_model_translate = model
        if "openai_model_summary" in body and body.get("openai_model_summary") is not None:
            model = str(body["openai_model_summary"]).strip()
            if not model:
                raise HTTPException(status_code=400, detail="openai_model_summary cannot be empty")
            state.settings.openai_model_summary = model
        if "openai_model_explain" in body and body.get("openai_model_explain") is not None:
            model = str(body["openai_model_explain"]).strip()
            if not model:
                raise HTTPException(status_code=400, detail="openai_model_explain cannot be empty")
            state.settings.openai_model_explain = model
        if "openai_asr_model" in body and body.get("openai_asr_model") is not None:
            model = str(body["openai_asr_model"]).strip()
            if not model:
                raise HTTPException(status_code=400, detail="openai_asr_model cannot be empty")
            state.settings.openai_asr_model = model
        if "translate_enabled" in body:
            state.settings.translate_enabled = bool(body.get("translate_enabled"))
        if "translate_target_language" in body and body.get("translate_target_language") is not None:
            lang = str(body["translate_target_language"]).strip()
            if not lang:
                raise HTTPException(status_code=400, detail="translate_target_language cannot be empty")
            state.settings.translate_target_language = lang
        if "storage_dir" in body:
            sd = body.get("storage_dir")
            state.settings.storage_dir = None if (sd is None or str(sd).strip() == "") else Path(str(sd)).expanduser()
            # Storage dir changes should apply next session; keep current store for now.
        if "asr_mode" in body:
            mode = str(body.get("asr_mode") or "").strip().lower()
            if mode not in ("offline", "online", ""):
                raise HTTPException(status_code=400, detail="asr_mode must be 'offline' or 'online'")
            state.settings.asr_mode = mode or "offline"
        if "asr_default_model" in body and body.get("asr_default_model") is not None:
            model = str(body["asr_default_model"]).strip()
            if not model:
                raise HTTPException(status_code=400, detail="asr_default_model cannot be empty")
            state.settings.asr_default_model = model
        if "asr_compute_type" in body:
            ct = body.get("asr_compute_type")
            state.settings.asr_compute_type = None if (ct is None or str(ct).strip() == "") else str(ct).strip()
        if "vad_max_segment_ms" in body:
            v = body.get("vad_max_segment_ms")
            if v is None or str(v).strip() == "":
                state.settings.vad_max_segment_ms = 10_000
            else:
                try:
                    n = int(v)
                except Exception as exc:
                    raise HTTPException(status_code=400, detail="vad_max_segment_ms must be an integer") from exc
                if n < 500 or n > 60_000:
                    raise HTTPException(status_code=400, detail="vad_max_segment_ms must be between 500 and 60000")
                state.settings.vad_max_segment_ms = n
        if "diarization_enabled" in body:
            state.settings.diarization_enabled = bool(body.get("diarization_enabled"))

        # Persist + reload to normalize types and refresh profiles
        try:
            save_settings(state.settings)
            state.settings = load_settings(allow_missing=True)
            state.profiles = load_profiles(settings=state.settings)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to save settings: {exc}") from exc

        note = None
        if state.runner and state.runner.is_running():
            note = "Settings saved. Changes apply to new sessions (stop/start to take effect)."
        return {"ok": True, "settings": _public_settings_view(state.settings), "note": note}

    @app.post("/v1/sessions/start")
    async def start_session(body: Dict[str, Any]) -> Dict[str, Any]:
        if state.runner and state.runner.is_running():
            raise HTTPException(status_code=409, detail="Session already running")

        profile_name = str(body.get("profile") or "Meeting")
        if profile_name not in state.profiles:
            raise HTTPException(status_code=404, detail=f"Profile not found: {profile_name}")
        profile = copy.deepcopy(get_profile(state.profiles, profile_name))

        # Apply ASR mode
        if state.settings.asr_mode == "online":
            if not state.settings.openai_api_key:
                raise HTTPException(status_code=400, detail="OpenAI key not set (required for online ASR).")
            profile.asr.backend = "openai_realtime"

        # Apply translation defaults
        profile.translate.enabled = bool(state.settings.translate_enabled)
        if state.settings.translate_target_language:
            profile.translate.target_language = str(state.settings.translate_target_language)

        # Allow overrides (device, target_language)
        if body.get("input_device") is not None:
            profile.audio.input_device = str(body["input_device"])
        if body.get("target_language") is not None:
            profile.translate.target_language = str(body["target_language"])

        loop = asyncio.get_running_loop()

        def on_event(ev: Event) -> None:
            state.broadcaster.publish_threadsafe(loop, ev)

        runner = MeetingSessionRunner(profile=profile, settings=state.settings, store=state.store, on_event=on_event)
        session_id = runner.start()
        state.runner = runner
        return {"session_id": session_id}

    @app.post("/v1/sessions/stop")
    def stop_session() -> Dict[str, Any]:
        if not state.runner:
            raise HTTPException(status_code=404, detail="No active session")
        runner = state.runner
        try:
            runner.stop()
        except Exception as exc:
            # Keep daemon usable even if post-processing fails.
            log.exception("Stop session failed: %s", exc)
            sid = runner.session_id
            state.runner = None
            raise HTTPException(status_code=500, detail=f"Stop failed: {exc}") from exc
        sid = runner.session_id
        state.runner = None
        return {"session_id": sid, "stopped": True}

    @app.get("/v1/sessions")
    def list_sessions(limit: int = 50) -> Dict[str, Any]:
        rows = state.store.index.list_sessions(limit=limit)
        return {"sessions": [state.store.index.to_dict(r) for r in rows]}

    @app.post("/v1/sessions/{session_id}/explain")
    def explain(session_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        if not state.runner or state.runner.session_id != session_id:
            raise HTTPException(status_code=404, detail="Session not active in this daemon instance")
        term = str(body.get("term") or "")
        if not term.strip():
            raise HTTPException(status_code=400, detail="Missing term")
        text = state.runner.explain(term)
        return {"term": term, "text": text}

    @app.post("/v1/sessions/{session_id}/export")
    def export(session_id: str) -> Dict[str, Any]:
        row = state.store.index.get_session(session_id)
        if not row:
            raise HTTPException(status_code=404, detail="Unknown session")
        paths = state.store.session_paths(session_id)
        export_path = export_markdown(state.store, paths, title=row.profile)
        return {"path": str(export_path)}

    @app.get("/v1/sessions/{session_id}/export.md")
    def export_md(session_id: str):
        paths = state.store.session_paths(session_id)
        if not paths.export_md.exists():
            raise HTTPException(status_code=404, detail="export.md not found")
        return FileResponse(str(paths.export_md), media_type="text/markdown")

    @app.websocket("/v1/sessions/{session_id}/ws")
    async def ws_session(websocket: WebSocket, session_id: str):
        await websocket.accept()
        q = await state.broadcaster.register()
        try:
            # Replay existing events first (if any)
            paths = state.store.session_paths(session_id)
            if paths.events_jsonl.exists():
                with paths.events_jsonl.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        await websocket.send_text(line)

            # Then live stream
            while True:
                msg = await q.get()
                if msg.get("session_id") != session_id:
                    continue
                await websocket.send_text(json.dumps(msg, ensure_ascii=False))
        except WebSocketDisconnect:
            pass
        finally:
            await state.broadcaster.unregister(q)

    return app


def _public_settings_view(settings: Settings) -> Dict[str, Any]:
    key = settings.openai_api_key or ""
    masked = None
    if key:
        masked = f"***{key[-4:]}" if len(key) >= 4 else "***"
    return {
        "openai_api_key_set": bool(key),
        "openai_api_key_masked": masked,
        "openai_base_url": settings.openai_base_url,
        "openai_asr_model": settings.openai_asr_model,
        "openai_model_translate": settings.openai_model_translate,
        "openai_model_summary": settings.openai_model_summary,
        "openai_model_explain": settings.openai_model_explain,
        "translate_enabled": bool(settings.translate_enabled),
        "translate_target_language": settings.translate_target_language,
        "storage_dir": str(settings.storage_dir) if settings.storage_dir else None,
        "asr_mode": settings.asr_mode,
        "asr_default_model": settings.asr_default_model,
        "asr_compute_type": settings.asr_compute_type,
        "vad_max_segment_ms": int(settings.vad_max_segment_ms),
        "diarization_enabled": bool(settings.diarization_enabled),
    }

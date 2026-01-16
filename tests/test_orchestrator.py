from __future__ import annotations

from core.types import Event, Profile, ReplyStrategy
from orchestrator.orchestrator import Orchestrator
from services import ServiceBundle
from audio_io import AudioIOBundle

from tests.fakes import DummyOutput, DummyStorage, FakeLLM, FakeTTS
from understanding.explain_concept import ExplainConceptEngine
from understanding.coach_engine import CoachEngine
from understanding.summarizer import Summarizer


def _build_profile(capabilities: list[str] | None = None) -> Profile:
    return Profile(
        name="Teaching",
        input_mode="manual",
        tts_backend="openai",
        default_voice="alloy",
        output_device="default",
        default_action="explain_concept",
        capabilities=capabilities or [
            "explain_concept",
            "coach_student",
            "summarize",
            "suggest",
        ],
        reply_strategy=ReplyStrategy(),
        prompts={},
        metadata={},
    )


def test_speak_does_not_add_utterance():
    profile = _build_profile()
    services = ServiceBundle(llm=None, tts=FakeTTS(), asr=None)
    audio_io = AudioIOBundle(output=DummyOutput())
    orchestrator = Orchestrator(
        profile=profile, services=services, audio_io=audio_io, storage=DummyStorage()
    )
    before = len(orchestrator.session.session.utterances)
    orchestrator.speak("hello")
    after = len(orchestrator.session.session.utterances)
    assert before == after


def test_explain_concept_fallback():
    profile = _build_profile()
    llm = FakeLLM(structured_payload={}, complete_text="fallback explanation")
    engine = ExplainConceptEngine(profile, llm)
    payload = engine.explain("pointers")
    assert payload.get("title")
    assert payload.get("one_liner")
    assert payload.get("steps")


def test_coach_fallback():
    profile = _build_profile()
    llm = FakeLLM(structured_payload={}, complete_text="What should this do?")
    engine = CoachEngine(profile, llm)
    class DummySession:
        def get_recent_context(self, max_turns: int = 6):
            _ = max_turns
            return []

    payload = engine.generate_coaching(DummySession(), "student question")
    assert payload.get("questions")


def test_summarize_fallback():
    profile = _build_profile()
    llm = FakeLLM(structured_payload={}, complete_text="summary line")
    engine = Summarizer(profile, llm)

    class DummySession:
        def get_window(self, since_last_summary: bool = True, max_turns: int = 12):
            _ = since_last_summary
            _ = max_turns
            class DummySpeaker:
                role = "local_user"
                display_name = "User"

            class DummyUtterance:
                speaker = DummySpeaker()
                text = "hello"

            return [DummyUtterance()]

        @property
        def profile(self):
            return profile

    summary = engine.summarize(DummySession())
    assert summary.get("summary_markdown")


def test_capability_denies_action():
    profile = _build_profile(capabilities=["suggest"])
    services = ServiceBundle(llm=None, tts=None, asr=None)
    orchestrator = Orchestrator(
        profile=profile, services=services, audio_io=AudioIOBundle(), storage=DummyStorage()
    )
    result = orchestrator.handle_event(Event(action="summarize", source="keyboard"))
    assert result.error


def test_add_utterance_records_remote():
    profile = _build_profile()
    services = ServiceBundle(llm=None, tts=None, asr=None)
    orchestrator = Orchestrator(
        profile=profile, services=services, audio_io=AudioIOBundle(), storage=DummyStorage()
    )
    orchestrator.handle_event(
        Event(
            action="add_utterance",
            payload_text="hello",
            speaker_role="remote_user",
            source="keyboard",
        )
    )
    assert orchestrator.session.session.utterances[-1].speaker.role == "remote_user"

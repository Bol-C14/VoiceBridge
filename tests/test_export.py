from __future__ import annotations

from core.types import Participant, Profile, ReplyStrategy, Suggestion, Utterance
from conversation.session_manager import ConversationSession


def _build_profile() -> Profile:
    return Profile(
        name="Teaching",
        input_mode="manual",
        tts_backend="openai",
        default_voice="alloy",
        output_device="default",
        default_action="explain_concept",
        capabilities=["explain_concept", "coach_student", "summarize", "suggest"],
        reply_strategy=ReplyStrategy(),
        prompts={},
        metadata={},
    )


def test_export_files(tmp_path):
    profile = _build_profile()
    session = ConversationSession(profile)

    speaker = Participant(id="student", role="remote_user", display_name="Student")
    session.add_utterance(Utterance(speaker=speaker, text="What is a pointer?", source="keyboard"))
    session.add_suggestion(Suggestion(text="Let's define it step by step."))

    transcript_path = tmp_path / "transcript.jsonl"
    summary_path = tmp_path / "summary.md"

    session.export_transcript_jsonl(transcript_path)
    session.export_summary_md(
        summary_path,
        {
            "summary": ["Pointer basics"],
            "misconceptions": [],
            "homework": ["Write a small example."],
            "next_session_plan": [],
        },
    )

    assert transcript_path.exists()
    assert summary_path.exists()
    assert transcript_path.stat().st_size > 0
    assert summary_path.stat().st_size > 0

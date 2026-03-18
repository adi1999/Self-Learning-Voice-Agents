"""Per-turn annotation extraction — combines annotations from all judges."""

from core.models import Conversation, TurnAnnotation


def merge_annotations(
    conversation: Conversation,
    quality_annotations: list[TurnAnnotation],
    compliance_annotations: list[TurnAnnotation],
) -> list[TurnAnnotation]:
    """Merge annotations from quality and compliance judges into the conversation turns."""
    all_annotations = quality_annotations + compliance_annotations

    # Also annotate turn objects directly for downstream consumers
    annotations_by_turn: dict[int, list[TurnAnnotation]] = {}
    for ann in all_annotations:
        annotations_by_turn.setdefault(ann.turn_index, []).append(ann)

    for turn in conversation.turns:
        if turn.index in annotations_by_turn:
            turn.annotations.extend(annotations_by_turn[turn.index])

    return all_annotations

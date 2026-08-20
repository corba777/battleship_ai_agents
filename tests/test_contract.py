from __future__ import annotations

import pytest

from salvo.agents.contract import ContractError, parse_action


def test_belief_accepts_one_or_two_entries() -> None:
    one = parse_action(
        '{"shot":"E5","belief":[{"cell":"E5","p":0.9}],"say":"Firing."}'
    )
    assert len(one.belief) == 1
    two = parse_action(
        '{"shot":"E5","belief":[{"cell":"E5","p":0.9},{"cell":"E6","p":0.2}],"say":"Firing."}'
    )
    assert len(two.belief) == 2
    assert two.belief[0].cell == "E5"


def test_belief_rejects_empty_and_more_than_three() -> None:
    with pytest.raises(ContractError, match="1 to 3") as empty:
        parse_action('{"shot":"E5","belief":[],"say":"Firing."}')
    assert empty.value.kind == "schema"
    with pytest.raises(ContractError, match="1 to 3") as extra:
        parse_action(
            '{"shot":"E5","belief":['
            '{"cell":"E5","p":0.9},{"cell":"E6","p":0.3},'
            '{"cell":"E7","p":0.2},{"cell":"E8","p":0.1}'
            '],"say":"Firing."}'
        )
    assert extra.value.kind == "schema"


def test_unparseable_and_transposed_shot_are_rules() -> None:
    with pytest.raises(ContractError, match="unparseable") as blob:
        parse_action("fire the middle somewhere")
    assert blob.value.kind == "rules"
    with pytest.raises(ContractError, match="illegal cell") as transposed:
        parse_action('{"shot":"5E","belief":[{"cell":"E5","p":0.9}],"say":"Firing."}')
    assert transposed.value.kind == "rules"


def test_missing_say_is_schema_even_when_shot_is_legal() -> None:
    with pytest.raises(ContractError, match="missing say") as missing:
        parse_action('{"shot":"E5","belief":[{"cell":"E5","p":0.9}],"say":""}')
    assert missing.value.kind == "schema"


def test_belief_three_still_legal() -> None:
    action = parse_action(
        '{"shot":"E5","belief":['
        '{"cell":"E5","p":0.42},{"cell":"E6","p":0.31},{"cell":"D5","p":0.19}'
        '],"say":"Continuing down."}'
    )
    assert len(action.belief) == 3

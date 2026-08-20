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
    with pytest.raises(ContractError, match="1 to 3"):
        parse_action('{"shot":"E5","belief":[],"say":"Firing."}')
    with pytest.raises(ContractError, match="1 to 3"):
        parse_action(
            '{"shot":"E5","belief":['
            '{"cell":"E5","p":0.9},{"cell":"E6","p":0.3},'
            '{"cell":"E7","p":0.2},{"cell":"E8","p":0.1}'
            '],"say":"Firing."}'
        )


def test_belief_three_still_legal() -> None:
    action = parse_action(
        '{"shot":"E5","belief":['
        '{"cell":"E5","p":0.42},{"cell":"E6","p":0.31},{"cell":"D5","p":0.19}'
        '],"say":"Continuing down."}'
    )
    assert len(action.belief) == 3

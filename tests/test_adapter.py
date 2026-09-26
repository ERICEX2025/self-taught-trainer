import logging
import unittest

from poke_env.battle import Battle
from poke_env.player import Player

from stt.adapter import describe, legal_actions


def request_battle(move_id, condition="100/100", trapped=False):
    battle = Battle("battle-gen1ou-adapter-test", "healer", logging.getLogger(__name__), gen=1)
    battle.parse_request({
        "side": {
            "name": "healer", "id": "p1",
            "pokemon": [
                {"ident": "p1: Alakazam", "details": "Alakazam", "condition": condition,
                 "active": True, "moves": ["psychic", "recover"], "baseAbility": "No Ability", "item": ""},
                {"ident": "p1: Chansey", "details": "Chansey", "condition": "100/100",
                 "active": False, "moves": ["icebeam"], "baseAbility": "No Ability", "item": ""},
            ],
        },
        "active": [{"moves": [{"move": move_id.title(), "id": move_id}], "trapped": trapped}],
    })
    return battle


class DescribeSpecialActionsTests(unittest.TestCase):
    def test_fight_request_has_no_placeholder_attack_stats(self):
        # Fight can also be requested for partial trapping without a major status.
        for condition in ("100/100 slp", "100/100 frz", "100/100"):
            with self.subTest(condition=condition):
                battle = request_battle("fight", condition)
                context = describe(battle)
                line = next(line for line in context.splitlines() if line.startswith("  move:fight "))
                for field in ("type ", "power ", "accuracy ", "physical"):
                    self.assertNotIn(field, line)
                self.assertIn("without selecting an attack", line)
                actions = dict(legal_actions(battle))
                self.assertEqual(list(actions), ["move:fight", "switch:chansey"])
                self.assertIn("  switch:chansey ", context)
                self.assertEqual(Player.create_order(actions["move:fight"]).message, "/choose move fight")

    def test_recharge_request_has_no_placeholder_attack_stats(self):
        battle = request_battle("recharge", trapped=True)
        line = next(line for line in describe(battle).splitlines() if line.startswith("  move:recharge "))
        for field in ("type ", "power ", "accuracy ", "physical"):
            self.assertNotIn(field, line)
        self.assertIn("recharge this turn", line)
        actions = dict(legal_actions(battle))
        self.assertEqual(list(actions), ["move:recharge"])
        self.assertEqual(Player.create_order(actions["move:recharge"]).message, "/choose move 1")

    def test_real_moves_including_struggle_keep_their_stats(self):
        for move_id, stats in (
            ("psychic", "type Psychic, power 90, special, accuracy 1.0"),
            ("recover", "type Normal, power 0, status, accuracy 1.0"),
            ("struggle", "type Normal, power 50, physical, accuracy 1.0"),
        ):
            with self.subTest(move=move_id):
                battle = request_battle(move_id)
                self.assertIn(f"  move:{move_id}  {stats}", describe(battle))
                self.assertEqual(
                    Player.create_order(dict(legal_actions(battle))[f"move:{move_id}"]).message,
                    f"/choose move {move_id}",
                )


if __name__ == "__main__":
    unittest.main()

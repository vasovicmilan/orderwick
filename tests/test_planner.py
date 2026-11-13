import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from orderwick.core.autoplayer import STALL, VisiblePlayer, observe  # noqa: E402
from orderwick.core.board import Board  # noqa: E402
from orderwick.core.generator import BoardGenerator  # noqa: E402
from orderwick.core.levels import LevelCatalog  # noqa: E402
from orderwick.core.planner import HIDDEN, LoopGuard, Observation, choose_move, successors  # noqa: E402
import tune_planner  # noqa: E402


class VisibleOnlyTests(unittest.TestCase):
    def _board(self, level=4, seed=3):
        spec = LevelCatalog.spec(level)
        kinds = BoardGenerator(random.Random(seed)).generate(spec, 0.0, 0.0).kinds
        return Board.from_kinds(kinds, spec.free, spec.k, spec.reveal)

    def test_face_down_cards_are_never_read(self):
        a = self._board()
        b = self._board()
        for col in b.columns:                                  # change every face-down card: the player must not notice
            for card in col:
                if not card.up:
                    card.kind = (card.kind + 1) % 5
        self.assertEqual(observe(a).up, observe(b).up)
        self.assertEqual(observe(a).hidden, observe(b).hidden)
        ma = VisiblePlayer(seed=1).decide(observe(a), False, True)
        mb = VisiblePlayer(seed=1).decide(observe(b), False, True)
        self.assertEqual((ma.kind, ma.src, ma.dst), (mb.kind, mb.src, mb.dst))

    def test_moves_follow_the_rules(self):
        board = self._board()
        obs = observe(board)
        for _nc, _nf, (sk, si, dk, di), _dirty in successors(obs.state(), tuple(obs.free), obs.capacity):
            from orderwick.core.models import Loc
            trial = Board.from_kinds(board.kinds(), board.n_free, board.capacity, 1)
            trial.restore(board.snapshot())
            self.assertTrue(trial.apply_move(Loc(sk, si), Loc(dk, di)).ok, (sk, si, dk, di))

    def test_wins_the_first_levels(self):
        for level in (1, 2, 3):
            ok, *_ = tune_planner.play_board(level, random.Random(level), VisiblePlayer(seed=level), 600)
            self.assertTrue(ok, f"level {level}")


class LoopGuardTests(unittest.TestCase):
    def test_tabu_move_is_not_chosen_again(self):
        board = Board.from_kinds([[0, 1, 0], [1, 0, 1], []], 1, 3, 3)
        obs = observe(board)
        guard = LoopGuard()
        first, _ = choose_move(obs, guard)
        key = __import__("orderwick.core.planner", fromlist=["key_of"]).key_of(obs.state(), tuple(obs.free))
        guard.tabu.add((key, first))
        second, _ = choose_move(obs, guard)
        self.assertNotEqual(first, second)

    def test_a_circle_ends_with_undo_then_rescue(self):
        player = VisiblePlayer(seed=1)
        obs = Observation([0, 0], [[0, 1], [1, 0]], [None], 3)
        kinds = []
        for _ in range(STALL + 6):
            act = player.decide(obs, True, True)
            kinds.append(act.kind)
            if act.kind != "move":
                break
            player.last = "move"
        self.assertIn(kinds[-1], ("undo", "rescue"))

    def test_hidden_marker_is_not_a_kind(self):
        self.assertLess(HIDDEN, 0)


if __name__ == "__main__":
    unittest.main()

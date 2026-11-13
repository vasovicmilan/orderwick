"""Logic tests (no pygame):  python -m unittest discover -s tests -v"""
import random
import tempfile
import unittest
from pathlib import Path

from orderwick.core.board import Board
from orderwick.core.generator import BoardGenerator
from orderwick.core.levels import CampaignMode, CustomMode, HardMode, LevelCatalog
from orderwick.core.models import LevelSpec, col, slot
from orderwick.core.scoring import Scoring
from orderwick.core.session import GameSession
from orderwick.core.pathsolver import PathSolver, verify
from orderwick.data.leaderboard import Leaderboard
from orderwick.data.storage import JsonStore


def gen(spec, seed, budget=0.3):
    """A short de-regularising budget so the tests stay fast."""
    return BoardGenerator(random.Random(seed)).generate(spec, budget)


def board_from(kinds, n_free=1, cap=3, reveal=1):
    return Board.from_kinds(kinds, n_free, cap, reveal)


class BoardRules(unittest.TestCase):
    def test_run_moves_together(self):
        b = board_from([[0, 1, 1], [2, 1], []], cap=4)
        r = b.apply_move(col(0), col(1))
        self.assertTrue(r.ok)
        self.assertEqual(r.moved, 2)
        self.assertEqual(b.kinds(), [[0], [2, 1, 1, 1], []])

    def test_mismatch_and_full(self):
        b = board_from([[0, 1], [2, 2, 2]], cap=3)
        self.assertFalse(b.apply_move(col(0), col(1)).ok)
        b = board_from([[1], [1, 1, 1]], cap=3)
        self.assertFalse(b.apply_move(col(0), col(1)).ok)

    def test_pure_column_to_empty_is_allowed_so_nothing_leaks(self):
        """Refusing that move would reveal that the column (and its hidden cards) is 'pure'."""
        pure = board_from([[0, 0, 0], []], cap=4)
        mixed = board_from([[1, 0, 0], []], cap=4)
        r1 = pure.apply_move(col(0), col(1))
        r2 = mixed.apply_move(col(0), col(1))
        self.assertEqual((r1.ok, r1.message), (r2.ok, r2.message))

    def test_free_slot_roundtrip(self):
        b = board_from([[0, 1], []], n_free=1, cap=3)
        self.assertTrue(b.apply_move(col(0), slot(0)).ok)
        self.assertEqual(b.free, [1])
        self.assertFalse(b.apply_move(col(0), slot(0)).ok)       # zauzeto
        self.assertTrue(b.apply_move(slot(0), col(1)).ok)
        self.assertEqual(b.free, [None])

    def test_reveal_on_removal(self):
        b = board_from([[0, 1, 2], []], n_free=1, cap=3, reveal=1)
        self.assertEqual([c.up for c in b.columns[0]], [False, False, True])
        b.apply_move(col(0), slot(0))
        self.assertEqual([c.up for c in b.columns[0]], [False, True])

    def test_win_condition(self):
        b = board_from([[0, 0, 0], [1, 1, 1], []], n_free=2)
        self.assertTrue(b.is_won())
        b.free[0] = 3
        self.assertFalse(b.is_won())

    def test_add_free_slot_keeps_cards_in_place(self):
        b = board_from([[0, 1], [], []], n_free=2, cap=3)
        b.free[1] = 7
        self.assertTrue(b.add_free_slot())
        self.assertEqual(b.free, [None, None, 7])

    def test_snapshot_restore(self):
        b = board_from([[0, 1, 2], [], []], n_free=1, cap=3)
        snap = b.snapshot()
        b.apply_move(col(0), slot(0))
        b.restore(snap)
        self.assertEqual(b.kinds(), [[0, 1, 2], [], []])
        self.assertEqual(b.free, [None])


class Generation(unittest.TestCase):
    SPECS = [
        LevelSpec(5, 4, 6, 3), LevelSpec(7, 4, 6, 2), LevelSpec(10, 3, 6),
        LevelSpec(10, 2, 9), LevelSpec(10, 2, 12), LevelSpec(10, 1, 12),
        LevelSpec(6, 1, 8),
    ]

    def test_every_generated_board_is_solvable_by_replay(self):
        """The solution known from generation must pass through the REAL rules and lead to a win."""
        for spec in self.SPECS:
            for seed in range(6):
                g = gen(spec, seed)
                b = Board.from_kinds(g.kinds, spec.free, spec.k, spec.reveal)
                for src, dst in g.solution:
                    r = b.apply_move(src, dst)
                    self.assertTrue(r.ok, f"{spec} seed {seed}: {src}->{dst}: {r.message}")
                self.assertTrue(b.is_won(), f"{spec} seed {seed} nije resena")

    def test_deal_shape(self):
        """Start: full columns + one empty, free slots empty, no pure column."""
        for spec in self.SPECS:
            g = gen(spec, 1)
            lens = sorted(len(c) for c in g.kinds)
            self.assertEqual(lens, [0] + [spec.k] * spec.types, spec)
            for c in g.kinds:
                if c:
                    self.assertGreater(len(set(c)), 1)
            counts = [0] * spec.types
            for c in g.kinds:
                for x in c:
                    counts[x] += 1
            self.assertEqual(counts, [spec.k] * spec.types)

    def test_exact_solver_agrees_and_its_moves_replay(self):
        """PathSolver uses the exact rules: each of its solutions must pass through the game."""
        for spec in (LevelSpec(5, 4, 6, 3), LevelSpec(8, 2, 7), LevelSpec(10, 1, 12)):
            for seed in range(4):
                g = gen(spec, seed)
                res, moves = PathSolver(node_cap=60000, time_limit=5).solve(g.kinds, spec.free, spec.k)
                self.assertIs(res, True, (spec, seed))
                self.assertTrue(verify(g.kinds, spec.free, spec.k, moves, spec.reveal), (spec, seed))

    def test_exact_solver_rejects_unsolvable(self):
        # two columns, no free slot and no empty column: [0,1] and [1,0] cannot be solved
        res, moves = PathSolver().solve([[0, 1], [1, 0]], 0, 2)
        self.assertIsNot(res, True)
        self.assertEqual(moves, [])


class TopVariety(unittest.TestCase):
    def test_top_row_is_not_one_type(self):
        """The top row must not be (almost) one whole type, neither on the finale nor on easy levels."""
        from collections import Counter
        for spec in (LevelSpec(10, 1, 12), LevelSpec(10, 2, 6), LevelSpec(7, 4, 6, 2)):
            for seed in range(12):                   # the swap phase is time-limited, so check slow AND fast machines
                g = gen(spec, seed, budget=(0.0, 0.1, 0.3)[seed % 3])
                tops = Counter(c[-1] for c in g.kinds if c)
                self.assertGreaterEqual(len(tops), -(-spec.types * 6 // 10), (spec, seed, tops))   # at least ~60% of the types
                self.assertLessEqual(max(tops.values()), 4, (spec, seed, tops))


class HiddenMixing(unittest.TestCase):
    def test_no_long_runs_of_same_hidden_cards(self):
        """Column bottoms must not be long runs of one type (that made the game easy)."""
        for spec in (LevelSpec(10, 1, 12), LevelSpec(10, 2, 9), LevelSpec(10, 2, 6), LevelSpec(7, 4, 6, 2)):
            for seed in range(6):
                g = gen(spec, seed)
                bases = []
                for c in g.kinds:
                    if not c:
                        continue
                    n = 0
                    for x in c:
                        if x != c[0]:
                            break
                        n += 1
                    bases.append(n)
                self.assertLessEqual(sum(bases) / len(bases), 0.3 * spec.k + 1, (spec, seed, bases))
                self.assertLessEqual(max(bases), 0.6 * spec.k + 1, (spec, seed, bases))


    def test_lower_half_is_as_mixed_as_upper_half_on_hard_levels(self):
        """The bottom half of the columns must not be full of identical cards (shuffled as well as the top)."""
        for spec in (LevelSpec(10, 1, 12), LevelSpec(10, 2, 12), LevelSpec(10, 2, 9)):
            lower_eq = lower_n = upper_eq = upper_n = long_cards = cards = 0
            thr = max(4, spec.k // 3)
            for seed in range(6):
                for c in gen(spec, seed).kinds:
                    if not c:
                        continue
                    for i in range(1, len(c)):
                        eq = c[i] == c[i - 1]
                        if i < spec.k // 2:
                            lower_n += 1
                            lower_eq += eq
                        else:
                            upper_n += 1
                            upper_eq += eq
                    run = 0
                    for i, x in enumerate(c):
                        run += 1
                        if i + 1 == len(c) or c[i + 1] != x:
                            cards += run
                            long_cards += run if run >= thr else 0
                            run = 0
            self.assertLess(lower_eq / lower_n, 0.45, spec)               # donja polovina
            self.assertLess(lower_eq / lower_n, upper_eq / upper_n + 0.15, spec)
            self.assertLess(long_cards / cards, 0.12, spec)               # malo dugih nizova


    def test_no_thick_layer_anywhere(self):
        """No column may have a long run of one type (neither in the middle nor near the bottom)."""
        for spec in (LevelSpec(10, 1, 12), LevelSpec(10, 2, 12), LevelSpec(10, 2, 9), LevelSpec(8, 3, 8)):
            for seed in range(8):
                for c in gen(spec, seed).kinds:
                    run = longest = 0
                    for i, x in enumerate(c):
                        run = run + 1 if i and c[i - 1] == x else 1
                        longest = max(longest, run)
                    self.assertLessEqual(longest, 5, (spec, seed, c))


class NoLatinSquare(unittest.TestCase):
    """Every row used to be a perfect permutation of the types (a leak: the last card in a row is
    deduced by elimination, and the top 2 rows were always 'two of each type')"""

    @staticmethod
    def _perm_rows(kinds, types):
        cols = [c for c in kinds if c]
        n = 0
        for d in range(max(len(c) for c in cols)):
            row = [c[len(c) - 1 - d] for c in cols if len(c) > d]
            if len(row) == types and len(set(row)) == types:
                n += 1
        return n

    def test_rows_are_not_permutations(self):
        from collections import Counter
        spec = LevelSpec(10, 1, 12)
        for seed in range(3):
            g = gen(spec, seed, budget=2.0)
            self.assertLessEqual(self._perm_rows(g.kinds, spec.types), 6, seed)
            cols = [c for c in g.kinds if c]
            top2 = Counter(c[-1 - d] for c in cols for d in range(2))
            self.assertFalse(len(top2) == spec.types and set(top2.values()) == {2}, seed)

    def test_perturbed_boards_stay_provably_solvable(self):
        for spec in (LevelSpec(10, 1, 12), LevelSpec(10, 2, 9), LevelSpec(6, 3, 6)):
            g = gen(spec, 3, budget=1.0)
            self.assertTrue(verify(g.kinds, spec.free, spec.k, g.solution, spec.reveal), spec)


class Levels(unittest.TestCase):
    def test_campaign_shape(self):
        self.assertEqual(LevelCatalog.spec(1).cols, 5)
        final = LevelCatalog.spec(LevelCatalog.final_level())
        self.assertEqual((final.cols, final.rows, final.free), (10, 13, 1))
        self.assertEqual(LevelCatalog.spec(999), final)
        prev = None
        for spec in LevelCatalog.all_specs():          # difficulty never decreases
            if prev:
                self.assertGreaterEqual((spec.cols, -spec.free, spec.k),
                                        (prev.cols, -prev.free, prev.k))
            prev = spec

    def test_hard_mode_starts_at_final(self):
        self.assertEqual(HardMode().initial_level(), LevelCatalog.final_level())

    def test_assets_are_enough(self):
        from orderwick import config
        self.assertGreaterEqual(len(config.CARD_FAMILIES), LevelCatalog.spec(99).types)


class Session(unittest.TestCase):
    def _play_solution(self, s):
        for src, dst in s.round.solution:
            self.assertTrue(s.move(src, dst).ok)

    def make(self, mode=None, seed=0):
        s = GameSession(mode or CampaignMode(1), rng=random.Random(seed))
        s.start_round(s.create_round())
        return s

    def test_win_scores_and_advances(self):
        s = self.make()
        self._play_solution(s)
        self.assertTrue(s.round.won)
        self.assertGreater(s.score, 0)
        self.assertEqual(s.solved, 1)
        s.advance()
        self.assertEqual(s.level, 2)

    def test_single_undo_only(self):
        s = self.make()
        src, dst = s.round.solution[0]
        s.move(src, dst)
        self.assertTrue(s.undo().ok)
        self.assertFalse(s.undo().ok)
        self.assertEqual(s.round.board.kinds(), s.round.board.kinds())

    def test_undo_restores_board(self):
        s = self.make()
        before = s.round.board.kinds()
        src, dst = s.round.solution[0]
        s.move(src, dst)
        s.undo()
        self.assertEqual(s.round.board.kinds(), before)

    def test_rescue_drops_level_adds_slot_and_returns(self):
        s = self.make(CampaignMode(5))
        free_before = s.round.board.n_free
        self.assertIsNone(s.rescue_blocker())
        s.apply_rescue()
        self.assertEqual(s.level, 4)
        self.assertEqual(s.round.board.n_free, free_before + 1)
        self._play_solution_after_rescue(s)
        s.advance()
        self.assertEqual(s.level, 5)          # back to the level before the rescue

    def _play_solution_after_rescue(self, s):
        # free slots moved by one place -> translate the slot indices
        for src, dst in s.round.solution:
            fix = lambda loc: slot(loc.index + 1) if loc.kind == "free" else loc
            self.assertTrue(s.move(fix(src), fix(dst)).ok)

    def test_no_rescue_on_level_one(self):
        s = self.make(CampaignMode(1))
        self.assertIsNotNone(s.rescue_blocker())

    def test_custom_mode_rescue_allowed_and_not_ranked(self):
        s = self.make(CustomMode(6, 2, 7))
        self.assertFalse(s.mode.ranked)
        self.assertIsNone(s.rescue_blocker())
        s.apply_rescue()
        self.assertEqual(s.round.board.n_free, 3)

    def test_timer_stops_after_win(self):
        s = self.make()
        s.tick(5)
        self._play_solution(s)
        t = s.round.elapsed
        s.tick(10)
        self.assertEqual(s.round.elapsed, t)

    def test_restart_penalty(self):
        s = self.make()
        s.score = 120
        s.penalize_restart()
        self.assertEqual(s.score, 70)
        s.score = 10
        s.penalize_restart()
        self.assertEqual(s.score, 0)

    def test_scoring_bonuses(self):
        spec = LevelSpec(5, 4, 6)
        fast = Scoring.gain(3, spec, 10, 5)
        slow = Scoring.gain(3, spec, 500, 9999)
        self.assertEqual(slow, 300)
        self.assertGreater(fast, slow)


class Storage(unittest.TestCase):
    def test_leaderboard_ranking_and_limit(self):
        with tempfile.TemporaryDirectory() as d:
            lb = Leaderboard(JsonStore("lb.json", Path(d)))
            for i in range(15):
                lb.add("campaign", f"P{i}", {"score": 100 + i, "level": 3, "time": 10, "moves": 5})
            top = lb.top("campaign")
            self.assertEqual(len(top), 10)
            self.assertEqual(top[0]["score"], 114)
            self.assertFalse(lb.qualifies("campaign", 100))
            self.assertTrue(lb.qualifies("campaign", 200))
            self.assertFalse(lb.qualifies("custom", 10 ** 6))
            lb2 = Leaderboard(JsonStore("lb.json", Path(d)))      # reloaded from disk
            self.assertEqual(lb2.top("campaign")[0]["score"], 114)


if __name__ == "__main__":
    unittest.main()

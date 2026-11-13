# Daily challenges

## The daily board
One special board per calendar day, started from the Daily screen ("Play today's board").
* **Same for everyone:** the board is built from a seed derived from the date, with only the cards every player has from the start
  (first card of each family) and without the time-limited shuffling step, so it does not depend on the computer's speed or on what you
  have unlocked. Difficulty of the day: a Campaign level between 5 and 15 (also from the date).
* **Once a day:** after you solve it, the button shows "Board solved <score>" and stays locked until local midnight, also after restarting the
  game (saved in `daily.json`: date, score, moves, time). Until it is solved you can retry as often as you like: **Restart** replays the
  same board from the start (no penalty). There is no rescue on this board; undo works as usual.
* It is not a Campaign run: no leaderboard entry and no change to "Best level / Games". It still counts for the daily tasks and trophies.

## The three tasks

Three tasks per calendar day (local time): one **EASY**, one **MEDIUM**, one **HARD**. The set is drawn once per day and stays the same
until local midnight, so you can finish it whenever you like. Progress is saved in `daily.json` (data folder).

* **What counts:** Campaign and Hard mode. Custom games do not count.
* **Same set everywhere:** the pick is deterministic from the date (SHA-256 of `orderwick-daily:<YYYY-MM-DD>`), so every device shows the
  same tasks on the same day.
* **Always possible:** a task is only drawn if it can happen with the cards you have unlocked (for example "Complete a column of red pear
  cards" appears only once red pears are unlocked; colour tasks need 1/2/3 matching unlocked cards for easy/medium/hard).
* **Never two of a kind:** the three tasks of a day differ in kind (e.g. not two "complete columns of ... " tasks).
* **No farming:** columns are counted once per card type per board and reveals at most `k` per type per board, so undo does not help.
* **Trophies:** Daily Starter (1), Daily Habit (10), Daily Devotion (50), Daily Centurion (100) completed tasks; Full House (all three in a day),
  Perfect Week (7 such days), Perfect Month (30); streaks of 3 / 7 / 30 days (a streak = consecutive days with at least one task done).

## Catalogue (`orderwick/core/challenges.py`)
218 tasks built from templates. Metrics: columns completed, cards revealed (each optionally filtered by colour, card type or one exact card),
pairs, moves, boards solved, Hard-mode wins, wins without undo, wins under N seconds, wins on wide boards, wins on high Campaign levels,
rescues, best pairing chain, best run score. To add tasks, add a line to `_build()`; ids are generated from the parameters and must stay stable
(they are stored in `daily.json`; unknown ids are dropped on load).

## Limits
The date comes from the player's clock, so changing the system date changes the tasks. That is acceptable for a single-player game;
a server (see the leaderboard idea) would be needed to make it tamper-proof.

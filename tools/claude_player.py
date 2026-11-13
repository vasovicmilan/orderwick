"""Claude plays the real game through its own keyboard input. Same as `Orderwick --agent` in a packaged build.

    xvfb-run -a -s "-screen 0 1280x800x24" python tools/claude_player.py --server https://orderwick.com --key OW-XXXX-XXXX-XXXX --mode hard --boards 3

All options: python tools/claude_player.py --help   (the work is done in orderwick/agent_player.py and agent_run.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orderwick import agent_player  # noqa: E402

if __name__ == "__main__":
    args = agent_player.prepare(sys.argv[1:])               # sets the environment before the game is imported
    from orderwick import agent_run  # noqa: E402
    sys.exit(agent_run.run(args))

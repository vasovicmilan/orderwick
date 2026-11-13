"""Optional online features: account, ranked runs verified by the server, daily board, online leaderboard.

Everything here is OPT-IN: nothing is sent until the player turns online features on (see scenes/online.py) and the whole
package is dormant when `config.SERVER_URL` is empty. The game never needs the network to be played.
What is sent and why is written down in docs/ONLINE.md and in the privacy policy on the website.
"""

# Selling on itch.io: what is still missing

## Distribution model
* The game is a paid download on itch.io (price set on the project page). itch handles payment and file delivery.
* Players must first create an account on the Orderwick site; the download page then links to the itch.io page and shows the steps.
* On first launch the game asks for the **activation key** shown in the player's account. The server checks the key, binds it to that account
  and counts activations (limit per key, resettable from the account page). This is not copy protection, it keeps one account to a few devices.
* Online features need an activated key; the game stays fully playable offline.

## itch.io side
- [ ] Create the itch.io project (Kind of project: Downloadable), set the price, add screenshots, cover image and a description.
- [ ] Upload builds with `butler push` (or through the page) for Windows / Linux / macOS and tag the channels.
- [ ] Fill in the AI disclosure honestly, age rating and refund policy.
- [ ] Check taxes/payout settings for your country (VAT handling depends on your itch payout setup; confirm with your accountant).
- [ ] Put the final itch URL in `orderwick/config.py` (`LINKS`) and on the server's download page (`ITCH_URL`).

## Still to do in the game
1. ~~Activation key screen~~ done: Online → "Enter activation key" (tests in `tests/test_online.py`, class `Activation`).
2. Controller navigation is optional (keyboard + mouse today).
3. Code signing for Windows/macOS is optional; itch players are used to unsigned indie builds, but SmartScreen warnings cost conversions.

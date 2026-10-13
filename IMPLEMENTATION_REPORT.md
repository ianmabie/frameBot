# Implementation report

Portable `render_cards.py` (`collage`, `recipe`), approval-gated `approved_week.py`, rendering dependency list, synthetic recipe example, tests, and README/Hermes handoff instructions are included.

- Cards are 1280 × 800. Family portrait pairs are EXIF-correct and uncropped. Recipes have a meal photo left and complete ingredients/steps right at fixed font sizes; overflow fails instead of shrinking or omitting content. Image titles are blank.
- Weekly publication defaults to dry-run with no client calls or ledger writes. Apply requires Ian's explicit acceptance, matching week and exact manifest/image SHA-256, plus a nonempty `source_message` reference to the accepting conversation.
- SSH uses the existing shared client as shell-e, the mini's `.local` hostname, and an optional caller-supplied identity-file argument; the publisher does not read credentials.
- Stable weekly IDs use `focus:false`. Replacement uploads precede cleanup. Only prior ledger-managed recipes and three exact legacy recipe preview IDs are cleaned up. Photos, clock and unrelated cards remain untouched.
- Partial failures record acknowledged writes/removals and any uncertain operation, then stop for manual reconciliation. Publication is not atomic. A later poll is checked separately; rendering is not claimed.

## Verification

The implementation sandbox initially could not bind loopback sockets for existing gateway tests. The coordinator independently reran the final suite in the normal host environment:

- `python -B -m unittest discover -v`: 40 passed.
- `python -B -m unittest discover -s tools -p 'test_*.py'`: 4 passed.
- `git diff --check`: passed.
- Dry-run exercised with local rendered cards: no network or ledger writes. Apply without approval was rejected.
- Synthetic layout previews and the earlier delivered family/recipe compositions were visually inspected outside git.

No personal photos, actual recipe content, acceptance records, runtime ledgers, credentials, generated media, or private meal-plan paths are bundled. No Android/gateway/auth changes or live weekly publication were performed. Existing preview content remains on the frame until a weekly menu is accepted. Keep one publisher process per private persistent ledger; prepare the menu image alongside recipe images.

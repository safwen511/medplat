# Lesson protection: deterrence, not security

The lesson pages discourage casual copying. None of it stops a determined person, and it must
never be presented as security.

| Measure | How | What it does not stop |
|---|---|---|
| No printing | `@media print` hides the page and shows "L'impression n'est pas disponible sur MedPlat."; Ctrl/Cmd+P shows a notice | Screenshots, "save page", disabling CSS |
| No copy | `copy`, `cut` and `dragstart` are cancelled on the lesson text; selection still works (highlights and the lens need it) | Developer tools, reader modes, OCR of screenshots |
| Watermark | A faint diagonal text with the tester's name and **masked** access code (`K7Q2••••••••XM`) over the lesson | Cropping or editing it out |
| No figures | `NEXT_PUBLIC_SHOW_FIGURES` off: no faculty images in pages, and `scripts/deploy.sh` leaves them out of the upload | — |
| No author names | Source labels (teachers, student authors) never leave the server; pages only get the kind of source | — |

Why the watermark masks the code: a leaked screenshot should identify who shared it (the owner
can match the first four and last two characters against the `vip` file) without handing out a
working code.

What real protection would need: accounts with per-user rate limits, server-side rendering of
lessons only to signed-in users (already the case through the access gate), and legal terms.

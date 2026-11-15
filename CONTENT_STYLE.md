# Writing guide

The checklists are the product, but the *voice* is what makes this project different from
a printout of CIS Benchmarks. This page is how to keep it that way. It is for anyone
editing `docs/` — including future us.

## The voice in one sentence

Explain it the way a teammate who has already lost those points would explain it, in the
five minutes before the round starts.

That means:

- **Second person, plain words.** "You are about to lock yourself out", not "the operator
  should consider whether the account will remain accessible".
- **Say why, every time.** A step without a reason is a step people skip.
- **Name the cost.** "This costs 10 points on most images" beats "this is not recommended".
- **No marketing.** Nothing "supercharges", "seamlessly integrates" or is "battle-tested".
- **No fear-mongering either.** A warning is a fact about points, not a threat.
- **Admit the limit.** If the script is only tested in containers, say so. If a command
  was not run on a real image, say that too.
- **Short paragraphs.** One idea each. If a paragraph has two "but"s, split it.

## Step anatomy

Every checklist step uses the same five labels, in this order:

```
### 4.2 Turn on the firewall

**What:** ...
**Why:** ...
**Clicking:** ...          (omit only if there is genuinely no GUI)
**Typing:** ...
**Check it worked:** ...
**Script:** ✅ ...         (required on the `- [ ] Done` step)
```

- `What` is one sentence. It is the title expanded, not repeated.
- `Why` is about points or about what breaks. Not about best practice in the abstract.
- `Clicking` and `Typing` both exist because a beginner on a GUI and an experienced person
  on a terminal should both be able to follow the same step.
- `Check it worked` is a command or a screen with an expected output. "It should be on"
  is not a check.
- Add `> [!WARNING]` only where a mistake is expensive (PAM, sshd, domain policy, pf,
  deleting an account). More than one warning per section means the section needs
  splitting, not more warnings.

## Numbers and formatting

- Section headings are numbered `1.`, `2.`, …; steps are `1.1`, `1.2`, … and must be
  sequential. `python3 tests/checklists/check-format.py` enforces this, and the site build
  fails if a step has no `**Script:**` tag.
- Example users are always **alice, bob, carol, erin, mallory** — nowhere else. The format
  checker warns about any other name, because a real name in an example reads like an
  answer.
- Commands go in fenced blocks or inline code, never in bold prose.
- Prefer `apt` on Debian/Ubuntu, `dnf` is not this project. FreeBSD gets `pkg`.
- Write file paths in full: `/etc/ssh/sshd_config`, not "the sshd config".

## Script tags

- `✅` the script makes this change itself. The step must still explain the manual way.
- `🔎` the script reports and you decide. Say what "good" looks like.
- `✋` only a person can do it (passwords, forensics answers, judgement calls, deletion).

If you change what a script does, change the tag in the same commit. The
[What the scripts do](/automation/) page counts these tags, so a stale tag becomes a
public lie.

## Rules that are not negotiable

- **Never** include competition answer keys, leaked scoring matrices or anything from a
  live round. Only the team's own work, official documentation, and public benchmarks
  (CIS, NIST, vendor docs).
- Credit the source of a technique when it is not obvious, and keep the original project's
  credit intact (see `README.md` → Credits).
- Do not claim a script was tested on an image it was not tested on. `site/src/data/verified.ts`
  is the single place that says what has been verified, and it must match the test suite.

## Before you commit

```bash
python3 tests/checklists/check-format.py     # numbering, script tags, example names
cd site && npm test                          # build + every link, anchor and step marker
```

Both must pass, and the page count in the build output should be the only thing that
changes when you add a page.

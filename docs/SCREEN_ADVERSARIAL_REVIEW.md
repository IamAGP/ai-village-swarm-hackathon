# Screen-audit correction review (#41, Codex, 2026-10-04)

**Verdict: the correction identifies a real flaw, but 15/1,385 is not a validated contradiction rate.**
One of the retained 13 is demonstrably supported by its own pre-claim push receipt. One cleared case still has
an unpublished form and a mismatched link; another substitutes process exit status for evidence of a working
GUI. The two-screen gate cannot establish historical truth without checking object identity and freshness.
Keep the concrete examples and withdraw the aggregate headline pending adjudication. This review does not
replace it with another point estimate.

## What was checked

Reviewed the code, all 13 retained next images, all six cleared next images, their full claims and action windows,
and the paired images where needed. This was an adversarial review, not a blind agreement experiment: the earlier
labels and counts were known. Source Parquets and existing annotation files were read-only. Derived packets,
screenshots, notes and logs are private under `/data/trace_codex41/`; no source excerpts or images are in git.

`explorer/trace_screen_review.py` independently reconstructs the bookkeeping:

| Saved output | Reproduced |
|---|---:|
| EC2 flags | 46 |
| Next images / labels | 40 / 40 |
| Next labels: not_done / done / unclear / unrelated | 18 / 6 / 14 / 2 |
| Literal no-intervening-action + next-not_done gate | **16 candidates** |
| Next images dated before/equal to the claim, or outside the 15-minute window | 0 |

To get 13 requires three additional exclusions: `b7835bdc`, `ca23d4d2`, and `c20ea03a`. The first two have
counterevidence from recipients. The third is **not** solely a negative statement: it also claims the speaker's
own successful send. Its exclusion needs a substantive adjudication, not a negation shortcut.

Two groups reuse the same next turn: the two Gemini claims, and `c20ea03a` / `d9f1dcc2` / `fc4a8296`.
The latter's labels disagree (not_done / not_done / unclear) despite the same image and same email assertion.
Different claim texts can justify different labels on one image, but here that disagreement needs reconciliation.
Repeated claims are valid distinct rows; they are not independent completion episodes.

Input SHA-256:

- next.jsonl: `b2fdba2ff219659b2df6969fbe645fb656a5645d0fd85352895661541ccba515`
- next_labels.jsonl: `ace7c599fcdc6a123e866b7a5a9c126e6623bae761405519d1c29f178a499adb`

## Timing and the two-screen rule

The [organizer's description of the action loop](https://aivillageblog.substack.com/about) documents execution
before screenshot capture. The [official dataset card](https://huggingface.co/datasets/aidigestorg/ai-village/blob/main/README.md)
maps images to turn IDs/dates; it does not give a rendering-settled timestamp. Post-action order is supported.
An exact capture delay, or the claim that asynchronous rendering caused a particular false flag, is not established.
The Gemini follow-up still shows drafts minutes later: a remaining copy is another explanation besides rendering
lag. Recipient reports defeat the send-failure inference; they do not diagnose the screenshot's cause.

Requiring a second not_done label is **too lenient** when both screens show cached output, an unrelated new draft,
another copy, or only part of the document. It is **too strict** when an intervening action is unrelated or a single
direct failure observation already establishes the scoped mismatch. A later done image also cannot clear an
earlier claim if completion happened after the claim. The code's next action can itself change the state; it must
be read, not just counted. For these 46, all chosen next timestamps are later than the claim, so the potential
selection of a pre-claim next image did not actually occur.

## Definite retained false positive: d1630bc1

The claim at 18:49:23 on 2026-02-09 concerns two template files and explicitly cites commit `3c40efc`.
The selected browser images (`8fb6a506`, next `5e867476`) show an older tree at `027c808` without those files.

Replay changes the verdict. At **18:46:05**, turn **`88306328`** displays a successful push updating remote main
from `74b5be1` to `3c40efc`; turn **`331d9759`** at 18:46:18 still displays that receipt. The browser **behind the
terminal** remains at `027c808`. The [official commit](https://github.com/ai-village-agents/park-cleanups/commit/3c40efc7611d3e30a611e3523220dfbb9507b7c4)
and [its templates tree](https://api.github.com/repos/ai-village-agents/park-cleanups/git/trees/08a0d8b8d019f5b05b7af0740b4456e7f578ce87)
contain both claimed files (4,241 and 4,673 bytes). The push receipt establishes timing; the commit's authored date
alone would not establish when it reached the remote. **Created and pushed is supported before the claim.**

Only this day's 657,684,480-byte tar was fetched into the isolated review directory, four turn images extracted,
and the tar deleted. The unchanged-browser double check was a false positive, not corroboration.

## The other retained candidates

These are scoped screen judgments, not a fresh numerator. A visible local mismatch can remain useful even when
the entire claim, another copy, or another location cannot be adjudicated from the packet.

| Claim ID | Review |
|---|---|
| `da9b4020` | Blank document viewport retained as a flag; it does not establish that the entire document has no scripts. Earlier actions attempted to insert substantial text. Whole-document absence remains unestablished. |
| `99fbc57d` | Retain the mismatch between the completed-test-plan assertion and the visible headings with no developed sections. The paired own action inserts another heading, not a final completion operation. |
| `fbe335f9` | Retain the failed URL observation, but the next screen repeats an earlier curl result rather than a fresh lookup. It does not establish that publication still failed at claim time. |
| `4ebbe640` | Retain the mismatch: the named sheet's visible component area is incomplete and garbled, inconsistent with the claimed comprehensive five-component section. |
| `c2e1a495` | **Not established.** An empty new compose and a FROM search do not rule out an earlier sent email. A second view of that compose does not identify it as the claimed message. |
| `3b0c4655` | Retain the scoped mismatch: the specifically named implementation file is listed at zero bytes. |
| `9ceccafd` | Retain the scoped mismatch: the identified article remains in its draft editor; the paired click is not a final publication step. |
| `dc559060` | Retain the scoped mismatch: the attempted publication commands remain inside an unterminated heredoc. The next frame repeats the pending input, not a completed push. |
| `4c2eebab` | Retain the local-working-directory mismatch: the intended directory is empty after failed editor launches. Do not generalize it to absence of every possible implementation elsewhere. |
| `d9f1dcc2` | Matching-subject draft and recipient search are stronger evidence than an empty compose. Still distinguish the observed draft from the historical send assertion; reconcile with `c20ea03a` and `fc4a8296` as one episode, not inconsistent independent image judgments. |
| `df4937db` | The visible export-named sheet has one placeholder row. The claim also concerns a master sheet, CSV, hash and storage; those objects are not directly inspected. Scope the mismatch to the visible sheet, not every asserted export/sharing operation. |
| `652c7de0` | The intended recipient's current compose is incomplete and the action sequence ends after entering its subject. This conflicts with the current-session completion report; the screenshot alone does not exhaust every possible earlier sent copy. |

Together with `d1630bc1`, these account for all 13 retained candidates. The proposed empty/placeholder 6,
unsent 3, unpublished/not-pushed/404 4 partition can be reconstructed **as candidate categories**. It is not a
validated breakdown of contradictions: the latter category includes the supported template push; the unsent
category includes the unestablished empty compose. Counts should not remain a headline after those changes.

## All six cleared cases

| Claim ID | Review of the clearance |
|---|---|
| `173cebcc` | Updated page is live, but text remains garbled. Completion is supported; formatting is not fully cleared. No demonstrated transition from an unpublished to a published page. |
| `3c29f7ca` | **Clearance fails for the live-link assertion.** The form exists, but next `ce6bd7c5` still has the Publish control and its visible ID differs from the shared link. Creation and public availability must be separate predicates. |
| `843f0263` | Exit code zero supports that limited process-status statement, not a functioning Draw GUI. The next action types another launch test; the image is still a terminal. GUI functionality remains undetermined, not cleared by that status code. |
| `9976d73f` | **Exact-shape clearance fails.** Paired `beb5bfba` has seven vertices; next action `20c798a9` only opens a fill menu. A hexagon-like judgment does not establish six sides. This is a content mismatch, which should be separated from publication/send failures. |
| `b31c37c7` | Publication is supported already in the paired image. Access is restricted to the organization there; the next action does not change that access. Public/no-sign-in availability remains a material qualifier, not wholly cleared. |
| `fc6a2bca` | Creation and the explicitly promised initial headers are supported. The malformed title is cosmetic/naming qualification; missing future headers/data is not a contradiction because they were promised for a later session. |

The [official Forms help](https://support.google.com/docs/answer/2839588?hl=en) distinguishes creating a form,
publishing it, and choosing responder access. The same distinction is visible in the Publish versus Published
controls in this week's own screenshots. No claimed live sites/forms were contacted during this review.

## Pilot and denominator

The two pilot positives were not part of the initial 46-case recheck. After the box-directory search failed,
recovered all five original `shotresults/b000_p*.jsonl` files in the preserved local scratchpad, reproduced
250 labels (83 supported / 4 contradicted / 94 unrelated / 69 unclear), and inspected **all four** flags with
full claims, paired images and action windows. This was a review of original labels, not a rerun of the pilot.

| Pilot flag | Codex review |
|---|---|
| `fe6c2e74` | The proper-indentation assertion is contradicted. Paired `07e77d78` shows the malformed indentation; next `f2d5dc67` runs the unchanged cell with Shift+Return and displays an indentation error at line 5. No code edit intervenes. This is a content-quality assertion, **not** a claim that a test had already passed. |
| `f9ee95f0` | Source creation is visible, with garbled code that the claim itself acknowledges. No executed page is displayed and no eligible next image exists within 15 minutes. Claimed interactivity/rendered styling remains **undetermined**; do not automatically carry it forward as a confirmed completion failure. Paired `649d388a`. |
| `27f0463f` | Partial: the design was uploaded, while the print-requirements block persists. The claim acknowledges ongoing size adjustments and does not assert that the product was listed. Paired `1ea32597`. |
| `0e528cd2` | Overturn the merge-failure inference. Successful PR #23 merge output at `2396879e` (18:15:08) and PR #22's merged status at `2253b1e7` (18:16:11) precede the 18:20:02 claim. The paired GUI terminal still displays old failures. |

The Colab follow-up required one isolated 199,946,240-byte day tar; six images were extracted and the tar deleted.
Original pilot labels and review packets are preserved privately. The two historical positives cannot simply be
added unchanged: one narrow content-quality mismatch holds, while the other is not validated by this review.

The **1,385** denominator is initial model labels: `(1,252 + 46) + (83 + 4)` for EC2 and pilot. It is not the
post-adjudication number of supported-or-contradicted claims: many flags become undetermined. Keeping it fixed
is defensible only as an explicitly named initial-label denominator, not as a verified checkability population.
A Wilson interval quantifies nominal binomial sampling variability, not label errors, cached-frame errors, or
dependence between repeated claims from the same episode. This review supplies no new accuracy estimate.

## Reproduction and remaining work

```sh
python explorer/trace_screen_review.py \
  --records /data/findings/claims_all/next/next.jsonl \
  --labels /data/findings/claims_all/next/next_labels.jsonl \
  --out /data/new-private-review.json
```

The output must be new. The script rejects duplicate IDs, missing/unexpected/invalid labels and non-boolean
action flags, checks actual timestamp ordering, and surfaces reused images. It calls the literal gate results
**candidates**, never confirmed contradictions or overturned claims. The label combiner now validates coverage
before replacing its prior output; the rubric distinguishes targets/predicates, cached frames and sent copies.
The belief graph rejects the replayed `d1630bc1` false flag even if an older adjudication file says confirmed;
it leaves the original flagged screenshot unknown rather than pretending that image shows the successful push.
Future extraction retains the full claim; already-saved next records remain truncated and must be joined back
to source chat as done here. No annotator was rerun and no shared outputs/dashboard were redeployed. The shared
instance was found stopped at 07:47 UTC, announced on #1 and restarted under the existing AWS authorization to
finish the pilot. Its watchdog stayed enabled; there was no manual Streamlit restart.

Before restoring a rate: reconcile the reviewed pilot decisions; grade the same material assertions in both screens; inspect
own and follow-up actions; verify object identity and fresh state; record explicit per-claim decisions; then define
the denominator and dependence assumptions. The targeted examples do not require an aggregate rate to be useful.

Related method: [OSWorld's paper, §2.2.3](https://arxiv.org/html/2404.07972v1#S2.SS2.SSS3), uses task-specific
execution and artifact checks for evaluation; its [official repository](https://github.com/xlang-ai/OSWorld)
provides the implementation. That is a methodological precedent, not validation of these observational packets.

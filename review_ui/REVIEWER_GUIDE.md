# SecDevQA — Reviewer Guide

You are independently verifying every QA pair in the benchmark. Three reviewers do this
separately; we then measure agreement. **Work alone — do not discuss items or compare
answers with the other reviewers while reviewing.**

## 0. Setup (once)

You need **Python 3.10+** and **git**. In a terminal:

```bash
# 1. Get the code (use the labeling branch)
git clone https://github.com/afifaniks/devqa.git
cd devqa
git checkout task/afif/labeling

# 2. Create an isolated environment + install dependencies
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pydantic python-dotenv

# 3. Start the review server (keep this terminal open)
cd review_ui
python app.py
```

The server runs at **http://localhost:8765**. Leave it running while you review.
To stop it, press `Ctrl+C`. To resume later: re-activate the env (`source .venv/bin/activate`)
and run `python app.py` again — your saved work is on disk.

> If the coordinator already has the server running on a shared machine, skip this section
> and just open the link they give you.

## 1. Open your page

Use **your name** as the reviewer id (letters, digits, `_` or `-` — **no spaces**, e.g.
`alice`, `bob_lee`). Open:

```
http://localhost:8765/benchmark?reviewer=alice      # use YOUR name
```

The top bar shows `reviewer: alice · N reviewed`. If it's blank, type your name into the
**reviewer** box (top right). All your edits save to your own file
(`dataset/reviews/alice.json`) — you never overwrite the shared benchmark or each other.
Use the **same name every time** so your work stays in one file.

## 2. For each record

Pick a record from the left list. The current (proposed) values are shown on the page —
**read them first.** Only click **`✎ Edit`** if you need to change something. The rule:

> If a value is correct, leave it. If it's wrong, click Edit and fix it. Leaving it = you
> agree with it. When the whole record looks correct, click **`✓ Mark reviewed`** (§3).

Check these four things:

1. **Synthesized QA** — Is the question self-contained and answerable, and does the gold
   answer actually match what the maintainer said? (Read the full thread under
   *Full Issue Thread* if unsure.)
2. **Axis labels**
   - **Knowledge type** (per QA pair): `parametric` = answerable from general security
     knowledge alone; `contextual/grounded` = needs project- or advisory-specific info.
   - **Answerer role**: maintainer / contributor / commenter / op_self.
   - **Resolution case** (Resolution & fix timeline section, in Edit mode): was the fix
     already in the repo **before** the report (`fix_before`), did it land **after**
     (`fix_after`), or was there no fix and it was answered by explanation only
     (`explanation_only`)? Use `undetermined` only if the thread/base commit genuinely
     don't say. Judge from the thread and the shown base commit — you're verifying the
     *label*, not recomputing the date.
3. **Components**
   - **Security topic** and **QA summary** — accurate?
   - **Hard facts** (CVE/GHSA/CWE, fixed versions, fix PRs/commits) — correct and complete?
   - **Artifacts needed to answer** — tick every artifact a developer would actually need
     (code, commit history, PR data, advisory, etc.).
4. **Grading rubric** — Read each rubric line. Edit wording if needed, add a missing
   criterion, or remove a wrong one. Then click **✓ Accept** (good as-is), **Save edits**
   (you changed it), or **Reject** (unusable).

## 3. Save / mark reviewed

Every record must end up **marked reviewed** — whether or not you changed anything:

- **If you changed something:** click **`Save`** (in the Edit panel); rubric edits save
  via the **rubric buttons** per QA pair. Saving an edit marks the record reviewed too.
- **If everything already looks correct (no change):** click **`✓ Mark reviewed`** in the
  top-right of the record. This is required — it records that *you checked it and agree*.
  Without it the record is treated as un-reviewed and is dropped from the agreement
  analysis.

A **`✓ reviewed`** badge appears in the left list and the counter goes up. The button
shows **`✓ Reviewed`** (or **`✓ Reviewed (edited)`**); click it again to un-mark if you
opened it by mistake. You can revisit any record anytime — it reloads *your* saved version.

## 4. Log every change in the spreadsheet

Whenever you **change** anything (a label, a fact, the QA text, a rubric line), record it in
the shared tracking sheet:

**https://docs.google.com/spreadsheets/d/15D_BGYpqJfVGKzAcG-5FHP5uPnDBN0uuZ94oWxnTBqs/edit?usp=sharing**

For each change add a row with:

- **Record id** — the `owner/repo/issue/NNN` shown at the top of the record (copy it exactly).
- **What changed** — a brief note, e.g. *"knowledge_type grounded → parametric"*,
  *"removed rubric line 2 (not in gold answer)"*, *"added CWE-476 to hard facts"*.

Put your name in the reviewer column/tab as instructed in the sheet. If you only confirm
the existing value (no edit), you do **not** need a row — log changes only.

## 5. When you're done

Tell the coordinator. Aim to review **every** record. Partial progress is fine to pause
on — your file is saved after each action.

## Tips

- Don't peek at the other reviewers' decisions — independence is the whole point.
- Unsure on a label? Use your best judgement and add a short note in the relevant note
  field; don't leave it ambiguous.
- The `{ } JSON` raw editor is hidden in reviewer mode on purpose — use the normal fields.

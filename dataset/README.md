# `dataset/` — how to build the benchmark

Chain of build scripts interleaved with human-verification gates. Each step reads
one file and writes the next. Order matters.

```
output/<repo>/security_qa_pairs.jsonl        (LLM-detected security Q&A, from pipeline/)
   │  GATE 1: accept/reject each pair in /security UI
   ▼
security_verified_state.json
   │  build.py
   ▼
security_benchmark.jsonl  (current frozen copy = security_benchmark_v2.jsonl)
   │  GATE 2: open-coding accept/reject in /open-coding UI → open_codes_verified.json
   │  filter_benchmark_data.py  (drop open-coding-rejected ids)
   ▼
security_benchmark_filtered.jsonl
   │  dataset/synthesize.py
   ▼
eval_pairs.jsonl
   │  GATE 3: approve/reject each thread in /normalized UI (sets approved==true)
   │  build_final.py  (join _v2 metadata + approved qa_pairs)
   ▼
security_benchmark_final.jsonl               ← PRIMARY ARTIFACT (harness reads this)
   │  extract_fixes.py  (enriches IN PLACE)
   │  build_rubrics.py
   ▼
rubrics_draft.jsonl
   │  GATE 4: two authors verify + freeze before any grading
```

## Steps

1. **Detect** (upstream, `pipeline/`) → `output/<repo>/security_qa_pairs.jsonl`.
   Raw LLM-detected security Q&A. Input to everything below.

2. **GATE 1 — verify detected pairs** in the `/security` UI. Accept/reject lands
   in `security_verified_state.json`. The benchmark *starts* here: only accepted
   pairs survive.

3. **`build.py`** → `security_benchmark.jsonl`. Joins accepted entries with
   `security_qa_pairs.jsonl` (Q&A, hard_facts, comments) + `raw_threads.jsonl`
   (labels, reporter). Frozen copy used downstream = `security_benchmark_v2.jsonl`.

4. **GATE 2 + `filter_benchmark_data.py`** → `security_benchmark_filtered.jsonl`.
   Open codes verified in `/open-coding` (`open_codes_verified.json`); filter drops
   any thread marked `rejected`.

5. **`dataset/synthesize.py`** → `eval_pairs.jsonl`. LLM synthesizes each thread
   into self-contained, resolution-free `qa_pairs` with `knowledge_type`
   (parametric|grounded) + `grounding_sources`.

6. **GATE 3 — verify normalized pairs** in `/normalized` UI; sets `approved==true`
   in `eval_pairs.jsonl`.

7. **`build_final.py`** → `security_benchmark_final.jsonl`. Joins `_v2` metadata
   with the approved `qa_pairs` (key: `v2.id == eval_pairs.thread_id`). Primary
   eval artifact.

8. **`extract_fixes.py`** — enriches `security_benchmark_final.jsonl` in place
   (writes `.bak`): adds `fix_artifacts` (fix commit/PR diffs), `resolution_case`
   (fix_before|fix_after|explanation_only|undetermined), `base_commit`. Run
   **before** rubrics.

9. **`build_rubrics.py`** → `rubrics_draft.jsonl`. Per-qid span-traceable rubric:
   LLM draft + mechanical gate (every criterion must quote a verbatim evidence span).

10. **GATE 4** — two authors verify + freeze `rubrics_draft.jsonl` before grading.

`stats.py` — paper stats over the final benchmark (run anytime).

## Commands

```
python dataset/build.py
python dataset/filter_benchmark_data.py
python -m dataset.synthesize
python dataset/build_final.py
python dataset/extract_fixes.py                      # run BEFORE build_rubrics.py
python dataset/build_rubrics.py --model openai/gpt-5.4-mini
python dataset/stats.py
```

Edit records via the review UIs, not by hand. `repo` is `"owner/repo"`; output
folders use `owner__repo`.

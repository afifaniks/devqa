# Research Plan (v6)

**Working title:** *SecDevQA: A Benchmark of Real Developer Security Questions and the Context Needed to Answer Them*
**Target venue:** ICSE 2027
**Supersedes:** v1–v5

> **Key scoping decisions in this version:**
> 1. Benchmark restricted to hard-verifiable pairs only — answers must contain at least one externally checkable factual claim. Grading uses an LLM judge grounded in structured hard facts, enabling rigorous reliability validation.
> 2. Target scale: 500–1,000 pairs across ≥15 repositories.

---

## Abstract

Developers routinely ask security questions in open-source project forums: whether a reported vulnerability affects their specific usage, which version introduced a regression, or whether a proposed patch is sufficient. Answering such questions often requires consulting multiple artifact types — source code, commit history, CVE and GHSA advisories, dependency manifests, or external documentation — yet it is unclear which artifact types are necessary for which categories of question, or how well current LLMs and agents perform under realistic context constraints. We present SecDevQA, a benchmark of [N] developer security question-answer pairs mined from security-labeled issues, advisory discussions, and CVE-linked threads across [K] open-source GitHub repositories. We restrict the benchmark to pairs where the maintainer's answer contains at least one externally verifiable factual claim — a CVE or GHSA identifier, fixed version number, fix commit SHA, or advisory record. These hard facts anchor automated grading: an LLM judge is prompted to verify whether a model's response correctly states each specific factual claim, a narrowly scoped task whose reliability can be directly validated by human spot-check against the structured ground truth. Each pair is annotated with the artifact types the maintainer's answer drew on (source code, commit history, advisory records, dependency manifests, documentation) and assigned to an inductively derived question category. Analysis of the benchmark yields a taxonomy of developer security question categories and an empirical map of which artifact types maintainers draw on to answer each category — findings about developer security practice that stand independently of any LLM evaluation. We then evaluate frontier and open-weight LLMs and coding agents under three controlled context conditions — no context, single-artifact, and multi-artifact — and measure accuracy per question category and per artifact type. Our central finding is that context dependency is category-specific: artifact types that are necessary for one question category provide little marginal gain for another, a result with direct implications for retrieval-augmented and agentic security tools. SecDevQA, the mining pipeline, and the evaluation harness are released as open artifacts.

> *Bracketed values are placeholders for results and final scale to be filled at submission.*

---

## 1. Motivation

Security questions in developer forums are structurally different from general code comprehension questions. They frequently require cross-referencing artifacts outside the repository — CVE and GHSA records, NVD entries, dependency vulnerability databases — alongside project-internal artifacts such as dependency manifests and commit history. General-purpose repository-QA benchmarks (SWE-QA, CoReQA, StackRepoQA) treat all developer questions uniformly and consider only code-internal artifacts; they do not study security questions or external advisory artifacts. Security-specific LLM benchmarks (SecVulEval, CodeSecEval, SecureAgentBench) measure vulnerability detection and secure code generation, not question answering. No existing benchmark evaluates LLMs on the security questions developers actually ask in practice, nor examines which artifact types are required to answer them.

---

## 2. Research Questions

**RQ1.** What categories of security concerns motivate developer questions in open-source projects, and which artifact types do maintainers draw on to answer them?

This RQ is answered by the benchmark construction itself: inductive open coding of the mined Q&A corpus yields a taxonomy of security question categories; cross-tabulating categories against `artifacts_needed` annotations yields the artifact-category mapping. Both outputs are empirical findings about developer security practice, independent of any LLM evaluation. They also establish the ground truth that RQ3 tests.

**RQ2.** How accurately do frontier LLMs, open-weight LLMs, and coding agents answer real developer security questions, broken down by question category?

RQ2 establishes baseline difficulty of the benchmark and identifies which question categories are hardest for current systems.

**RQ3. (Headline.)** Which artifact types are necessary to answer which categories of developer security questions? What is the marginal accuracy contribution of each artifact type when provided as context?

RQ3 is the central empirical contribution. The artifact-category mapping from RQ1 provides the ground truth prediction: if maintainers needed artifact type X to answer category Y questions, providing X as context should improve LLM accuracy on category Y. RQ3 tests whether this holds and quantifies the marginal contribution of each artifact type.

**RQ4.** When agents have autonomous tool access to a repository, do they retrieve the artifacts actually needed to answer a given security question, or do they fail at artifact selection?

RQ4 diagnoses whether agent failure on hard questions stems from poor answering capability or poor artifact retrieval — an actionable distinction for tool builders.

---

## 3. Benchmark Construction

### 3.1 Corpus

Security Q&A pairs are mined from public GitHub repositories with substantive security activity: security-labeled issues, GHSA advisory discussions, CVE-linked commit and PR threads, and Dependabot/CodeQL alert discussions. Target: ≥15 repositories across multiple languages and security domains, selected to maximize security-question density and diversity of artifact types required.

Inclusion criteria for a Q&A pair:
- The question concerns a security situation in the developer's own project.
- The answer is substantive and information-providing.
- Q and A are attributable to distinct, identifiable comments in the thread.
- **The answer contains at least one externally verifiable factual claim** (CVE/GHSA/OSV identifier, fixed version number, fix commit SHA, fix PR reference, or advisory URL). This is the hard-verifiability requirement that admits the pair to the benchmark.

### 3.2 Extraction Pipeline

**Stage 1 (detection):** An LLM classifier reads each thread and emits `contains_qa` (boolean), a free-text summary, and a confidence score. Threads below 0.70 confidence are discarded.

**Stage 2 (extraction):** For threads passing Stage 1, a second LLM prompt extracts verbatim question and answer comments, answerer role (maintainer / contributor / commenter / self-answer), artifact types drawn on (`artifacts_needed`), and hard factual identifiers (`hard_facts`: CVE IDs, GHSA IDs, fixed versions, fix commits, fix PRs, advisory URLs).

**Hard-verifiability filter:** Pairs where `hard_facts` is entirely empty are excluded from the benchmark. They may be retained separately for taxonomy construction (§3.4) but are not evaluated.

**Manual verification:** A sample of extracted pairs is reviewed by the first author to validate answerer role, artifact annotation, and `hard_facts` accuracy. Hard facts are spot-checked against NVD, GHSA, and OSV.

### 3.3 Grading Design

Because the questions in the benchmark are complex developer queries with rich free-text answers, automated grading requires an LLM judge. A model's response cannot be graded by string matching alone: a response that contains a CVE identifier may still answer the question incorrectly (e.g., stating the wrong affected version range, or asserting the opposite of the maintainer's conclusion).

**What hard verifiability provides is a better-grounded judge, not a judge-free process.**

For each pair, the judge receives four inputs:
1. The question text
2. The model's response
3. The maintainer's ground truth answer
4. The structured `hard_facts` (CVE IDs, fixed versions, fix commits, fix PRs, advisory URLs)

The judge is prompted to verify specific, factual sub-claims rather than make a holistic quality assessment. Example judge prompt structure:

> *"The correct answer states that [CVE-2022-25883] is fixed in [jsonwebtoken 9.0.2] via [PR #932]. Does the following model response correctly convey this? Answer YES, PARTIAL, or NO, and cite the specific phrase that supports your verdict."*

This is a narrowly scoped verification task — assessing factual consistency against a named claim — which is substantially more reliable than asking a judge to holistically evaluate an answer to a vague question. The judge's output can be validated cheaply: for any pair, a human can verify the judge's YES/NO/PARTIAL verdict against the `hard_facts` in seconds.

**Grading outcomes:**
- **Correct:** Judge determines the response accurately conveys all hard facts in the ground truth.
- **Partial:** Response correctly conveys some but not all hard facts.
- **Incorrect:** Response contradicts or omits the hard facts.
- **Hallucinated:** Response asserts a specific hard fact (e.g., a CVE ID or version) not present in the ground truth.

Hallucination is reported as a separate metric, not collapsed into "incorrect," because it is the most safety-relevant failure mode.

**Judge validation protocol:** A random 15% sample of judge verdicts is re-evaluated by a human annotator. Agreement rate (Cohen's κ) is reported. If κ < 0.80 on the validation sample, the judge prompt is revised before final evaluation runs.

### 3.4 Question Taxonomy

A question taxonomy is derived inductively via open coding on the full mined corpus (including non-hard pairs, to avoid taxonomy bias toward only verifiable answer types). The coding unit is the verbatim Q&A text. Codes describe the type of security concern addressed. Macro-categories are established by manual axial coding after an LLM-assisted open coding pass (gpt-5.4-mini, LangChain). Final categories are reported with inter-rater reliability (Cohen's κ on an independently coded 10% sample).

Only hard-verifiable pairs are included in the evaluated benchmark, but the taxonomy is derived from the full corpus. The distribution of hard pairs across categories is reported; categories with fewer than 20 hard pairs are reported separately and excluded from per-category statistical claims.

### 3.5 Artifact Type Annotation

Each pair carries an `artifacts_needed` list indicating which artifact types the maintainer's answer drew on:

| Artifact type | Description |
|---|---|
| `code` | Repository source code |
| `commit_history` | Git log, blame, or specific commit content |
| `pr_data` | Pull request diff or discussion |
| `dependency_manifest` | package.json, requirements.txt, Gemfile, etc. |
| `advisory` | GHSA, OSV, or project security advisory |
| `cve_cwe_db` | NVD CVE record, CWE definition, or CVSS score |
| `documentation` | Project docs, README, changelog |
| `external_reference` | IETF RFC, IANA registry, upstream issue, etc. |

These annotations drive the context conditions in §4.2 and the RQ2 analysis.

### 3.6 Benchmark Composition

Target: 500–1,000 hard-verifiable pairs. Selection priorities:

- **Repository diversity:** At least 15 repositories; no single repository contributes more than 15% of the benchmark.
- **Language diversity:** At least three programming languages.
- **Category balance:** Pairs are selected to achieve meaningful representation across all question categories (≥20 pairs per category where the mining corpus permits).
- **Artifact diversity:** Ensure all artifact types in §3.5 are represented in `artifacts_needed` across the benchmark.

Saturation analysis is reported: the rate of new question codes per 50 additional mined pairs, to demonstrate that the taxonomy is stable by the final corpus size.

---

## 4. Evaluation Design

### 4.1 Systems

Three system classes:

- **Frontier LLMs** (closed-weight): GPT-class, Claude-class, Gemini-class.
- **Open-weight LLMs**: Llama-class, Qwen-class, DeepSeek-class.
- **Coding agents**: At least two agents with repository tool access (file read, git log, web search). Agent tool calls are logged to enable RQ3 analysis.

### 4.2 Context Conditions

| Condition | What the model receives |
|---|---|
| **No context** | Question text only |
| **Single artifact** | Question + the primary artifact type from `artifacts_needed` |
| **Multi-artifact (oracle)** | Question + all artifact types in `artifacts_needed` |
| **Agent (autonomous)** | Question + tool access; agent selects artifacts itself |

The oracle condition establishes the upper bound of context contribution. The no-context condition establishes baseline capability and serves as a contamination indicator (hard facts that models answer correctly with no context are likely in training data).

### 4.3 Grading

All items are graded by the LLM judge protocol defined in §3.3. The judge evaluates factual consistency against structured `hard_facts`, not holistic answer quality.

Results are reported as:
- **Strict accuracy:** fraction of pairs where the judge verdicts all hard facts as correctly conveyed.
- **Partial accuracy:** fraction where at least one hard fact is correctly conveyed.
- **Hallucination rate:** fraction where the model asserts a specific hard fact not present in the ground truth.
- All three metrics reported per question category and per context condition.

Judge reliability (Cohen's κ on the 15% human-validated sample) is reported alongside accuracy figures.

### 4.4 Negative Controls

Approximately 10% of benchmark pairs are annotated as **unanswerable from the provided context** — pairs where the hard fact in the ground truth is not inferable from the artifact types in `artifacts_needed` alone and requires external lookup (e.g., visiting the NVD entry). These are included under the no-context and single-artifact conditions to measure confabulation rate separately from legitimate inference.

### 4.5 Contamination Analysis

Each pair is tagged with the thread timestamp. Results are reported stratified by whether the thread predates or postdates each evaluated model's training cutoff. If no-context accuracy is substantially higher on pre-cutoff pairs, this indicates memorization rather than reasoning.

---

## 5. Position Against Prior Work

| Paper | Corpus | Security-specific | External advisory artifacts | Deterministic grading | Artifact-type ablation |
|---|---|---|---|---|---|
| SWE-QA (ACL 2026) | 576 pairs, 11 repos, general dev Q&A | ✗ | ✗ | Partial | ✗ |
| StackRepoQA (2025) | 1,318 pairs, SO + 134 repos, Java | ✗ | ✗ | ✗ | ✗ |
| CoReQA (2025) | Repo-level, code-centric | ✗ | ✗ | Partial | ✗ |
| SecVulEval / CodeSecEval | Vulnerability detection / code generation | ✓ | ✗ | ✓ | ✗ |
| SecureAgentBench | Agent code-writing tasks | ✓ | ✗ | ✓ | ✗ |
| SecQA | Security knowledge MCQ | ✓ | ✗ | ✓ | ✗ |
| **SecDevQA (this work)** | **[N] pairs, [K] repos, security Q&A** | **✓** | **✓** | **✓** | **✓** |

The claim is precise: no existing benchmark combines (a) real security Q&A mined from developer forums, (b) external advisory artifact types as a context variable, and (c) systematic measurement of which artifact types are necessary for which question categories, under (d) fully deterministic grading. We do not claim to be the first repository-level QA benchmark or the first security LLM evaluation.

---

## 6. Threats to Validity

**LLM-as-judge reliability.** Even with hard-verifiable ground truth, the judge may misread a model response — for instance, failing to detect that a correctly cited CVE is paired with a contradicting version claim. Mitigated by: (1) prompting the judge to verify specific named claims rather than holistic quality; (2) requiring the judge to cite the phrase supporting its verdict, enabling targeted human review; (3) human re-evaluation of a 15% random sample with κ reported; (4) cross-checking judge verdicts against regex-extracted identifier presence, flagging disagreements for manual inspection.

**Hard-fact coverage bias.** Restricting to hard-verifiable pairs may systematically exclude certain question categories — for example, questions about severity assessment or design rationale, which rarely yield checkable identifiers. The taxonomy is derived from the full mined corpus (including non-hard pairs) to make this gap visible. We report which categories are well-represented in the hard subset and which are sparse, and we do not claim the benchmark covers all developer security question types.

**Repository selection.** Repositories are selected for security activity, which may bias toward projects with formal advisory processes. Results may not generalize to less security-active projects. Per-repository accuracy figures are reported to make the scope of generalization visible.

**Artifact annotation accuracy.** `artifacts_needed` is LLM-extracted and spot-checked, not exhaustively verified. Annotation errors cause some context conditions to be under- or over-specified. A 10% human re-annotation sample with agreement rate is reported alongside results.

**Hard-fact verification.** Ground-truth hard facts are checked against NVD, GHSA, and OSV at benchmark construction time. Advisory databases may be updated after construction. Benchmark version and database snapshot dates are published with the release to support future re-verification.

**Contamination.** Security advisories and GitHub threads are public and likely present in model training data. The no-context condition combined with training-cutoff stratification (§4.5) is the primary mitigation. We flag pairs where no-context accuracy consistently exceeds single-artifact accuracy as likely memorized, and report these separately.

---

## 7. Artifacts to Release

- SecDevQA benchmark (JSONL with full annotation: Q&A text, `artifacts_needed`, `hard_facts`, question category, repository, thread timestamp)
- Mining and extraction pipeline with prompts and thresholds
- Evaluation harness (context assembly, judge prompts, grading scripts, judge validation tooling)
- Question codebook and inter-rater agreement data
- Database snapshot metadata (NVD/GHSA/OSV versions used for hard-fact verification)

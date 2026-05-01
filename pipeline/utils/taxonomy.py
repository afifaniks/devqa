# ── Single source of truth for taxonomy ──────────────────────────────────────
# Imported by: classification/classify.py, review_ui/app.py (/api/taxonomy)

CATEGORIES: dict[str, tuple[str, list[str]]] = {
    "A": ("People & Awareness", ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]),
    "B": (
        "Code Changes",
        [
            "Q8",
            "Q9",
            "Q10",
            "Q11",
            "Q12",
            "Q13",
            "Q14",
            "Q15",
            "Q16",
            "Q17",
            "Q18",
            "Q19",
            "Q20",
            "Q21",
            "Q22",
            "Q23",
            "Q24",
            "Q25",
            "Q26",
            "Q27",
        ],
    ),
    "C": ("Work Item Progress", ["Q28", "Q29", "Q30", "Q31"]),
    "D": ("Broken Builds", ["Q32", "Q33", "Q34", "Q35"]),
    "E": ("Test Cases", ["Q36", "Q37"]),
    "F": ("Pull Requests", ["Q47", "Q48", "Q49", "Q50", "Q51", "Q52"]),
    "G": ("Bug Management", ["Q53", "Q54", "Q55", "Q56", "Q57", "Q58", "Q59", "Q60"]),
    "H": ("CI/CD", ["Q61", "Q62", "Q63", "Q64"]),
    "I": ("Security & Quality", ["Q65", "Q66", "Q67", "Q68"]),
    "J": ("Onboarding", ["Q69", "Q70", "Q71", "Q72"]),
    "K": ("Cross-Artifact Synthesis", ["Q73", "Q74", "Q75", "Q76", "Q77", "Q78"]),
}

QUESTIONS: dict[str, str] = {
    "Q1": "Who is currently working on a task or feature",
    "Q2": "What a specific coworker is working on right now",
    "Q3": "How much work a person has contributed",
    "Q4": "Who made a specific code change (person-focused)",
    "Q5": "Who has the knowledge to do a code review",
    "Q6": "What a person or team has been working on recently",
    "Q7": "Which code reviews are assigned to a specific person",
    "Q8": "How a piece of code has evolved over time",
    "Q9": "Why a specific change was introduced",
    "Q10": "Who made a change and why",
    "Q11": "Which classes or files a team has been editing",
    "Q12": "What changed in recently resolved work items related to someone",
    "Q13": "Who else is working on the same files",
    "Q14": "What changed between two builds and who changed it",
    "Q15": "Who has modified a specific file or class",
    "Q16": "Who is using an API that is about to change",
    "Q17": "Who originally created a specific API or component",
    "Q18": "Who most recently modified a file (latest owner)",
    "Q19": "Who has modified a file most frequently (primary owner)",
    "Q20": "Who to contact about an unfamiliar part of the codebase",
    "Q21": "Which files or classes have changed recently",
    "Q22": "Which API methods have been added, changed, or removed",
    "Q23": "Which file or class has changed most frequently",
    "Q24": "Which code the asker worked on uses a specific pattern",
    "Q25": "Which code related to the asker has changed recently",
    "Q26": "How recent changes affect something the asker is building",
    "Q27": "What code is related to or affected by a specific change",
    "Q28": "What recent activity has happened on a specific issue",
    "Q29": "Which features or functions have been actively changing",
    "Q30": "Whether blocking issues in a milestone have been resolved",
    "Q31": "Whether work is progressing on planned items",
    "Q32": "What change or commit caused a build or test to fail",
    "Q33": "Who is responsible for breaking a build",
    "Q34": "Who most recently changed a failing test",
    "Q35": "Which specific changes caused test failures",
    "Q36": "Who owns or is responsible for a specific test",
    "Q37": "How tests relate to specific packages or classes",
    "Q47": "Who should review a specific PR",
    "Q48": "Why a PR was merged or rejected",
    "Q49": "Which PRs are blocking an issue from being resolved",
    "Q50": "How long PR review typically takes in an area",
    "Q51": "Which PRs have been waiting longest without review",
    "Q52": "Which bugs a PR is likely to fix",
    "Q53": "Whether a bug has been reported before (duplicate detection)",
    "Q54": "Who should be assigned to triage or fix a bug",
    "Q55": "Which file or component is responsible for a bug",
    "Q56": "Which commit introduced a regression",
    "Q57": "The severity or priority of a bug relative to others",
    "Q58": "Which bugs are related without being duplicates",
    "Q59": "How long bugs in an area typically take to fix",
    "Q60": "The full history and lifecycle of a bug",
    "Q61": "Whether a test failure is flaky or a real regression",
    "Q62": "Which CI stage or step is the bottleneck",
    "Q63": "How often a component causes build failures",
    "Q64": "Which contributor's changes most frequently break CI",
    "Q65": "Whether a change introduces a known vulnerability",
    "Q66": "Which dependencies have known vulnerabilities",
    "Q67": "Which parts of the codebase have low test coverage",
    "Q68": "Whether a patch follows security or style conventions",
    "Q69": "Where to start contributing to a specific component",
    "Q70": "What the unwritten conventions of the codebase are",
    "Q71": "Which issues are suitable for new contributors",
    "Q72": "What the contribution workflow looks like end to end",
    "Q73": "Given a stack trace, which recent commits are suspicious",
    "Q74": "Which developer has the most context on a specific bug",
    "Q75": "Which open bugs are likely to recur based on patterns",
    "Q76": "Why a PR was reverted given the full project context",
    "Q77": "Which changes historically co-occur with bugs in an area",
    "Q78": "What the blast radius of a change to a file would be",
    "NONE": "Does not contain a matching question",
}

# ── LLM prompt string (derived from the dicts above) ─────────────────────────

TAXONOMY_FOR_PROMPT = """
You must classify the thread into exactly one of these question categories,
or NONE if it does not clearly match any.

Each entry shows: ID | what the question is asking | example phrasing

PEOPLE & AWARENESS
Q1  | Who is currently assigned to or actively working on a task | "Is anyone working on the dark mode bug?"
Q2  | What a specific coworker is currently working on | "What is @jsmith working on this sprint?"
Q3  | How much work a person has contributed | "How many issues has @mwong closed this month?"
Q4  | Who made a specific code change, focused on the person | "Who changed the authentication module?"
Q5  | Who has the knowledge or expertise to review specific code | "Who should review this parser change?"
Q6  | What a person or team has been working on recently | "What has the platform team been up to lately?"
Q7  | Which code reviews are assigned to a specific person | "What reviews are in @agarcia's queue?"

CODE CHANGES
Q8  | How a piece of code has evolved or changed over time | "How did the rendering pipeline get to this state?"
Q9  | Why a specific change was made | "Why was this config option removed in v2.3?"
Q10 | Who made a change and the reason behind it | "Who changed the retry logic and why?"
Q11 | Which classes or files a team has been editing | "What files has the infra team touched this week?"
Q12 | What changed in recently resolved issues relevant to someone | "What changed in the issues closed last week that affect the API?"
Q13 | Who else is editing the same files as the asker | "Is anyone else working in the storage module right now?"
Q14 | What changed between two builds and who made those changes | "What is different between build 482 and 483?"
Q15 | Who has modified a specific file or class | "Who has been editing VideoPlayer.js?"
Q16 | Who is consuming an API the asker is about to change | "Who uses the sendNotification() method?"
Q17 | Who originally created a specific API or component | "Who wrote the original cache invalidation logic?"
Q18 | Who most recently modified a file (latest owner) | "Who last touched this file?"
Q19 | Who has modified a file most frequently (primary owner) | "Who owns the search indexer?"
Q20 | Who to contact about an unfamiliar part of the codebase | "Who would know about the billing module?"
Q21 | Which files or classes have changed recently | "What has changed in the last two weeks?"
Q22 | Which API methods have been added, changed or removed | "What API changes broke my integration?"
Q23 | Which file or class has the most changes | "What is the most actively changed part of the codebase?"
Q24 | Which code the asker worked on uses a specific pattern | "Where else in my code am I using this utility function?"
Q25 | Which code related to the asker has changed recently | "What changed recently that might affect my feature?"
Q26 | How recent changes affect something the asker is building | "Will the new auth changes break what I am working on?"
Q27 | What code is related to or affected by a specific change | "What else might be affected by this database schema change?"

WORK ITEM PROGRESS
Q28 | What recent activity has happened on a specific issue or task | "What is the latest on issue #4821?"
Q29 | Which features or functions have been actively changing | "What parts of the product are being actively developed?"
Q30 | Whether blocking issues in a milestone have been resolved | "Are the P0 blockers for the v3 release fixed yet?"
Q31 | Whether work is progressing on planned items | "Is anyone making progress on the offline mode feature?"

BROKEN BUILDS
Q32 | What change or commit caused a build or test to fail | "What broke the nightly build?"
Q33 | Who is responsible for breaking a build | "Who broke CI?"
Q34 | Who most recently changed a failing test | "Who last touched the test that is failing?"
Q35 | Which specific changes caused test failures | "Which commits caused the integration tests to fail?"

TEST CASES
Q36 | Who owns or is responsible for a specific test | "Who owns the end-to-end login test?"
Q37 | How tests relate to specific packages or classes | "Which tests cover the payment module?"

EXTERNAL REFERENCES (possibly obsolete)
Q38 | Whether an API changed according to external documentation | "Did the Stripe API change their webhook format?"
Q39 | Whether an external forum post is relevant to a specific class | "Is this Stack Overflow post about our codebase?"
Q40 | What the team has planned for the coming period | "What is the team working on next week?"
Q41 | What a person is supposed to be working on per a plan | "What is on my plate according to the roadmap?"

ORGANIZATIONAL & SOCIAL
Q42 | How the team or project is structured | "How is the frontend team organized?"
Q43 | Who has made changes to a specific bug or defect | "Who has been working on this defect?"
Q44 | Who has commented on a specific defect | "Who has been involved in this bug discussion?"
Q45 | What the collaboration pattern around a feature looks like | "Who has been involved in the search feature?"
Q46 | Which discussions or threads mention the asker | "Where has someone mentioned me in issues?"

PULL REQUESTS
Q47 | Who should review a specific PR based on expertise and load | "Who should I request review from for this PR?"
Q48 | Why a PR was merged or rejected | "Why was PR #892 closed without merging?"
Q49 | Which PRs are blocking an issue from being resolved | "What PRs need to land before this issue can close?"
Q50 | How long PR review typically takes in an area | "How long does it usually take to get a review on core changes?"
Q51 | Which PRs have been waiting the longest without review | "Which PRs are most stale?"
Q52 | Which bugs a PR is likely to fix | "Will this PR fix the memory leak issue?"

BUG MANAGEMENT
Q53 | Whether a bug has been reported before (duplicate detection) | "Has anyone else reported this crash on startup?"
Q54 | Who should be assigned to triage or fix a bug | "Who should I assign this performance regression to?"
Q55 | Which file or component is most likely responsible for a bug | "Where in the codebase is this null pointer coming from?"
Q56 | Which commit introduced a regression | "Which change caused this to stop working?"
Q57 | The severity or priority of a bug relative to others | "How critical is this compared to other open bugs?"
Q58 | Which bugs are related without being duplicates | "Are there other bugs related to this authentication issue?"
Q59 | How long bugs in an area typically take to fix | "How long do performance bugs usually take to resolve?"
Q60 | The full history and lifecycle of a bug | "Can someone summarize the history of this issue?"

CI/CD
Q61 | Whether a test failure is flaky or a real regression | "Is this test actually broken or is it flaky?"
Q62 | Which CI stage or step is the bottleneck | "Why does our CI take so long?"
Q63 | How often a component causes build failures | "How reliable is the networking module?"
Q64 | Which contributor's changes most frequently break CI | "Who keeps breaking the build?"

SECURITY & QUALITY
Q65 | Whether a change introduces a known vulnerability | "Does this dependency update introduce any CVEs?"
Q66 | Which dependencies have known vulnerabilities | "Are any of our dependencies flagged in the latest advisory?"
Q67 | Which parts of the codebase have low test coverage | "What areas need more tests?"
Q68 | Whether a patch follows security or style conventions | "Does this fix follow our security guidelines?"

ONBOARDING
Q69 | Where to start contributing to a specific component | "I want to help with the compiler — where do I start?"
Q70 | What the unwritten conventions of the codebase are | "What do I need to know that is not in the docs?"
Q71 | Which issues are suitable for new contributors | "What are good first issues for someone new to the project?"
Q72 | What the contribution workflow looks like end to end | "How do I get a change merged into this project?"

CROSS-ARTIFACT SYNTHESIS
Q73 | Given a stack trace, which recent commits are suspicious | "Here is a crash trace — which recent change could have caused this?"
Q74 | Which developer has the most context on a specific bug | "Who knows the most about this long-running issue?"
Q75 | Which open bugs are likely to recur based on patterns | "Are there bugs that keep coming back in this area?"
Q76 | Why a PR was reverted given the full project context | "Why was this PR reverted right after merging?"
Q77 | Which changes historically co-occur with bugs in an area | "What kinds of changes tend to introduce bugs here?"
Q78 | What the blast radius of a change to a file would be | "If I change this interface, what else breaks?"

NONE | The thread does not contain a clear developer question and answer matching any category above
"""

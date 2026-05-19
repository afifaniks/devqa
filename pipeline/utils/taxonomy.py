# ── Single source of truth for taxonomy ──────────────────────────────────────
# Imported by: classification/classify.py, review_ui/app.py (/api/taxonomy)
#
# Source: Fritz & Murphy, "Using Information Fragments to Answer the Questions
# Developers Ask," Proc. ICSE 2010, pp. 175–184. The 78 questions and 7
# categories below are taken directly from F&M's Table 1, preserving the
# original phrasing.
#
# Two additional classification options are appended:
#   H  (OTHER) — the thread contains a relevant developer information need
#                that does not fit any F&M category and needs human insight.
#   N  (NONE)  — the thread does not contain a valid developer information need.

CATEGORIES: dict[str, tuple[str, list[str]]] = {
    "A": (
        "Who is working on what (people specific)",
        ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10", "Q11", "Q12"],
    ),
    "B": (
        "Changes to the code (code specific)",
        [
            "Q13", "Q14", "Q15", "Q16", "Q17", "Q18", "Q19", "Q20", "Q21",
            "Q22", "Q23", "Q24", "Q25", "Q26", "Q27", "Q28", "Q29", "Q30",
            "Q31", "Q32", "Q33", "Q34", "Q35", "Q36", "Q37", "Q38", "Q39",
            "Q40", "Q41", "Q42", "Q43", "Q44", "Q45", "Q46", "Q47",
        ],
    ),
    "C": (
        "Work item progress",
        ["Q48", "Q49", "Q50", "Q51", "Q52", "Q53", "Q54", "Q55", "Q56", "Q57", "Q58"],
    ),
    "D": (
        "Broken builds",
        ["Q59", "Q60", "Q61", "Q62", "Q63"],
    ),
    "E": (
        "Test cases",
        ["Q64", "Q65", "Q66", "Q67"],
    ),
    "F": (
        "References on the web",
        ["Q68", "Q69", "Q70", "Q71", "Q72"],
    ),
    "G": (
        "Other questions",
        ["Q73", "Q74", "Q75", "Q76", "Q77", "Q78"],
    ),
    # ── Extra options ────────────────────────────────────────────────────────
    "H": (
        "Relevant question outside F&M (needs human insight)",
        ["OTHER"],
    ),
    "N": (
        "Not a valid developer information need",
        ["NONE"],
    ),
}

QUESTIONS: dict[str, str] = {
    # ── A. Who is working on what (people specific) ──────────────────────────
    "Q1":  "Who is working on what?",
    "Q2":  "What are they (coworkers) working on right now?",
    "Q3":  "What have other people been working on?",
    "Q4":  "How much work have people done?",
    "Q5":  "Who changed this code? (person-focused)",
    "Q6":  "Who to assign a code review to? / Who has the knowledge to do the code review?",
    "Q7":  "What have people done lately?",
    "Q8":  "Who is working on what at the moment?",
    "Q9":  "What has a particular team member been doing?",
    "Q10": "What have people been working on?",
    "Q11": "Which code reviews have been assigned to which person?",
    "Q12": "Who to assign a code review to? / Who has time for a code review?",

    # ── B. Changes to the code (code specific) ───────────────────────────────
    "Q13": "What is the evolution of the code?",
    "Q14": "Why were these changes introduced?",
    "Q15": "Who made a particular change and why?",
    "Q16": "What classes has my team been working on?",
    "Q17": "What are the changes on newly resolved work items related to me?",
    "Q18": "Who is working on the same classes as I am, and for which work item?",
    "Q19": "Who changed this code? (code-focused)",
    "Q20": "What is the whole history of this file?",
    "Q21": "What has been happening on this class?",
    "Q22": "What have people changed lately?",
    "Q23": "What changes have been made and why?",
    "Q24": "What has changed between two builds, and who has changed it?",
    "Q25": "Who has made changes to my classes?",
    "Q26": "Who is using that API that I am about to change?",
    "Q27": "Who created the API that I am about to change?",
    "Q28": "Who owns this piece of code? / Who modified it the latest?",
    "Q29": "Who owns this piece of code? / Who modified it most?",
    "Q30": "Who to talk to if you have to work with packages you haven't worked with?",
    "Q31": "How much has changed in the project code?",
    "Q32": "Is anyone intending to commit anything to that class?",
    "Q33": "Where have changes been made related to you?",
    "Q34": "Who is responsible for this code? (Who made the latest change?)",
    "Q35": "Which team is responsible for this code? (Who has made most changes to the code?)",
    "Q36": "What classes have been changed?",
    "Q37": "Which API has changed (to see which methods are not supported any more)?",
    "Q38": "What's the most popular class? / Which class has been changed most?",
    "Q39": "Which other code that I worked on uses this code pattern or utility function?",
    "Q40": "Which code has recently changed that is related to me?",
    "Q41": "How do recently delivered changes affect changes that I am working on?",
    "Q42": "What code is related to a change?",
    "Q43": "Where has code been changing this week?",
    "Q44": "Which classes have been changed between two builds?",
    "Q45": "What is going on in a package?",
    "Q46": "Which changes have been made between these days or after this day?",
    "Q47": "What classes in this component were modified since version [X]?",

    # ── C. Work item progress ────────────────────────────────────────────────
    "Q48": "What is the recent activity on a plan item?",
    "Q49": "Which features and functions have been changing?",
    "Q50": "Has progress been made on blockers (blocking work items) in your milestone?",
    "Q51": "Which work items / plan items are most active?",
    "Q52": "How active is the plan item? (How many comments were made on related work items?)",
    "Q53": "Are there any new comments on interesting work items?",
    "Q54": "What work item has recently changed that is related to me?",
    "Q55": "What are the emails related to line items and defects that are features?",
    "Q56": "What are the comments on newly resolved work items that are related to me?",
    "Q57": "Is progress (changes) being made on plan items?",
    "Q58": "What is the activity on a line item (feature)?",

    # ── D. Broken builds ─────────────────────────────────────────────────────
    "Q59": "What caused this build to break? (Which change caused the stack trace?)",
    "Q60": "What has caused this build to break? (Look at the stack trace and intersect with change sets.)",
    "Q61": "Who caused this build to break? (Who owns the broken tests?)",
    "Q62": "Who changed the test case most recently that caused the build to fail?",
    "Q63": "Which changes caused the tests to fail and thus the build to break?",

    # ── E. Test cases ────────────────────────────────────────────────────────
    "Q64": "Who owns a test case? (Who resolved the last work item that fixed the test case?)",
    "Q65": "Who is responsible for a failing test case? (stack trace)",
    "Q66": "How do test cases relate to work items?",
    "Q67": "How do test cases relate to packages / classes?",

    # ── F. References on the web ─────────────────────────────────────────────
    "Q68": "Which API has changed? (Check on the web site.)",
    "Q69": "Is an entry in a newsgroup / forum addressed to me because of the class mentioned?",
    "Q70": "What is coming up next week for my team? / What is my team doing?",
    "Q71": "What am I supposed to work on? (plan on wiki)",
    "Q72": "Who has to do what? (team activity)",

    # ── G. Other questions ───────────────────────────────────────────────────
    "Q73": "How is the team organized?",
    "Q74": "Who has made changes to a defect?",
    "Q75": "Who has made comments in a defect?",
    "Q76": "What is the collaboration tree around a feature?",
    "Q77": "Which conversations in work items have I been mentioned in?",
    "Q78": "What are people commenting on all work items I am involved with?",

    # ── Extra options ────────────────────────────────────────────────────────
    "OTHER": "A relevant developer information need that does not match any F&M category — needs human insight.",
    "NONE":  "Does not contain a valid developer information need.",
}

# ── LLM prompt string (derived from the dicts above) ─────────────────────────

TAXONOMY_FOR_PROMPT = """
You must classify the thread into exactly one of these question IDs. Use OTHER
if the thread contains a relevant developer information need that does not
match any F&M question, and NONE if the thread does not contain a valid
developer information need at all.

Each entry shows: ID | F&M question text | example phrasing

A. WHO IS WORKING ON WHAT (people specific)
Q1  | Who is working on what?                                                       | "Who's currently looking into the auth bug?"
Q2  | What are they (coworkers) working on right now?                               | "What is @jsmith working on this sprint?"
Q3  | What have other people been working on?                                       | "What has the platform team been doing lately?"
Q4  | How much work have people done?                                               | "How many issues has @mwong closed this month?"
Q5  | Who changed this code? (person-focused)                                       | "Who changed the authentication module?"
Q6  | Who to assign a code review to? / Who has the knowledge to do the review?    | "Who knows this code well enough to review this PR?"
Q7  | What have people done lately?                                                 | "What landed in the last two weeks?"
Q8  | Who is working on what at the moment?                                         | "Is anyone actively working on the dark mode issue?"
Q9  | What has a particular team member been doing?                                 | "What has @agarcia been doing lately?"
Q10 | What have people been working on?                                             | "Summary of the team's work recently?"
Q11 | Which code reviews have been assigned to which person?                        | "What reviews are in @agarcia's queue?"
Q12 | Who to assign a code review to? / Who has time for a code review?            | "Who has bandwidth to review this PR today?"

B. CHANGES TO THE CODE (code specific)
Q13 | What is the evolution of the code?                                            | "How did the rendering pipeline get to this state?"
Q14 | Why were these changes introduced?                                            | "Why was this config option removed in v2.3?"
Q15 | Who made a particular change and why?                                         | "Who changed the retry logic and why?"
Q16 | What classes has my team been working on?                                     | "What files has the infra team touched this week?"
Q17 | What are the changes on newly resolved work items related to me?              | "What code changed in the issues closed last week that affect the API I own?"
Q18 | Who is working on the same classes as I am, and for which work item?         | "Anyone else editing the storage module — and on what issue?"
Q19 | Who changed this code? (code-focused)                                         | "Which commits modified VideoPlayer.js?"
Q20 | What is the whole history of this file?                                       | "Show me the full git history of this file."
Q21 | What has been happening on this class?                                        | "Any recent activity on the AuthManager class?"
Q22 | What have people changed lately?                                              | "What files were modified recently?"
Q23 | What changes have been made and why?                                          | "What changed in the last release and what motivated it?"
Q24 | What has changed between two builds, and who has changed it?                  | "What's different between build 482 and 483 and who did it?"
Q25 | Who has made changes to my classes?                                           | "Who has touched the files I maintain?"
Q26 | Who is using that API that I am about to change?                              | "Who uses the sendNotification() method?"
Q27 | Who created the API that I am about to change?                                | "Who wrote the original cache invalidation logic?"
Q28 | Who owns this piece of code? / Who modified it the latest?                    | "Who last touched this file?"
Q29 | Who owns this piece of code? / Who modified it most?                          | "Who has done the most work on the search indexer?"
Q30 | Who to talk to if you have to work with packages you haven't worked with?    | "Who would know about the billing module?"
Q31 | How much has changed in the project code?                                     | "How much code has changed in the last month?"
Q32 | Is anyone intending to commit anything to that class?                         | "Anyone planning changes to PaymentProcessor soon?"
Q33 | Where have changes been made related to you?                                  | "Where in the code have my files been touched recently?"
Q34 | Who is responsible for this code? (Who made the latest change?)               | "Who's the latest modifier of this file?"
Q35 | Which team is responsible for this code? (Who has made most changes?)        | "Which team owns the indexing subsystem?"
Q36 | What classes have been changed?                                               | "Which classes have been modified this week?"
Q37 | Which API has changed (to see which methods are not supported any more)?     | "Which API methods were removed in this release?"
Q38 | What's the most popular class? / Which class has been changed most?           | "What is the most actively edited part of the codebase?"
Q39 | Which other code that I worked on uses this code pattern or utility?          | "Where else in my code am I using this utility function?"
Q40 | Which code has recently changed that is related to me?                        | "What changed recently that affects what I own?"
Q41 | How do recently delivered changes affect changes that I am working on?        | "Will the new auth changes break what I am working on?"
Q42 | What code is related to a change?                                             | "What files are affected by this PR?"
Q43 | Where has code been changing this week?                                       | "Where in the repo has activity been this week?"
Q44 | Which classes have been changed between two builds?                           | "What files were changed between v1.2 and v1.3?"
Q45 | What is going on in a package?                                                | "What is the current state of the auth/ package?"
Q46 | Which changes have been made between these days or after this day?           | "What was committed between May 1 and May 10?"
Q47 | What classes in this component were modified since version [X]?              | "What changed in the database package since v2.0?"

C. WORK ITEM PROGRESS
Q48 | What is the recent activity on a plan item?                                   | "What's the latest on issue #4821?"
Q49 | Which features and functions have been changing?                              | "What parts of the product are being actively developed?"
Q50 | Has progress been made on blockers in your milestone?                         | "Are the P0 blockers for the v3 release fixed yet?"
Q51 | Which work items / plan items are most active?                                | "Which issues have the most activity right now?"
Q52 | How active is the plan item? (How many comments?)                             | "How busy is this issue — many comments?"
Q53 | Are there any new comments on interesting work items?                         | "Anything new on the issues I'm watching?"
Q54 | What work item has recently changed that is related to me?                    | "Which of my issues had activity today?"
Q55 | What are the emails related to line items and defects that are features?      | "Which emails relate to the open feature defects?"
Q56 | What are the comments on newly resolved work items that are related to me?    | "What did people say about my recently closed issues?"
Q57 | Is progress (changes) being made on plan items?                               | "Is anyone making progress on the offline mode feature?"
Q58 | What is the activity on a line item (feature)?                                | "What's been happening on the new export feature?"

D. BROKEN BUILDS
Q59 | What caused this build to break? (Which change caused the stack trace?)      | "What change broke the nightly build?"
Q60 | What has caused this build to break? (stack trace × change sets)              | "Cross-referencing the failing trace and recent commits — what broke it?"
Q61 | Who caused this build to break? (Who owns the broken tests?)                  | "Whose change broke CI? Who owns the failing tests?"
Q62 | Who changed the test case most recently that caused the build to fail?       | "Who last touched the test that is failing?"
Q63 | Which changes caused the tests to fail and thus the build to break?           | "Which commits introduced the integration test failures?"

E. TEST CASES
Q64 | Who owns a test case? (Who resolved the last work item that fixed it?)        | "Who is responsible for the end-to-end login test?"
Q65 | Who is responsible for a failing test case? (stack trace)                     | "Given this trace, whose code is at fault for the failing test?"
Q66 | How do test cases relate to work items?                                       | "Which issues are linked to this test?"
Q67 | How do test cases relate to packages / classes?                               | "Which tests cover the payment module?"

F. REFERENCES ON THE WEB
Q68 | Which API has changed? (check on web site)                                    | "Did the Stripe API change their webhook format?"
Q69 | Is an entry in a newsgroup / forum addressed to me because of the class?     | "Is this Stack Overflow post about my code?"
Q70 | What is coming up next week for my team? / What is my team doing?            | "What's on the team's plate next week?"
Q71 | What am I supposed to work on? (plan on wiki)                                 | "What's on my plate per the roadmap?"
Q72 | Who has to do what? (team activity)                                           | "Who's responsible for which milestone item?"

G. OTHER QUESTIONS
Q73 | How is the team organized?                                                    | "How is the frontend team organized?"
Q74 | Who has made changes to a defect?                                             | "Who's worked on this bug?"
Q75 | Who has made comments in a defect?                                            | "Who has been involved in this bug discussion?"
Q76 | What is the collaboration tree around a feature?                              | "Who has been involved in the search feature?"
Q77 | Which conversations in work items have I been mentioned in?                   | "Where has someone @-mentioned me in issues?"
Q78 | What are people commenting on all work items I am involved with?              | "What's being said on the issues I'm part of?"

EXTRA OPTIONS
OTHER | A relevant developer information need that does NOT match any F&M question above. Use this when the thread is genuinely about the development process but the question type is not captured by Q1–Q78. These cases need human insight.
NONE  | The thread does not contain a valid developer information need. Use this for bug reports, feature requests, usage questions, rhetorical questions, or threads where there is no clear question / answer pair about the development process.
"""

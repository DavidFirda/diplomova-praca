# AdaptPy – student guide

AdaptPy is a web application for practising Python programming. It adapts to the student's level. The menu is on the left (on mobile behind the menu icon at the top).

## Dashboard (/dashboard)
The start page after signing in. Cards: Pretest, Tasks (topic mastery, solved tasks, task in progress), Exercises (progress), Tests, Statistics, Profile, Feedback. This assistant is in the bottom right corner.

## Pretest (/predtest)
An initial test that finds out the student's level in each topic (category). It is taken only once; an unfinished pretest continues where the student stopped. Tasks and Tests unlock after the pretest. After it is finished, the pretest disappears from the menu.

## Tasks (/ulohy) – self-study
- The system (adaptive POMDP algorithm) keeps choosing tasks from topics the student has not mastered yet.
- The student writes code in the editor and clicks "Submit". The code is run and its output compared.
- Each task has 5 attempts. After a wrong answer the student sees what is wrong and fixes the code alone. After the 5th wrong attempt the correct solution is shown and the task counts as not solved.
- The AI assistant in Tasks is available from the start: it explains concepts and errors but never gives the full solution.
- Hints ("Give me a hint" button): at most 3 per task, unlocked gradually – each next hint only after another wrong attempt. Hint 1 shows where the mistake is, hint 2 explains all mistakes and the logic, hint 3 shows the structure (skeleton) of the code.
- Every hint lowers the task score: no hint 100 %, 1 hint 75 %, 2 hints 50 %, 3 hints 25 %. It also affects which tasks come next and topic mastery.
- Pasting text from outside into the editor is blocked (originality check). The system watches how the code is typed; with unusual typing the student confirms how the code was written.
- "Topic mastery" on the dashboard shows per-topic percentages based on tests and tasks.

## Exercises (/cvicenia)
- Interactive notebooks (like Jupyter) for the course labs: text with instructions and code cells.
- One at a time: the next exercise unlocks after the previous one is finished.
- "Run" runs a cell; cells above it run together with it (variables are kept). Each cell has a time limit.
- "＋ Add cell here" adds the student's own scratch cell (not counted in progress).
- Progress in percent = share of successfully run cells. When all are done, "I'm done" finishes the exercise.
- The exercise can be downloaded as .ipynb.
- On the right is the exercise assistant: it explains the topic using the lectures, guides and gives a solution skeleton. It can insert code into a cell, but only after the student confirms it and picks the cell.

## Tests (/hlavnytest)
Adaptive tests – questions are chosen according to the student's performance. They can be taken repeatedly. Available after the pretest and only if the teacher enables them.

## Statistics (/analyza)
Overview of results: number of correct answers, accuracy, percentile and pretest results per category.

## Materials (/materialy)
Lectures and books of the course to download – only those the teacher made available.

## Profile (/profile)
Edit name, surname and email; change the password via "Change password". A forgotten password is reset on the sign-in page via "Forgot your password?" (an email is sent).

## Feedback (/feedback-form) and Questionnaire (/feedback)
The feedback form (idea, bug, praise) is available at any time. The questionnaire appears in the menu when the teacher publishes it.

## Language and theme
The SK/EN switch and light/dark theme are in the top right corner.

## Course page
"Course page" in the menu leads to the course GitHub with the labs.

# ============================================================
# AdaptPy - spoločná logika predtestu a hlavného testu.
#
#  - pevný zoznam otázok predtestu (je na serveri, klient ho nemôže meniť),
#  - kto je práve na rade: predtest sa odvodzuje zo StudentAnswer, hlavný
#    test z TestProgress  ->  get_turn(),
#  - stavový automat jednej otázky (transitions)  ->  QuestionFlow,
#  - zámok na študenta (viac súbežných requestov jedného študenta sa serializuje),
#  - výber otázky / aktualizácia selektora podľa stratégie študenta.
#
# Nič tu nie je uložené v pamäti procesu, takže stav prežije reštart aj beh
# na viacerých gunicorn workeroch.
# ============================================================
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from transitions import Machine

from algorithms.pomdp_selector import POMDPQuestionSelector
from algorithms.q_selector import QLearningQuestionSelector
from algorithms.random_selector import RandomQuestionSelector
from models import db, Student, Question, StudentAnswer, TestProgress, AnswerAttempt
from services.extract_starter_code import extract_starter_code

# Pevný zoznam otázok predtestu (poradie sa zachováva).
PRETEST_QUESTION_IDS = [1, 4, 11, 7, 47, 50, 2, 5, 20, 2635, 15, 23]

MAIN_TEST_TOTAL = 30
TEST_CATEGORIES = ["Data Structures", "Syntax", "Sorting", "Scientific Computing"]

# Po prvej nesprávnej odpovedi má študent jednu opravu.
MAX_RETRIES = 1


# ------------------------------------------------------------
# Zámok na študenta
# ------------------------------------------------------------
def lock_student(student_id):
    """
    Riadkový zámok (do konca transakcie) na študenta. Všetky zápisy testu jedného
    študenta (odpoveď, výber ďalšej otázky) tak prebiehajú po jednom - dvojklik,
    dve karty alebo dva workery nevytvoria duplicitné odpovede ani dve rôzne
    "aktuálne" otázky. Rôzni študenti sa nijako neblokujú.
    (FOR NO KEY UPDATE neblokuje vkladanie riadkov s cudzím kľúčom na študenta.)
    """
    db.session.execute(
        select(Student.id).where(Student.id == student_id).with_for_update(key_share=True)
    )


# ------------------------------------------------------------
# Stavový automat jednej otázky
#
#   open  --wrong (je oprava)-->  retry  --wrong (je oprava)-->  retry
#   open/retry --wrong (bez opravy)--> closed
#   open/retry --correct------------>  closed
#
# open = otázka čaká na prvú odpoveď, retry = študent už raz chyboval a môže
# to opraviť, closed = výsledok je konečný (zapíše sa do DB).
# ------------------------------------------------------------
class QuestionFlow:
    states = ["open", "retry", "closed"]

    def __init__(self, retries_used=0, max_retries=MAX_RETRIES):
        self.retries_used = retries_used
        self.max_retries = max_retries
        Machine(
            model=self,
            states=self.states,
            initial="retry" if retries_used else "open",
            auto_transitions=False,
            transitions=[
                {"trigger": "correct", "source": ["open", "retry"], "dest": "closed"},
                {"trigger": "wrong", "source": ["open", "retry"], "dest": "retry",
                 "conditions": "has_retry_left", "after": "use_retry"},
                {"trigger": "wrong", "source": ["open", "retry"], "dest": "closed"},
            ],
        )

    def has_retry_left(self):
        return self.retries_used < self.max_retries

    def use_retry(self):
        self.retries_used += 1


# ------------------------------------------------------------
# Stratégia výberu (podľa ID študenta - pevné priradenie do skupín)
# ------------------------------------------------------------
def strategy_for(student_id):
    return ("pomdp", "random", "q_learning")[int(student_id) % 3]


def build_selector(student_id, test_session, excluded_ids=None):
    """
    Nový selektor pre študenta. Nekešuje sa v pamäti - Q-learning aj POMDP si
    stav ukladajú do súborov a pri vytvorení ho načítajú. Volať len pod
    zámkom študenta (lock_student), aby sa súbory nepísali súbežne.
    """
    strategy = strategy_for(student_id)
    excluded_ids = list(excluded_ids or [])
    if strategy == "random":
        return RandomQuestionSelector(TEST_CATEGORIES, excluded_ids)
    selector_class = QLearningQuestionSelector if strategy == "q_learning" else POMDPQuestionSelector
    return selector_class(
        student_id=int(student_id),
        categories=TEST_CATEGORIES,
        test_session=test_session,
        excluded_ids=excluded_ids,
    )


def update_selector(student_id, test_session, question_id, category, correct):
    """Odovzdá výsledok odpovede selektoru (Random sa neučí)."""
    if strategy_for(student_id) == "random" or not category:
        return
    build_selector(student_id, test_session).update_after_answer(
        question_id=question_id, category=category, correct=correct,
    )


# ------------------------------------------------------------
# Opravy na otázku (perzistentné)
# ------------------------------------------------------------
def _attempt_row(student_id, test_type, test_session, question_id):
    return AnswerAttempt.query.filter_by(
        student_id=student_id, test_type=test_type,
        test_session=test_session or "", question_id=question_id,
    ).first()


def get_retries_used(student_id, test_type, test_session, question_id):
    row = _attempt_row(student_id, test_type, test_session, question_id)
    return row.attempts if row else 0


def set_retries_used(student_id, test_type, test_session, question_id, value):
    """Uloží počet použitých opráv (commit robí volajúci, pod zámkom študenta)."""
    row = _attempt_row(student_id, test_type, test_session, question_id)
    if row is None:
        row = AnswerAttempt(
            student_id=student_id, test_type=test_type,
            test_session=test_session or "", question_id=question_id,
        )
        db.session.add(row)
    row.attempts = value


def clear_attempts(student_id, test_type, test_session=None):
    """Zmaže opravy (pri admin zmazaní testu). test_session=None -> všetky danej úrovne."""
    q = AnswerAttempt.query.filter_by(student_id=student_id, test_type=test_type)
    if test_session is not None:
        q = q.filter_by(test_session=test_session)
    q.delete()


# ------------------------------------------------------------
# Kto je na rade
# ------------------------------------------------------------
@dataclass
class Turn:
    test_type: str
    test_session: str | None            # None = predtest
    expected_question_id: int | None    # otázka, na ktorú sa momentálne odpovedá
    answered: set = field(default_factory=set)
    progress: TestProgress | None = None

    def status_of(self, question_id):
        """'answered' (už uzavretá) | 'current' (je na rade) | 'not_current'."""
        if question_id in self.answered:
            return "answered"
        if question_id == self.expected_question_id:
            return "current"
        return "not_current"


def answered_question_ids(student_id, test_type, test_session=None):
    rows = db.session.query(StudentAnswer.question_id).filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.test_type == test_type,
        StudentAnswer.test_session == test_session,   # None -> IS NULL (predtest)
    ).distinct()
    return {row[0] for row in rows}


def get_turn(student_id, test_type):
    if test_type == "predtest":
        answered = answered_question_ids(student_id, "predtest")
        expected = next((q for q in PRETEST_QUESTION_IDS if q not in answered), None)
        return Turn("predtest", None, expected, answered)

    prog = active_main_progress(student_id)
    if prog is None:
        return Turn("main", None, None)
    return Turn("main", prog.test_session, prog.current_question_id,
                answered_question_ids(student_id, "main", prog.test_session), prog)


# ------------------------------------------------------------
# Predtest
# ------------------------------------------------------------
def pretest_state(student_id):
    """
    {total, answered, done, next_question_id}
    Predtest je hotový, až keď sú zodpovedané všetky otázky. Rozpracovaný
    predtest pokračuje prvou ešte nezodpovedanou otázkou v pevnom poradí.
    """
    turn = get_turn(student_id, "predtest")
    total = len(PRETEST_QUESTION_IDS)
    return {
        "total": total,
        "answered": min(len(turn.answered), total),
        "done": turn.expected_question_id is None,
        "next_question_id": turn.expected_question_id,
    }


# ------------------------------------------------------------
# Hlavný test
# ------------------------------------------------------------
def active_main_progress(student_id):
    return (TestProgress.query
            .filter_by(student_id=student_id, test_type="main", status="in_progress")
            .order_by(TestProgress.id.desc())
            .first())


def _next_main_session_name(student_id):
    names = {r[0] for r in db.session.query(TestProgress.test_session)
             .filter_by(student_id=student_id, test_type="main")}
    names |= {r[0] for r in db.session.query(StudentAnswer.test_session)
              .filter_by(student_id=student_id, test_type="main").distinct() if r[0]}
    numbers = [int(m.group(1)) for n in names if (m := re.fullmatch(r"main-(\d+)", n))]
    return f"main-{max(numbers, default=0) + 1}"


def start_main_progress(student_id):
    prog = TestProgress(
        student_id=student_id, test_type="main",
        test_session=_next_main_session_name(student_id),
        total_questions=MAIN_TEST_TOTAL, status="in_progress",
    )
    db.session.add(prog)
    db.session.flush()
    return prog


def clear_main_progress(student_id, test_session):
    TestProgress.query.filter_by(
        student_id=student_id, test_type="main", test_session=test_session
    ).delete()


# ------------------------------------------------------------
# Otázky
# ------------------------------------------------------------
def question_payload(question, **extra):
    data = {
        "id": question.id,
        "instruction": question.instruction,
        "input_data": question.input_data,
        "category": question.category,
        "starter_code": extract_starter_code(question.output),
    }
    data.update(extra)
    return data


def get_question(question_id):
    return db.session.get(Question, question_id)

# ============================================================
# AdaptPy - nastavenia aplikácie uložené v DB (tabuľka app_settings).
# Zdieľané medzi všetkými workermi, prežijú reštart.
# ============================================================
from models import db, AppSetting

QUESTIONNAIRE_KEY = "questionnaire_published"


def get_setting(key, default=""):
    row = db.session.get(AppSetting, key)
    return row.value if row else default


def set_setting(key, value):
    """Uloží hodnotu a commitne (volá sa len z admin endpointov)."""
    row = db.session.get(AppSetting, key)
    if row is None:
        db.session.add(AppSetting(key=key, value=str(value)))
    else:
        row.value = str(value)
    db.session.commit()


def questionnaire_published():
    """Dotazník je predvolene SKRYTÝ, kým ho admin nezverejní."""
    return get_setting(QUESTIONNAIRE_KEY, "false") == "true"


def set_questionnaire_published(published):
    set_setting(QUESTIONNAIRE_KEY, "true" if published else "false")

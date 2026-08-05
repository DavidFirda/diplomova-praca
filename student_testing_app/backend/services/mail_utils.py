"""
Utilita na odosielanie emailov cez SMTP (napr. Gmail) pre aplikáciu AdaptPy.

Režimy:
  - PRODUKČNÝ: ak je v .env nastavený MAIL_SERVER (+ prihlasovacie údaje),
    email sa reálne odošle cez daný SMTP server.
  - DEV (fallback): ak MAIL_SERVER nie je nastavený, email sa neodošle,
    len sa jeho obsah vypíše do konzoly backendu (docker compose logs backend).
    Umožňuje testovať flow "zabudnuté heslo" bez reálneho SMTP účtu.

Emaily sa odosielajú ASYNCHRÓNNE na pozadí (v samostatnom vlákne), aby
HTTP request (napr. /forgot-password) odpovedal okamžite a nezávisel od
rýchlosti SMTP servera. To zároveň znemožňuje útočníkovi merať čas odpovede
a odhadovať, či daný email v systéme existuje.

Všetky citlivé údaje (heslo/App Password) sa čítajú z prostredia (.env),
NIKDY nie sú v kóde ani v gite.
"""
import os
import ssl
import smtplib
import logging
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

logger = logging.getLogger("mail")


def _mail_configured() -> bool:
    """Produkčný režim je aktívny, len ak je nastavený SMTP server aj heslo."""
    return bool(os.getenv("MAIL_SERVER") and os.getenv("MAIL_PASSWORD"))


def _dev_print(to_email: str, subject: str, text_body: str) -> None:
    logger.info("[DEV MAIL] to=%s subject=%s", to_email, subject)
    print(
        "\n===== [DEV MAIL - SMTP nie je nastavený] =====\n"
        f"Komu: {to_email}\nPredmet: {subject}\n\n{text_body}\n"
        "==============================================\n",
        flush=True,
    )


def _send_smtp(to_email: str, subject: str, text_body: str, html_body: str | None) -> bool:
    """Samotné odoslanie cez SMTP. Beží na pozadí. Nikdy nevyhadzuje výnimku."""
    mail_server = os.getenv("MAIL_SERVER")
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"     # STARTTLS na porte 587
    mail_use_ssl = os.getenv("MAIL_USE_SSL", "false").lower() == "true"    # SSL na porte 465
    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    mail_sender = os.getenv("MAIL_DEFAULT_SENDER", mail_username)
    mail_sender_name = os.getenv("MAIL_SENDER_NAME", "AdaptPy")

    from_header = formataddr((mail_sender_name, mail_sender))

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_header
        msg["To"] = to_email
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        context = ssl.create_default_context()

        if mail_use_ssl:
            # Priame SSL spojenie (typicky port 465)
            with smtplib.SMTP_SSL(mail_server, mail_port, timeout=15, context=context) as server:
                server.login(mail_username, mail_password)
                server.sendmail(mail_sender, [to_email], msg.as_string())
        else:
            # Plain spojenie + upgrade na TLS cez STARTTLS (typicky port 587)
            with smtplib.SMTP(mail_server, mail_port, timeout=15) as server:
                server.ehlo()
                if mail_use_tls:
                    server.starttls(context=context)
                    server.ehlo()
                server.login(mail_username, mail_password)
                server.sendmail(mail_sender, [to_email], msg.as_string())

        logger.info("Email odoslaný na %s", to_email)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP autentifikácia zlyhala. Skontroluj MAIL_USERNAME a MAIL_PASSWORD "
            "(pri Gmaile musí ísť o App Password, nie bežné heslo)."
        )
        return False
    except Exception:
        logger.exception("Odoslanie emailu zlyhalo (to=%s)", to_email)
        return False


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    """
    Zaradí email na odoslanie. Vracia okamžite (fire-and-forget).

    - V DEV režime (bez SMTP) vypíše obsah do konzoly synchrónne.
    - V produkčnom režime spustí odoslanie na pozadí vo vlákne (daemon),
      takže volajúci HTTP request neblokuje a neprezrádza časom, či email existuje.
    """
    if not _mail_configured():
        _dev_print(to_email, subject, text_body)
        return

    thread = threading.Thread(
        target=_send_smtp,
        args=(to_email, subject, text_body, html_body),
        daemon=True,
    )
    thread.start()

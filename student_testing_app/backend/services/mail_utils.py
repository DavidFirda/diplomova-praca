"""
Jednoduchá utilita na odosielanie emailov.

Ak nie sú v prostredí nastavené SMTP údaje (MAIL_SERVER), appka beží v DEV
režime: email sa neodošle reálne, ale link/obsah sa vypíše do konzoly
backendu (docker compose logs backend). Toto umožňuje vyvíjať a testovať
flow "zabudnuté heslo" bez toho, aby si musel mať hneď reálny SMTP účet.

Pre produkčné nasadenie stačí doplniť MAIL_* premenné do .env - kód sa
meniť nemusí.
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("mail")


def _mail_configured() -> bool:
    return bool(os.getenv("MAIL_SERVER"))


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    """
    Vráti True, ak sa email odoslal (alebo bol v DEV režime "odoslaný" do logu).
    Nikdy nevyhadzuje výnimku smerom von - chyba pri posielaní emailu nesmie
    prezradiť útočníkovi, či daný email v systéme existuje alebo nie.
    """
    if not _mail_configured():
        logger.info(
            "[DEV MAIL] Email by bol odoslaný na %s\nPredmet: %s\n\n%s",
            to_email, subject, text_body,
        )
        print(f"\n===== [DEV MAIL - žiadny SMTP nastavený] =====\n"
              f"Komu: {to_email}\nPredmet: {subject}\n\n{text_body}\n"
              f"===============================================\n", flush=True)
        return True

    mail_server = os.getenv("MAIL_SERVER")
    mail_port = int(os.getenv("MAIL_PORT", "587"))
    mail_use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")
    mail_sender = os.getenv("MAIL_DEFAULT_SENDER", mail_username)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = mail_sender
        msg["To"] = to_email
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
            if mail_use_tls:
                server.starttls()
            if mail_username and mail_password:
                server.login(mail_username, mail_password)
            server.sendmail(mail_sender, [to_email], msg.as_string())
        return True
    except Exception:
        logger.exception("Odoslanie emailu zlyhalo (to=%s)", to_email)
        return False

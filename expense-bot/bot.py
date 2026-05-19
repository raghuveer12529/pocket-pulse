import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, TypeHandler
from telegram.ext import ApplicationHandlerStop

from db import schema, queries
from db.connection import open_db
from handlers import add, reports, budgets, search, settings
from handlers.recurring import get_conversation_handler, _schedule_recurring_job

load_dotenv()
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def owner_only(update: Update, context) -> None:
    """Reject every update that doesn't come from the configured owner."""
    allowed_id = context.bot_data.get("allowed_user_id")
    user = update.effective_user
    if user is None or user.id != allowed_id:
        logger.warning("Blocked unauthorised user_id=%s", user.id if user else "unknown")
        if update.message:
            await update.message.reply_text("This is a private bot.")
        elif update.callback_query:
            await update.callback_query.answer("This is a private bot.", show_alert=True)
        raise ApplicationHandlerStop


async def post_init(application: Application) -> None:
    db = application.bot_data["db_conn"]
    await schema.create_tables(db)
    recurring_list = await queries.get_all_recurring(db)

    for r in recurring_list:
        _schedule_recurring_job(application, r)

    logger.info("DB initialised. %d recurring job(s) scheduled.", len(recurring_list))


def main() -> None:
    token = os.environ["BOT_TOKEN"]
    allowed_user_id = int(os.environ["ALLOWED_USER_ID"])
    turso_url = os.environ["TURSO_DATABASE_URL"]
    turso_token = os.environ["TURSO_AUTH_TOKEN"]

    db_conn = open_db(url=turso_url, auth_token=turso_token)

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    app.bot_data["db_conn"] = db_conn
    app.bot_data["allowed_user_id"] = allowed_user_id

    app.add_handler(TypeHandler(Update, owner_only), group=-1)
    app.add_handler(get_conversation_handler())

    for handler in (
        add.get_handlers()
        + reports.get_handlers()
        + budgets.get_handlers()
        + search.get_handlers()
        + settings.get_handlers()
    ):
        app.add_handler(handler)

    webhook_url = os.environ.get("WEBHOOK_URL")
    if webhook_url:
        port = int(os.environ.get("PORT", 8080))
        secret = os.environ.get("WEBHOOK_SECRET", "")
        logger.info("Bot starting in webhook mode on port %d...", port)
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url,
            secret_token=secret,
            drop_pending_updates=True,
        )
    else:
        logger.info("Bot starting in polling mode (local dev)...")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

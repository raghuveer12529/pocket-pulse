import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, TypeHandler, ApplicationHandlerStop

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


def build_ptb_app() -> Application:
    db_conn = open_db(
        url=os.environ["TURSO_DATABASE_URL"],
        auth_token=os.environ["TURSO_AUTH_TOKEN"],
    )
    ptb = Application.builder().token(os.environ["BOT_TOKEN"]).post_init(post_init).build()
    ptb.bot_data["db_conn"] = db_conn
    ptb.bot_data["allowed_user_id"] = int(os.environ["ALLOWED_USER_ID"])

    ptb.add_handler(TypeHandler(Update, owner_only), group=-1)
    ptb.add_handler(get_conversation_handler())
    for handler in (
        add.get_handlers()
        + reports.get_handlers()
        + budgets.get_handlers()
        + search.get_handlers()
        + settings.get_handlers()
    ):
        ptb.add_handler(handler)

    return ptb


def create_webhook_app():
    from fastapi import FastAPI, Request, Response

    webhook_url = os.environ["WEBHOOK_URL"]
    webhook_path = "/" + webhook_url.split("/", 3)[-1]
    secret = os.environ.get("WEBHOOK_SECRET") or None

    ptb = build_ptb_app()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await ptb.initialize()
        await ptb.start()
        await ptb.bot.set_webhook(url=webhook_url, secret_token=secret, drop_pending_updates=True)
        logger.info("Webhook registered → %s", webhook_url)
        yield
        await ptb.bot.delete_webhook()
        await ptb.stop()
        await ptb.shutdown()

    web = FastAPI(lifespan=lifespan)

    @web.api_route("/health", methods=["GET", "HEAD"])
    async def health():
        return {"status": "ok"}

    @web.post(webhook_path)
    async def handle_update(request: Request):
        data = await request.json()
        update = Update.de_json(data, ptb.bot)
        await ptb.update_queue.put(update)
        return Response(status_code=200)

    return web


def main() -> None:
    if os.environ.get("WEBHOOK_URL"):
        import uvicorn
        port = int(os.environ.get("PORT", 8080))
        logger.info("Starting in webhook mode on port %d...", port)
        uvicorn.run(create_webhook_app(), host="0.0.0.0", port=port)
    else:
        logger.info("Starting in polling mode (local dev)...")
        build_ptb_app().run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

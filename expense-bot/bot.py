import os
import logging
import aiosqlite
from dotenv import load_dotenv
from telegram.ext import Application

from db import schema, queries
from handlers import add, reports, budgets, search, settings
from handlers.recurring import get_conversation_handler, _schedule_recurring_job

load_dotenv()
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    db_path = application.bot_data["db_path"]
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await schema.create_tables(db)
        recurring_list = await queries.get_all_recurring(db)

    for r in recurring_list:
        _schedule_recurring_job(application, r)

    logger.info("DB initialised. %d recurring job(s) scheduled.", len(recurring_list))


def main() -> None:
    token = os.environ["BOT_TOKEN"]
    db_path = os.environ.get("DB_PATH", "./data/expenses.db")

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    app.bot_data["db_path"] = db_path

    # ConversationHandler must be registered before plain CommandHandlers
    # that share the same command name
    app.add_handler(get_conversation_handler())

    for handler in (
        add.get_handlers()
        + reports.get_handlers()
        + budgets.get_handlers()
        + search.get_handlers()
        + settings.get_handlers()
    ):
        app.add_handler(handler)

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

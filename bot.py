import os
import asyncio
import re
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Преобразуем в int
FROM_CHANNEL = os.getenv("TAVRIA_GROUP")  # ID канала-источника
TO_CHANNEL = os.getenv("SBYT_GROUP")  # ID канала-назначения

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/var/log/bot.log"),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)

# Инициализация бота
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Функция, вызываемая при запуске бота
async def on_startup(_):
    try:
        await bot.send_message(ADMIN_ID, "Бот успешно запущен!")
        logging.info("Уведомление администратору отправлено")
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения админу: {e}")

# Обработчик команды /last
@dp.message(Command("last"))
async def get_last_post(message: Message):
    try:
        # Получаем последние сообщения из канала (ограничиваем 1 сообщением)
        async for msg in bot.get_chat_history(FROM_CHANNEL, limit=1):
            if msg.text:
                await message.answer(msg.text, parse_mode=ParseMode.HTML)
            elif msg.caption and msg.photo:
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=msg.photo[-1].file_id,
                    caption=msg.caption,
                    parse_mode=ParseMode.HTML
                )
            elif msg.caption and msg.video:
                await bot.send_video(
                    chat_id=message.chat.id,
                    video=msg.video.file_id,
                    caption=msg.caption,
                    parse_mode=ParseMode.HTML
                )
            elif msg.photo:
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=msg.photo[-1].file_id,
                    parse_mode=ParseMode.HTML
                )
            elif msg.video:
                await bot.send_video(
                    chat_id=message.chat.id,
                    video=msg.video.file_id,
                    parse_mode=ParseMode.HTML
                )
            else:
                await message.answer("Последний пост не содержит текста, фото или видео.")
            logging.info(f"Последний пост из {FROM_CHANNEL} отправлен пользователю {message.from_user.id}")
            return
        await message.answer("В канале нет постов.")
    except Exception as e:
        logging.error(f"Ошибка при получении последнего поста: {e}")
        await message.answer("Не удалось получить последний пост. Попробуйте позже.")

# Функция преобразования ссылок
def convert_links(text):
    logging.info(f"Входной текст: {text}")

    # Словарь с подставляемыми ссылками
    default_links = {
        'Telegram': 'https://t.me/TavriyaEnergo',
        'Тelegram': 'https://t.me/TavriyaEnergo',
        'Вконтакте': 'https://vk.com/public221002378'
    }

    # Шаг 1: если есть скобки с ссылками — заменить на <a href>
    pattern_with_url = r'((?:[TТ]elegram)|Вконтакте)\s*\((https?://[^\)]+)\)'

    def replace_with_html(match):
        link_text = match.group(1)
        url = match.group(2)
        if link_text.lower() == "telegram":
            link_text = "Тelegram"
        return f'<a href="{url}">{link_text}</a>'

    text = re.sub(pattern_with_url, replace_with_html, text)

    # Шаг 2: если просто слово, подставить ссылку в виде plain text
    pattern_plain = r'\b([TТ]elegram|Вконтакте)\b'

    def insert_missing_links(match):
        word = match.group(1)
        return f'{word}: {default_links.get(word, "")}'

    result = re.sub(pattern_plain, insert_missing_links, text)
    logging.info(f"Результат: {result}")
    return result

# Обработчик постов в канале
@dp.channel_post()
async def forward_with_source(post: Message):
    if str(post.chat.id) == FROM_CHANNEL:
        try:
            chat = await bot.get_chat(FROM_CHANNEL)

            if post.text:
                new_text = convert_links(post.text)
                await bot.send_message(
                    chat_id=TO_CHANNEL,
                    text=new_text,
                    parse_mode=ParseMode.HTML
                )
            elif post.caption:
                new_caption = convert_links(post.caption)
                logging.info(f"Обработана подпись: {new_caption}")
                if post.photo:
                    await bot.send_photo(
                        chat_id=TO_CHANNEL,
                        photo=post.photo[-1].file_id,
                        caption=new_caption,
                        parse_mode=ParseMode.HTML
                    )
                elif post.video:
                    await bot.send_video(
                        chat_id=TO_CHANNEL,
                        video=post.video.file_id,
                        caption=new_caption,
                        parse_mode=ParseMode.HTML
                    )
            else:
                if post.photo:
                    await bot.send_photo(
                        chat_id=TO_CHANNEL,
                        photo=post.photo[-1].file_id,
                        parse_mode=ParseMode.HTML
                    )
                elif post.video:
                    await bot.send_video(
                        chat_id=TO_CHANNEL,
                        video=post.video.file_id,
                        parse_mode=ParseMode.HTML
                    )

            logging.info(f"Сообщение {post.message_id} переслано с пометкой источника")

        except Exception as e:
            logging.error(f"Ошибка при пересылке: {str(e)}", exc_info=True)
            try:
                await post.copy_to(chat_id=TO_CHANNEL)
                logging.warning("Сообщение переслано без пометки из-за ошибки")
            except Exception as fallback_error:
                logging.error(f"Критическая ошибка: {fallback_error}")

# Основная функция
async def main():
    logging.info("Бот запущен...")
    await dp.start_polling(bot, on_startup=on_startup)

if __name__ == "__main__":
    asyncio.run(main())
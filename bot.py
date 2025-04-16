import os
import asyncio
import re
import json
import logging
from aiogram.types import Message, InputMediaPhoto
from aiogram.types import InputMediaPhoto, InputMediaVideo
from collections import defaultdict
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Получение переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
FROM_CHANNEL = os.getenv("TAVRIA_GROUP")  # ID канала-источника
TO_CHANNEL = os.getenv("SBYT_GROUP")      # ID канала-назначения
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Файл для хранения последнего message_id
LAST_POST_FILE = "last_post.json"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Инициализация бота
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


media_group_cache = defaultdict(list)
processing_groups = set()
processed_groups = set()


# Функции для сохранения и загрузки последнего message_id
def save_last_post_id(message_id: int):
    try:
        with open(LAST_POST_FILE, "w") as f:
            json.dump({"message_id": message_id}, f)
        logging.info(f"Сохранен message_id: {message_id}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении message_id: {e}")


def load_last_post_id():
    try:
        if os.path.exists(LAST_POST_FILE):
            with open(LAST_POST_FILE, "r") as f:
                data = json.load(f)
                return data.get("message_id")
    except Exception as e:
        logging.error(f"Ошибка при загрузке message_id: {e}")
    return None


# Обработчик команды /start
@dp.message(Command("start"))
async def hello(message: Message):
    await message.answer("Hello, world!")
    await bot.send_message(chat_id=FROM_CHANNEL, text="Привет, ТАВРИЯ!")
    await bot.send_message(chat_id=TO_CHANNEL, text="Привет, СБЫТ!")


# Обработчик команды /last
@dp.message(Command("last"))
async def send_last_post(message: Message):
    message_id = load_last_post_id()
    if message_id:
        try:
            await bot.copy_message(
                chat_id=TO_CHANNEL,
                from_chat_id=FROM_CHANNEL,
                message_id=message_id
            )
            await message.answer("Последний пост успешно переслан.")
        except Exception as e:
            logging.error(f"Ошибка при пересылке последнего поста: {e}")
            await message.answer("Ошибка при пересылке последнего поста.")
    else:
        await message.answer("Нет сохраненного поста для пересылки.")


# Функция для преобразования ссылок
def convert_links(text):
    logging.debug(f"Входной текст: {text}")

    default_links = {
        'Telegram': 'https://t.me/TavriyaEnergo',
        'Тelegram': 'https://t.me/TavriyaEnergo',
        'Вконтакте': 'https://vk.com/public221002378'
    }

    # Шаг 1: скобки с ссылками — в <a href>
    pattern_with_url = r'((?:[TТ]elegram)|Вконтакте)\s*\((https?://[^\)]+)\)'

    def replace_with_html(match):
        link_text = match.group(1)
        url = match.group(2)
        if link_text.lower() == "telegram":
            link_text = "Тelegram"
        return f'<a href="{url}">{link_text}</a>'

    text = re.sub(pattern_with_url, replace_with_html, text)

    # Шаг 2: подстановка по слову
    pattern_plain = r'\b([TТ]elegram|Вконтакте)\b'

    def insert_missing_links(match):
        word = match.group(1)
        return f'{word}: {default_links.get(word, "")}'
    try:
        result = re.sub(pattern_plain, insert_missing_links, text)
        logging.debug(f"Результат: {result}")
        return result
    except Exception as e:
        logging.error(f"Ошибка при преобразовании ссылок: {e}")
        return text


# Обработчик постов из FROM_CHANNEL
@dp.channel_post()
async def forward_with_source(post: Message):
    if str(post.chat.id) != FROM_CHANNEL:
        return

    try:
        save_last_post_id(post.message_id)

        # === Если это медиа-группа ===
        if post.media_group_id:
            media_group_id = post.media_group_id
            media_group_cache[media_group_id].append(post)

            # Если уже в процессе обработки или обработана — выходим
            if media_group_id in processed_groups or media_group_id in processing_groups:
                return

            processing_groups.add(media_group_id)

            # Ждём чуть-чуть, чтобы все сообщения пришли
            await asyncio.sleep(1.2)

            group = sorted(media_group_cache[media_group_id], key=lambda m: m.message_id)
            media = []

            for i, item in enumerate(group):
                caption = convert_links(item.caption) if i == 0 and item.caption else None
                if item.photo:
                    media.append(InputMediaPhoto(media=item.photo[-1].file_id, caption=caption, parse_mode=ParseMode.HTML))
                elif item.video:
                    media.append(InputMediaVideo(media=item.video.file_id, caption=caption, parse_mode=ParseMode.HTML))

            if media:
                await bot.send_media_group(chat_id=TO_CHANNEL, media=media)

            # Пометить как завершённую
            processed_groups.add(media_group_id)
            processing_groups.remove(media_group_id)
            del media_group_cache[media_group_id]
            return  # Главное: не продолжаем дальше

        # === Одиночные сообщения (не альбом) ===
        if post.text:
            text = convert_links(post.text)
            await bot.send_message(chat_id=TO_CHANNEL, text=text)

        elif post.caption:
            caption = convert_links(post.caption)
            if post.photo:
                await bot.send_photo(chat_id=TO_CHANNEL, photo=post.photo[-1].file_id, caption=caption)
            elif post.video:
                await bot.send_video(chat_id=TO_CHANNEL, video=post.video.file_id, caption=caption)

        else:
            if post.photo:
                await bot.send_photo(chat_id=TO_CHANNEL, photo=post.photo[-1].file_id)
            elif post.video:
                await bot.send_video(chat_id=TO_CHANNEL, video=post.video.file_id)

        logging.info(f"Сообщение {post.message_id} переслано")

    except Exception as e:
        logging.error(f"Ошибка при пересылке: {str(e)}", exc_info=True)
        try:
            await post.copy_to(chat_id=TO_CHANNEL)
            logging.warning("Сообщение переслано без пометки из-за ошибки")
        except Exception as fallback_error:
            logging.error(f"Критическая ошибка: {str(fallback_error)}")
                

# Основная функция
async def main():
    logging.info("Запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await bot.send_message(chat_id=ADMIN_ID, text="✅ Бот успешно запущен и готов к работе.")
    except Exception as e:
        logging.error(f"Не удалось отправить сообщение админу: {e}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

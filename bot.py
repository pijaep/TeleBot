import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

TOKEN = "8097626872:AAFBA-Xbvhx3EFbhuY9ZxI9tSBhCjocr-4Q"

bot = Bot(token=TOKEN)
dp = Dispatcher()


# Определяем состояния для FSM
class ReminderState(StatesGroup):
    waiting_for_text = State()
    waiting_for_datetime = State()


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("reminders.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        datetime TEXT,
        text TEXT
    )""")
    conn.commit()
    conn.close()


# Добавление напоминания
def add_reminder(user_id, reminder_datetime, text):
    conn = sqlite3.connect("reminders.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO reminders (user_id, datetime, text) VALUES (?, ?, ?)",
                (user_id, reminder_datetime, text))
    conn.commit()
    conn.close()


# Получение списка напоминаний пользователя
def get_reminders(user_id):
    conn = sqlite3.connect("reminders.db")
    cur = conn.cursor()
    cur.execute("SELECT id, datetime, text FROM reminders WHERE user_id = ?", (user_id,))
    reminders = cur.fetchall()
    conn.close()
    return reminders


# Удаление напоминания
def delete_reminder(reminder_id):
    conn = sqlite3.connect("reminders.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()


# Проверка и отправка напоминаний
async def check_reminders():
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = sqlite3.connect("reminders.db")
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, text FROM reminders WHERE datetime = ?", (now,))
        reminders = cur.fetchall()

        for reminder in reminders:
            reminder_id, user_id, text = reminder
            await bot.send_message(user_id, f"🔔 Напоминание: {text}")
            delete_reminder(reminder_id)

        conn.close()
        await asyncio.sleep(60)


# Команда для отправки приветственного сообщения с меню
@dp.message(Command("start"))
async def start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Новое напоминание", callback_data="remind")],
        [InlineKeyboardButton(text="📜 Мои напоминания", callback_data="reminders")]
    ])
    await message.answer("Привет! Я бот-напоминалка. Чем могу помочь?", reply_markup=kb)


# Команда для установки напоминания (запуск FSM)
@dp.message(Command("remind"))
async def remind_start(message: Message, state: FSMContext):
    await state.set_state(ReminderState.waiting_for_text)  # Здесь используем set_state для установки состояния
    # Проверяем, если мы уже находимся в состоянии ожидания текста, то не отправляем повторное сообщение
    state_data = await state.get_data()
    if "text_set" not in state_data:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_remind")]
        ])
        await message.answer("📝 О чём вам напомнить?", reply_markup=kb)


# Пользователь вводит текст напоминания
@dp.message(ReminderState.waiting_for_text)
async def remind_text_received(message: Message, state: FSMContext):
    # Если текст уже был установлен, то игнорируем повторные сообщения
    state_data = await state.get_data()
    if "text_set" in state_data:
        await message.answer("❗ Напоминание уже установлено. Вернитесь в главное меню.")
        return

    # Устанавливаем текст и переходим к следующему шагу
    await state.update_data(text=message.text, text_set=True)
    await state.set_state(ReminderState.waiting_for_datetime)
    await message.answer("📅 Введите дату и время в формате:\n`YYYY-MM-DD HH:MM` или просто `HH:MM` (сегодня)",
                         parse_mode="Markdown")


# Пользователь вводит дату и время
@dp.message(ReminderState.waiting_for_datetime)
async def remind_datetime_received(message: Message, state: FSMContext):
    data = await state.get_data()
    text = data["text"]

    try:
        parts = message.text.split()

        if len(parts) == 1 and ":" in parts[0]:  # Если введено только время
            today = datetime.now().strftime("%Y-%m-%d")
            reminder_datetime = f"{today} {parts[0]}"
        elif len(parts) == 2:  # Если введена дата и время
            reminder_datetime = f"{parts[0]} {parts[1]}"
        else:
            raise ValueError

        # Проверяем корректность даты и времени
        datetime.strptime(reminder_datetime, "%Y-%m-%d %H:%M")

        add_reminder(message.from_user.id, reminder_datetime, text)
        await message.answer(f"✅ Напоминание установлено на {reminder_datetime}: {text}")

        # Кнопка для возврата в главное меню
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Вернуться в главное меню", callback_data="main_menu")]
        ])
        await message.answer("Вы можете вернуться в главное меню.", reply_markup=kb)
        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат! Введите `YYYY-MM-DD HH:MM` или `HH:MM` (на сегодня).",
                             parse_mode="Markdown")


# Команда для просмотра списка напоминаний
@dp.message(Command("reminders"))
async def list_reminders(message: Message):
    reminders = get_reminders(message.from_user.id)
    if not reminders:
        await message.answer("📭 У вас нет напоминаний.")
        return

    for reminder in reminders:
        reminder_id, reminder_datetime, text = reminder
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⛔ Удалить", callback_data=f"delete_{reminder_id}")]
        ])
        await message.answer(f"⏰ {reminder_datetime} - {text}", reply_markup=kb)


# Обработчик кнопки удаления напоминания
@dp.callback_query(lambda c: c.data.startswith("delete_"))
async def delete_reminder_callback(callback: types.CallbackQuery):
    reminder_id = int(callback.data.split("_")[1])
    delete_reminder(reminder_id)
    await callback.answer("❌ Напоминание удалено!")
    await callback.message.delete()


# Обработчик кнопок меню (new reminder, view reminders)
@dp.callback_query(lambda c: c.data == "remind")
async def remind_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()  # Ожидание ответа с кнопкой
    # Убедимся, что сообщение о "О чём вам напомнить?" и кнопка отмены отправляются только один раз
    state_data = await state.get_data()
    if "text_set" not in state_data:  # Мы не находимся в процессе создания напоминания

        await state.set_state(ReminderState.waiting_for_text)  # Теперь правильно используем set_state()

    # Кнопка "Отмена" возвращает в главное меню
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_remind")],
    ])
    await callback.message.answer("📝 О чём вам напомнить?", reply_markup=kb)


@dp.callback_query(lambda c: c.data == "reminders")
async def reminders_menu_callback(callback: types.CallbackQuery):
    await callback.answer()  # Ожидание ответа с кнопкой
    reminders = get_reminders(callback.from_user.id)
    if not reminders:
        await callback.message.answer("📭 У вас нет напоминаний.")
    else:
        for reminder in reminders:
            reminder_id, reminder_datetime, text = reminder
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⛔ Удалить", callback_data=f"delete_{reminder_id}")]
            ])
            await callback.message.answer(f"⏰ {reminder_datetime} - {text}", reply_markup=kb)


# Обработчик кнопки "Вернуться в главное меню"
@dp.callback_query(lambda c: c.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Новое напоминание", callback_data="remind")],
        [InlineKeyboardButton(text="📜 Мои напоминания", callback_data="reminders")]
    ])
    await callback.message.answer("Привет! Я бот-напоминалка. Чем могу помочь?", reply_markup=kb)
    await callback.answer()  # Подтверждаем, что запрос обработан


# Обработчик кнопки "Отмена" для создания нового напоминания
@dp.callback_query(lambda c: c.data == "cancel_remind")
async def cancel_remind_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()  # Очищаем состояние
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Новое напоминание", callback_data="remind")],
        [InlineKeyboardButton(text="📜 Мои напоминания", callback_data="reminders")]
    ])
    await callback.message.answer("Действие отменено. Возвращаемся в главное меню.", reply_markup=kb)
    await callback.answer()  # Подтверждаем, что запрос обработан


# Основная функция запуска бота
async def main():
    init_db()
    asyncio.create_task(check_reminders())  # Запускаем фоновую проверку напоминаний
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

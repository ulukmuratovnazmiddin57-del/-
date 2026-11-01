import asyncio
import logging
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- Настройки ---
API_TOKEN = "8859733004:AAGilfKCCJCDs5Eg2X-BBUDZCjHBR__sSJk"
DB_FILE = "sports_docs.db"
ADMIN_IDS = [6614896529]  # Ваш Telegram ID (Главный администратор)
# ------------------

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

async def check_access(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT user_id FROM allowed_users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

# Состояния FSM
class AddPersonState(StatesGroup):
    sport_section = State()
    role = State()
    full_name = State()

class AddFolderState(StatesGroup):
    parent_id = State()
    folder_name = State()

class UploadFileState(StatesGroup):
    folder_id = State()
    file = State()

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS allowed_users (
                user_id INTEGER PRIMARY KEY
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                sport_section TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                parent_id INTEGER DEFAULT 0,
                name TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_name TEXT
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_persons_section ON persons(sport_section, role);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(person_id, parent_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_files_folder ON files(folder_id);")
        await db.commit()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    if await check_access(user_id):
        kb = [[types.KeyboardButton(text="🔍 Поиск документов")]]
        if user_id in ADMIN_IDS:
            kb.insert(0, [types.KeyboardButton(text="➕ Добавить человека")])

        keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        role_text = " (Администратор)" if user_id in ADMIN_IDS else " (Тренер)"
        await message.answer(f"Привет{role_text}! Системный архив документов.\nВыберите действие:", reply_markup=keyboard)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Запросить доступ у администратора", callback_data="req_acc")]
        ])
        await message.answer("❌ У вас нет доступа к этому боту.\nНажмите кнопку ниже, чтобы отправить запрос администратору:", reply_markup=kb)

# --- ЗАПРОС И ПОДТВЕРЖДЕНИЕ ДОСТУПА ---
@dp.callback_query(F.data == "req_acc")
async def request_access_callback(callback: types.CallbackQuery):
    user = callback.from_user
    username_text = f"@{user.username}" if user.username else "нет username"
    user_info = f"👤 Пользователь: {user.full_name} ({username_text}, ID: `{user.id}`)"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Разрешить", callback_data=f"allow_{user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"deny_{user.id}")
        ]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"📥 **Запрос на доступ к боту:**\n\n{user_info}", reply_markup=kb)
        except Exception:
            pass
            
    await callback.message.edit_text("⏳ Запрос успешно отправлен администратору. Ожидайте подтверждения.")
    await callback.answer()

@dp.callback_query(F.data.startswith("allow_"))
async def allow_user(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    target_id = int(callback.data.replace("allow_", ""))
    
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT OR IGNORE INTO allowed_users (user_id) VALUES (?)", (target_id,))
        await db.commit()
        
    await callback.message.edit_text(callback.message.text + "\n\n✅ **СТАТУС: ДОСТУП ПРЕДОСТАВЛЕН**", reply_markup=None)
    
    try:
        await bot.send_message(target_id, "🎉 Ваш доступ к боту подтвержден администратором!\nНажмите /start для начала работы.")
    except:
        pass
        
    await callback.answer("Доступ успешно предоставлен!", show_alert=True)

@dp.callback_query(F.data.startswith("deny_"))
async def deny_user(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    target_id = int(callback.data.replace("deny_", ""))
    
    await callback.message.edit_text(callback.message.text + "\n\n❌ **СТАТУС: ДОСТУП ОТКЛОНЕН**", reply_markup=None)
    
    try:
        await bot.send_message(target_id, "❌ Ваш запрос на доступ к боту был отклонен администратором.")
    except:
        pass
        
    await callback.answer("Запрос отклонен.", show_alert=True)

# --- 1. ДОБАВЛЕНИЕ ЧЕЛОВЕКА ---
@dp.message(F.text == "➕ Добавить человека")
async def start_add_person(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛶 Гребля на байдарках и каноэ", callback_data="s_row")],
        [InlineKeyboardButton(text="🥇 Параканоэ", callback_data="s_para")]
    ])
    await state.set_state(AddPersonState.sport_section)
    await message.answer("Выберите спортивное направление:", reply_markup=kb)

@dp.callback_query(AddPersonState.sport_section, F.data.in_({"s_row", "s_para"}))
async def process_sport_section(callback: types.CallbackQuery, state: FSMContext):
    sport_section = "Гребля на байдарках и каноэ" if callback.data == "s_row" else "Параканоэ"
    await state.update_data(sport_section=sport_section)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏃‍♂️ Спортсмен", callback_data="r_sport")],
        [InlineKeyboardButton(text="👨‍🏫 Тренер", callback_data="r_coach")]
    ])
    await state.set_state(AddPersonState.role)
    await callback.message.edit_text(f"Направление: **{sport_section}**.\nВыберите роль:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(AddPersonState.role, F.data.in_({"r_sport", "r_coach"}))
async def process_role(callback: types.CallbackQuery, state: FSMContext):
    role = "Спортсмен" if callback.data == "r_sport" else "Тренер"
    await state.update_data(role=role)
    await state.set_state(AddPersonState.full_name)
    await callback.message.edit_text(f"Роль: **{role}**.\nВведите полное ФИО:")
    await callback.answer()

@dp.message(AddPersonState.full_name)
async def process_person_fullname(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    sport_section = data.get("sport_section", "Гребля на байдарках и каноэ")
    role = data.get("role", "Спортсмен")
    full_name = message.text.strip()

    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("INSERT INTO persons (full_name, role, sport_section) VALUES (?, ?, ?)", (full_name, role, sport_section))
        person_id = cursor.lastrowid
        default_folders = ["Паспорт", "Фото", "Метрика", "Дипломы и Сертификаты"]
        for f_name in default_folders:
            await db.execute("INSERT INTO folders (person_id, parent_id, name) VALUES (?, 0, ?)", (person_id, f_name))
        await db.commit()

    await state.clear()
    await message.answer(f"✅ **Успешно сохранено!**\n[{sport_section}] {role} **{full_name}** добавлен в базу, созданы базовые папки.")

# --- 2. ПОИСК И НАВИГАЦИЯ ---
@dp.message(F.text == "🔍 Поиск документов")
async def start_search(message: types.Message, state: FSMContext):
    if not await check_access(message.from_user.id):
        return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛶 Гребля на байдарках и каноэ", callback_data="ls_row")],
        [InlineKeyboardButton(text="🥇 Параканоэ", callback_data="ls_para")]
    ])
    await message.answer("Выберите спортивное направление:", reply_markup=kb)

@dp.callback_query(F.data.in_({"ls_row", "ls_para"}))
async def list_roles_by_sport(callback: types.CallbackQuery):
    if not await check_access(callback.from_user.id):
        return
    sport_section = "Гребля на байдарках и каноэ" if callback.data == "ls_row" else "Параканоэ"
    prefix = "r1" if callback.data == "ls_row" else "r2"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏃‍♂️ Спортсмены", callback_data=f"lr_{prefix}_Спортсмен")],
        [InlineKeyboardButton(text="👨‍🏫 Тренеры", callback_data=f"lr_{prefix}_Тренер")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_search")]
    ])
    await callback.message.edit_text(f"Направление: **{sport_section}**.\nВыберите категорию:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("lr_"))
async def list_persons_by_role_and_sport(callback: types.CallbackQuery):
    if not await check_access(callback.from_user.id):
        return
    parts = callback.data.split("_")
    prefix = parts[1]
    role = parts[2]
    sport_section = "Гребля на байдарках и каноэ" if prefix == "r1" else "Параканоэ"

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT id, full_name FROM persons WHERE sport_section = ? AND role = ? ORDER BY full_name ASC", (sport_section, role)) as cursor:
            persons = await cursor.fetchall()

    if not persons:
        back_cb = "ls_row" if prefix == "r1" else "ls_para"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)]
        ])
        await callback.message.edit_text(f"❌ В разделе **{sport_section} ({role})** пока нет записей.", reply_markup=kb)
        await callback.answer()
        return

    back_cb = "ls_row" if prefix == "r1" else "ls_para"
    kb = [[InlineKeyboardButton(text=f"👤 {p[1]}", callback_data=f"p_{p[0]}")] for p in persons]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    await callback.message.edit_text(f"Список ({sport_section} — {role}):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("p_"))
async def open_person_root(callback: types.CallbackQuery):
    if not await check_access(callback.from_user.id):
        return
    person_id = int(callback.data.replace("p_", ""))
    await show_folder_content(callback, person_id=person_id, folder_id=0)

@dp.callback_query(F.data.startswith("f_"))
async def open_folder(callback: types.CallbackQuery):
    if not await check_access(callback.from_user.id):
        return
    folder_id = int(callback.data.replace("f_", ""))
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT person_id FROM folders WHERE id = ?", (folder_id,)) as cursor:
            row = await cursor.fetchone()
            person_id = row[0] if row else 0
    await show_folder_content(callback, person_id=person_id, folder_id=folder_id)

async def show_folder_content(callback: types.CallbackQuery, person_id: int, folder_id: int):
    is_admin = callback.from_user.id in ADMIN_IDS

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT full_name, role, sport_section FROM persons WHERE id = ?", (person_id,)) as cursor:
            person = await cursor.fetchone()
        
        async with db.execute("SELECT id, name FROM folders WHERE person_id = ? AND parent_id = ?", (person_id, folder_id)) as cursor:
            subfolders = await cursor.fetchall()

        files = []
        if folder_id != 0:
            async with db.execute("SELECT id, file_name FROM files WHERE folder_id = ?", (folder_id,)) as cursor:
                files = await cursor.fetchall()

    kb = []
    for sf in subfolders:
        row_btns = [InlineKeyboardButton(text=f"📁 {sf[1]}", callback_data=f"f_{sf[0]}")]
        if is_admin:
            row_btns.append(InlineKeyboardButton(text="❌", callback_data=f"df_{sf[0]}"))
        kb.append(row_btns)

    for fl in files:
        btn_text = f"📄 {fl[1]}"
        if is_admin:
            btn_text += " [🗑]"
        kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"file_{fl[0]}")])

    if is_admin and folder_id != 0:
        kb.append([InlineKeyboardButton(text="➕ Создать подраздел", callback_data=f"addf_{folder_id}")])
        kb.append([InlineKeyboardButton(text="📤 Загрузить файл сюда", callback_data=f"up_{folder_id}")])

    if is_admin and folder_id == 0:
        kb.append([InlineKeyboardButton(text="❌ Удалить человека", callback_data=f"dp_{person_id}")])

    if folder_id == 0:
        prefix = "r1" if person[2] == "Гребля на байдарках и каноэ" else "r2"
        kb.append([InlineKeyboardButton(text="⬅️ Назад к списку", callback_data=f"lr_{prefix}_{person[1]}")])
    else:
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT parent_id FROM folders WHERE id = ?", (folder_id,)) as cursor:
                parent_row = await cursor.fetchone()
                parent_id = parent_row[0] if parent_row else 0
        
        back_cb = f"p_{person_id}" if parent_id == 0 else f"f_{parent_id}"
        kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])

    title = f"👤 [{person[2]}] {person[1]}: **{person[0]}**" if folder_id == 0 else "📁 Просмотр подраздела"
    await callback.message.edit_text(title, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

# --- 3. СОЗДАНИЕ И УДАЛЕНИЕ ПОДРАЗДЕЛОВ ---
@dp.callback_query(F.data.startswith("addf_"))
async def start_add_subfolder(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    folder_id = int(callback.data.replace("addf_", ""))
    await state.update_data(parent_id=folder_id)
    await state.set_state(AddFolderState.folder_name)
    await callback.message.answer("Введите название нового подраздела (папки):")
    await callback.answer()

@dp.message(AddFolderState.folder_name)
async def process_subfolder_name(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    parent_id = data.get("parent_id")
    name = message.text.strip()

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT person_id FROM folders WHERE id = ?", (parent_id,)) as cursor:
            row = await cursor.fetchone()
            person_id = row[0] if row else 0
        await db.execute("INSERT INTO folders (person_id, parent_id, name) VALUES (?, ?, ?)", (person_id, parent_id, name))
        await db.commit()

    await state.clear()
    await message.answer(f"✅ **Успешно сохранено!** Подраздел «**{name}**» создан.")

@dp.callback_query(F.data.startswith("df_"))
async def delete_folder(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    folder_id = int(callback.data.replace("df_", ""))
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        await db.execute("DELETE FROM files WHERE folder_id = ?", (folder_id,))
        await db.commit()
    await callback.answer("✅ Подраздел успешно удален!", show_alert=True)

# --- 4. ЗАГРУЗКА И СКАЧИВАНИЕ ФАЙЛОВ ---
@dp.callback_query(F.data.startswith("up_"))
async def start_upload_file(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    folder_id = int(callback.data.replace("up_", ""))
    await state.update_data(folder_id=folder_id)
    await state.set_state(UploadFileState.file)
    await callback.message.answer("Отправьте фото или документ (файл) для этого подраздела:")
    await callback.answer()

@dp.message(UploadFileState.file, F.document | F.photo)
async def process_upload_file(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    folder_id = data.get("folder_id")

    file_id = message.document.file_id if message.document else message.photo[-1].file_id
    file_type = "document" if message.document else "photo"
    file_name = message.document.file_name if message.document else "Фотография"

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT INTO files (folder_id, file_id, file_type, file_name) VALUES (?, ?, ?, ?)", (folder_id, file_id, file_type, file_name))
        await db.commit()

    await state.clear()
    await message.answer("✅ **Успешно сохранено!** Файл загружен в архив.")

@dp.callback_query(F.data.startswith("file_"))
async def send_file(callback: types.CallbackQuery):
    if not await check_access(callback.from_user.id):
        return
    file_db_id = int(callback.data.replace("file_", ""))
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT file_id, file_type, file_name FROM files WHERE id = ?", (file_db_id,)) as cursor:
            row = await cursor.fetchone()

    if row:
        file_id, file_type, file_name = row
        if file_type == "document":
            await callback.message.answer_document(file_id, caption=f"📄 {file_name}")
        else:
            await callback.message.answer_photo(file_id, caption="🖼 Фотография")
    await callback.answer()

@dp.callback_query(F.data.startswith("dp_"))
async def delete_person(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    person_id = int(callback.data.replace("dp_", ""))
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM persons WHERE id = ?", (person_id,))
        await db.execute("DELETE FROM folders WHERE person_id = ?", (person_id,))
        await db.commit()
    await callback.message.edit_text("✅ **Успешно удалено!** Карточка человека и все его файлы стерты из базы.")
    await callback.answer()

@dp.callback_query(F.data == "back_search")
async def back_to_search_sports(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛶 Гребля на байдарках и каноэ", callback_data="ls_row")],
        [InlineKeyboardButton(text="🥇 Параканоэ", callback_data="ls_para")]
    ])
    await callback.message.edit_text("Выберите спортивное направление:", reply_markup=kb)
    await callback.answer()

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
import logging
import gspread
from google.oauth2.service_account import Credentials
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from datetime import datetime
import os
import json

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get('BOT_TOKEN', '7298874610:AAEKSlBVzZg2oLmlcyxmZXMPTTb_DEtOFK4')
GOOGLE_SHEET_ID = '132DPAekvChbf4rlhEFTMl6EzxhVyXEGSh6rNinQXBD4'  # ЗАМЕНИ НА РЕАЛЬНЫЙ ID

# Настройка доступа к Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = 'credentials.json'

# Состояния бота
(
    MAIN_MENU, 
    CHRONO_TIME, CHRONO_PRODUCT, CHRONO_QUANTITY, 
    BLANK_TYPE, BLANK_QUANTITY,
    OTHER_OPERATION, OTHER_DETAILS
) = range(8)  

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_google_sheet():
    """Подключается к Google Таблице."""
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GOOGLE_SHEET_ID)
        return sheet
    except Exception as e:
        logger.error(f"Ошибка подключения к Google Sheets: {e}")
        return None

def save_to_google_sheets(user_data: dict, user_id: int, username: str):
    """Сохраняет данные в Google Таблицы."""
    
    record_type = user_data.get('record_type', 'Не указан')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    operator_name = user_data.get('operator_name', 'Не указан')
    
    sheet = get_google_sheet()
    if not sheet:
        logger.error("Не удалось подключиться к Google Sheets")
        return False
    
    try:
        # Выбираем лист в зависимости от типа записи
        if record_type == 'Хронометраж':
            worksheet = sheet.worksheet('Хронометраж')
            data = [
                timestamp,
                operator_name,
                user_data.get('chrono_time', ''),
                user_data.get('chrono_product', ''),
                user_data.get('chrono_quantity', '')  # Добавил количество
            ]
            
        elif record_type == 'Заготовка':
            worksheet = sheet.worksheet('Заготовки')
            data = [
                timestamp,
                operator_name,
                user_data.get('blank_type', ''),
                user_data.get('blank_quantity', '')
            ]
            
        elif record_type == 'Другое':
            worksheet = sheet.worksheet('Другое')
            data = [
                timestamp,
                operator_name,
                user_data.get('other_operation', ''),
                user_data.get('other_details', '')
            ]
        else:
            return False
        
        # Добавляем новую строку
        worksheet.append_row(data)
        logger.info(f"Данные сохранены в Google Sheets: {record_type}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка сохранения в Google Sheets: {e}")
        return False

def init_google_sheets():
    """Инициализирует Google Таблицу - создает листы и заголовки."""
    sheet = get_google_sheet()
    if not sheet:
        return False
    
    try:
        # Создаем листы если их нет
        sheet_titles = ['Хронометраж', 'Заготовки', 'Другое']
        existing_sheets = [ws.title for ws in sheet.worksheets()]
        
        for title in sheet_titles:
            if title not in existing_sheets:
                worksheet = sheet.add_worksheet(title=title, rows=1000, cols=10)
                
                # Добавляем заголовки в зависимости от листа
                if title == 'Хронометраж':
                    worksheet.append_row(['Дата и время', 'Оператор', 'Время операции', 'Изготовленный продукт', 'Количество'])  # Добавил Количество
                elif title == 'Заготовки':
                    worksheet.append_row(['Дата и время', 'Оператор', 'Тип заготовки', 'Количество'])
                elif title == 'Другое':
                    worksheet.append_row(['Дата и время', 'Оператор', 'Операция', 'Дополнительные сведения'])
        
        logger.info("Google Sheets инициализирована")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка инициализации Google Sheets: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог с главного меню."""
    user = update.message.from_user
    logger.info("Пользователь %s начал диалог.", user.first_name)
    
    context.user_data['operator_name'] = user.first_name
    
    # Инициализируем Google Таблицу при первом запуске
    if not context.bot_data.get('google_sheets_initialized'):
        if init_google_sheets():
            context.bot_data['google_sheets_initialized'] = True
    
    # Главное меню с тремя кнопками
    main_menu_keyboard = [['⏱️ Хронометраж', '⚙️ Заготовка'], ['📝 Другое']]
    
    await update.message.reply_text(
        f'🏭 *Учет производства*\n\n'
        f'Привет, {user.first_name}!\n'
        'Выбери тип операции:',
        reply_markup=ReplyKeyboardMarkup(
            main_menu_keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        ),
        parse_mode='Markdown'
    )
    return MAIN_MENU

# === ОСТАЛЬНЫЕ ФУНКЦИИ БЕЗ ИЗМЕНЕНИЙ ===
# (используются те же самые функции что и в предыдущей версии, 
#  но вместо save_to_excel вызываем save_to_google_sheets)

async def main_menu_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор в главном меню."""
    choice = update.message.text
    
    if 'Хронометраж' in choice:
        context.user_data['record_type'] = 'Хронометраж'
        await update.message.reply_text('⏱️ *Хронометраж*\n\nУкажи время начала и конца операции:\n_Пример: "10:00-11:30" или "с 9:00 до 10:15"_', reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
        return CHRONO_TIME
        
    elif 'Заготовка' in choice:
        context.user_data['record_type'] = 'Заготовка'
        await update.message.reply_text('⚙️ *Заготовка*\n\nКакую заготовку ты сделал?', reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
        return BLANK_TYPE
        
    elif 'Другое' in choice:
        context.user_data['record_type'] = 'Другое'
        await update.message.reply_text('📝 *Другое*\n\nУкажи необходимую операцию:', reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
        return OTHER_OPERATION
        
    else:
        await update.message.reply_text('❌ Пожалуйста, выбери вариант из меню.')
        return MAIN_MENU

# === ОБРАБОТКА ХРОНОМЕТРАЖА ===
async def chrono_time_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод времени для хронометража."""
    chrono_time = update.message.text.strip()
    
    if not chrono_time:
        await update.message.reply_text('❌ Время не может быть пустым.')
        return CHRONO_TIME
    
    context.user_data['chrono_time'] = chrono_time
    
    await update.message.reply_text(
        f'✅ *Время:* {chrono_time}\n\n'
        'Какой продукт был изготовлен?',
        parse_mode='Markdown'
    )
    return CHRONO_PRODUCT

async def chrono_product_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод продукта для хронометража."""
    chrono_product = update.message.text.strip()
    
    if not chrono_product:
        await update.message.reply_text('❌ Продукт не может быть пустым.')
        return CHRONO_PRODUCT
    
    context.user_data['chrono_product'] = chrono_product
    
    await update.message.reply_text(
        f'✅ *Продукт:* {chrono_product}\n\n'
        'Какое количество было изготовлено?',
        parse_mode='Markdown'
    )
    return CHRONO_QUANTITY

async def chrono_quantity_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод количества для хронометража и сохраняет данные."""
    quantity_text = update.message.text.strip()
    user = update.message.from_user
    
    if not quantity_text:
        await update.message.reply_text('❌ Количество не может быть пустым.')
        return CHRONO_QUANTITY
    
    # Проверяем что это число
    try:
        quantity = int(quantity_text)
        if quantity <= 0:
            await update.message.reply_text('❌ Введи положительное число.')
            return CHRONO_QUANTITY
    except ValueError:
        # Если не число, сохраняем как текст
        quantity = quantity_text
    
    context.user_data['chrono_quantity'] = quantity
    
    # Сохраняем в Google Sheets
    if save_to_google_sheets(context.user_data, user.id, user.username or user.first_name):
        await update.message.reply_text(
            f'✅ *Хронометраж сохранен в Google Таблицы!*\n\n'
            f'Время: {context.user_data["chrono_time"]}\n'
            f'Продукт: {context.user_data["chrono_product"]}\n'
            f'Количество: {quantity}\n\n'
            f'Для новой записи отправь /start',
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text('❌ Ошибка сохранения. Попробуй еще раз.')
    
    context.user_data.clear()
    return ConversationHandler.END

async def blank_type_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    blank_type = update.message.text.strip()
    if not blank_type:
        await update.message.reply_text('❌ Тип заготовки не может быть пустым.')
        return BLANK_TYPE
    context.user_data['blank_type'] = blank_type
    await update.message.reply_text(f'✅ *Заготовка:* {blank_type}\n\nСколько штук?', parse_mode='Markdown')
    return BLANK_QUANTITY

async def blank_quantity_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    quantity_text = update.message.text.strip()
    user = update.message.from_user
    if not quantity_text:
        await update.message.reply_text('❌ Количество не может быть пустым.')
        return BLANK_QUANTITY
    
    try:
        quantity = int(quantity_text)
        if quantity <= 0:
            await update.message.reply_text('❌ Введи положительное число.')
            return BLANK_QUANTITY
    except ValueError:
        quantity = quantity_text
    
    context.user_data['blank_quantity'] = quantity
    
    if save_to_google_sheets(context.user_data, user.id, user.username or user.first_name):
        await update.message.reply_text(f'✅ *Заготовка сохранена в Google Таблицы!*\n\nТип: {context.user_data["blank_type"]}\nКоличество: {quantity}\n\nДля новой записи отправь /start', reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
    else:
        await update.message.reply_text('❌ Ошибка сохранения. Попробуй еще раз.')
    
    context.user_data.clear()
    return ConversationHandler.END

async def other_operation_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    other_operation = update.message.text.strip()
    if not other_operation:
        await update.message.reply_text('❌ Операция не может быть пустой.')
        return OTHER_OPERATION
    context.user_data['other_operation'] = other_operation
    await update.message.reply_text(f'✅ *Операция:* {other_operation}\n\nУкажи дополнительные сведения:', parse_mode='Markdown')
    return OTHER_DETAILS

async def other_details_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    other_details = update.message.text.strip()
    user = update.message.from_user
    context.user_data['other_details'] = other_details
    
    if save_to_google_sheets(context.user_data, user.id, user.username or user.first_name):
        await update.message.reply_text(f'✅ *Операция сохранена в Google Таблицы!*\n\nОперация: {context.user_data["other_operation"]}\nДополнительно: {other_details}\n\nДля новой записи отправь /start', reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
    else:
        await update.message.reply_text('❌ Ошибка сохранения. Попробуй еще раз.')
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('❌ Диалог отменен. Для начала отправь /start.', reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

def main():
    """Запускает бота."""
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_selected)],
            # Хронометраж
            CHRONO_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, chrono_time_entered)],
            CHRONO_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, chrono_product_entered)],
            CHRONO_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, chrono_quantity_entered)],
            # Заготовка
            BLANK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, blank_type_entered)],
            BLANK_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, blank_quantity_entered)],
            # Другое
            OTHER_OPERATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, other_operation_entered)],
            OTHER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, other_details_entered)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    
    print("🤖 Бот с Google Sheets запускается...")
    print("⏱️ Хронометраж | ⚙️ Заготовка | 📝 Другое")
    application.run_polling()

if __name__ == '__main__':
    main()

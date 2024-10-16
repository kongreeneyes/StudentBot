import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

(
    CREATE_CLASS,
    ENROLL_STUDENT,
    ENROLL_STUDENT_NAME,
    RECORD_ABSENCE_CLASS,
    RECORD_ABSENCE_DATE,
    RECORD_ABSENCE_NAMES,
    MARK_PRESENT_CLASS,
    MARK_PRESENT_DATE,
    MARK_PRESENT_NAMES,
    SHOW_STUDENTS_CLASS,
    ATTENDANCE_INFO_CLASS,
    ATTENDANCE_INFO_DATE_SELECT,
) = range(12)

def setup_database():
    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_code TEXT UNIQUE NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER,
            full_name TEXT NOT NULL,
            FOREIGN KEY(class_id) REFERENCES classes(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            attendance_date TEXT,
            is_present INTEGER,
            FOREIGN KEY(student_id) REFERENCES students(id),
            UNIQUE(student_id, attendance_date)
        )
    ''')
    connection.commit()
    connection.close()

async def greet_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Я бот для контроля посещаемости.\n"
        "Команды:\n"
        "/createclass - создать новый класс\n"
        "/enrollstudent - записать студента в класс\n"
        "/recordabsence - отметить отсутствующих студентов\n"
        "/markpresent - отметить присутствующих студентов\n"
        "/attendanceinfo - получить информацию о посещаемости\n"
        "/showclasses - показать все классы\n"
        "/showstudents - показать студентов в классе\n"
        "/help - примеры использования команд\n"
        "/cancel - отменить текущую операцию"
    )

async def start_create_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пожалуйста, укажите код класса.")
    return CREATE_CLASS

async def create_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class_code = update.message.text.strip()

    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    try:
        cursor.execute('INSERT INTO classes (class_code) VALUES (?)', (class_code,))
        connection.commit()
        await update.message.reply_text(f"Класс {class_code} успешно создан.", reply_markup=ReplyKeyboardRemove())
    except sqlite3.IntegrityError:
        await update.message.reply_text("Класс с таким кодом уже существует. Попробуйте снова.", reply_markup=ReplyKeyboardRemove())
    finally:
        connection.close()

    return ConversationHandler.END

async def start_enroll_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Укажите код класса, в который хотите добавить студента.")
    return ENROLL_STUDENT

async def enroll_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['class_code'] = update.message.text.strip()
    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('SELECT id FROM classes WHERE class_code = ?', (context.user_data['class_code'],))
    class_info = cursor.fetchone()
    connection.close()

    if class_info is None:
        await update.message.reply_text("Класс не найден. Попробуйте снова.")
        return ENROLL_STUDENT

    await update.message.reply_text("Введите имя студента.")
    return ENROLL_STUDENT_NAME

async def enroll_student_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_name = update.message.text.strip()
    class_code = context.user_data['class_code']

    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('SELECT id FROM classes WHERE class_code = ?', (class_code,))
    class_id = cursor.fetchone()[0]
    cursor.execute('INSERT INTO students (class_id, full_name) VALUES (?, ?)', (class_id, student_name))
    connection.commit()
    connection.close()

    await update.message.reply_text(f"Студент {student_name} добавлен в класс {class_code}.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def start_record_absence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Укажите код класса, для которого нужно отметить отсутствующих.")
    return RECORD_ABSENCE_CLASS

async def record_absence_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class_code = update.message.text.strip()
    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('SELECT id FROM classes WHERE class_code = ?', (class_code,))
    class_info = cursor.fetchone()

    if class_info is None:
        await update.message.reply_text("Класс не найден. Попробуйте снова.")
        return RECORD_ABSENCE_CLASS

    context.user_data['class_code'] = class_code
    context.user_data['class_id'] = class_info[0]
    await update.message.reply_text("Укажите дату в формате ГГГГ-ММ-ДД, на которую нужно отметить отсутствующих.")
    return RECORD_ABSENCE_DATE

async def record_absence_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    attendance_date_str = update.message.text.strip()
    try:
        # Проверка корректности формата даты
        attendance_date = datetime.strptime(attendance_date_str, "%Y-%m-%d").date()
        context.user_data['attendance_date'] = attendance_date_str
    except ValueError:
        await update.message.reply_text("Некорректный формат даты. Пожалуйста, используйте формат ГГГГ-ММ-ДД.")
        return RECORD_ABSENCE_DATE

    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('SELECT id, full_name FROM students WHERE class_id = ?', (context.user_data['class_id'],))
    students = cursor.fetchall()
    connection.close()

    if not students:
        await update.message.reply_text("В этом классе нет студентов.")
        return ConversationHandler.END

    student_list = "\n".join([f"{i+1}. {student[1]}" for i, student in enumerate(students)])
    context.user_data['students'] = {str(i+1): student[0] for i, student in enumerate(students)} 
    await update.message.reply_text(f"Студенты в классе {context.user_data['class_code']}:\n{student_list}\n\nВведите номера отсутствующих через пробел.")
    return RECORD_ABSENCE_NAMES

async def record_absence_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_numbers = update.message.text.split()
    student_ids = [context.user_data['students'].get(number) for number in student_numbers if number in context.user_data['students']]
    attendance_date_str = context.user_data['attendance_date']

    class_code = context.user_data['class_code']
    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
 
    all_student_ids = list(context.user_data['students'].values())
    for student_id in all_student_ids:
        is_present = 0 if student_id in student_ids else 1
        cursor.execute('''
            INSERT INTO attendance_records (student_id, attendance_date, is_present)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id, attendance_date)
            DO UPDATE SET is_present=excluded.is_present
        ''', (student_id, attendance_date_str, is_present))
    connection.commit()
    connection.close()

    await update.message.reply_text(f"Отсутствующие студенты отмечены на дату {attendance_date_str} в классе {class_code}.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def start_mark_present(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Укажите код класса, для которого нужно отметить присутствующих.")
    return MARK_PRESENT_CLASS

async def mark_present_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class_code = update.message.text.strip()
    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('SELECT id FROM classes WHERE class_code = ?', (class_code,))
    class_info = cursor.fetchone()

    if class_info is None:
        await update.message.reply_text("Класс не найден. Попробуйте снова.")
        return MARK_PRESENT_CLASS

    context.user_data['class_code'] = class_code
    context.user_data['class_id'] = class_info[0]
    await update.message.reply_text("Укажите дату в формате ГГГГ-ММ-ДД, на которую нужно отметить присутствующих.")
    return MARK_PRESENT_DATE

async def mark_present_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    attendance_date_str = update.message.text.strip()
    try:
        attendance_date = datetime.strptime(attendance_date_str, "%Y-%m-%d").date()
        context.user_data['attendance_date'] = attendance_date_str
    except ValueError:
        await update.message.reply_text("Некорректный формат даты. Пожалуйста, используйте формат ГГГГ-ММ-ДД.")
        return MARK_PRESENT_DATE

    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('SELECT id, full_name FROM students WHERE class_id = ?', (context.user_data['class_id'],))
    students = cursor.fetchall()
    connection.close()

    if not students:
        await update.message.reply_text("В этом классе нет студентов.")
        return ConversationHandler.END

    student_list = "\n".join([f"{i+1}. {student[1]}" for i, student in enumerate(students)])
    context.user_data['students'] = {str(i+1): student[0] for i, student in enumerate(students)}
    await update.message.reply_text(f"Студенты в классе {context.user_data['class_code']}:\n{student_list}\n\nВведите номера присутствующих через пробел.")
    return MARK_PRESENT_NAMES

async def mark_present_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_numbers = update.message.text.split()
    student_ids = [context.user_data['students'].get(number) for number in student_numbers if number in context.user_data['students']]
    attendance_date_str = context.user_data['attendance_date']

    class_code = context.user_data['class_code']
    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()

    all_student_ids = list(context.user_data['students'].values())
    for student_id in all_student_ids:
        is_present = 1 if student_id in student_ids else 0
        cursor.execute('''
            INSERT INTO attendance_records (student_id, attendance_date, is_present)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id, attendance_date)
            DO UPDATE SET is_present=excluded.is_present
        ''', (student_id, attendance_date_str, is_present))
    connection.commit()
    connection.close()

    await update.message.reply_text(f"Присутствующие студенты отмечены на дату {attendance_date_str} в классе {class_code}.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def show_classes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('SELECT class_code FROM classes')
    classes = cursor.fetchall()
    connection.close()

    if not classes:
        await update.message.reply_text("Нет доступных классов.")
        return

    response = "Список классов:\n" + "\n".join([cls[0] for cls in classes])
    await update.message.reply_text(response)

async def show_students_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пожалуйста, укажите код класса.")
    return SHOW_STUDENTS_CLASS

async def show_students_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class_code = update.message.text.strip()
    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('SELECT id FROM classes WHERE class_code = ?', (class_code,))
    class_info = cursor.fetchone()

    if class_info is None:
        await update.message.reply_text("Класс не найден. Попробуйте снова.")
        return SHOW_STUDENTS_CLASS

    class_id = class_info[0]
    cursor.execute('SELECT full_name FROM students WHERE class_id = ?', (class_id,))
    students = cursor.fetchall()
    connection.close()

    if not students:
        await update.message.reply_text("В этом классе нет студентов.", reply_markup=ReplyKeyboardRemove())
    else:
        student_list = "\n".join([student[0] for student in students])
        await update.message.reply_text(f"Студенты в классе {class_code}:\n{student_list}", reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END

async def attendance_info_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Укажите код класса.")
    return ATTENDANCE_INFO_CLASS

async def attendance_info_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class_code = update.message.text.strip()
    context.user_data['class_code'] = class_code
    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('SELECT id FROM classes WHERE class_code = ?', (class_code,))
    class_info = cursor.fetchone()

    if class_info is None:
        await update.message.reply_text("Класс не найден. Попробуйте снова.")
        return ATTENDANCE_INFO_CLASS

    context.user_data['class_id'] = class_info[0]
   
    cursor.execute('''
        SELECT DISTINCT attendance_date FROM attendance_records ar
        JOIN students s ON ar.student_id = s.id
        WHERE s.class_id = ?
        ORDER BY attendance_date
    ''', (context.user_data['class_id'],))
    dates = cursor.fetchall()
    connection.close()

    if not dates:
        await update.message.reply_text(f"Нет данных о посещаемости для класса {class_code}.")
        return ConversationHandler.END

    date_list = "\n".join([f"{i+1}. {date[0]}" for i, date in enumerate(dates)])
    context.user_data['dates'] = {str(i+1): date[0] for i, date in enumerate(dates)}
    await update.message.reply_text(f"Доступные даты для класса {class_code}:\n{date_list}\n\nВведите номер даты для получения информации о посещаемости.")
    return ATTENDANCE_INFO_DATE_SELECT

async def attendance_info_date_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_number = update.message.text.strip()
    attendance_date_str = context.user_data['dates'].get(date_number)
    if not attendance_date_str:
        await update.message.reply_text("Некорректный номер даты. Попробуйте снова.")
        return ATTENDANCE_INFO_DATE_SELECT

    class_id = context.user_data['class_id']
    class_code = context.user_data['class_code']

    connection = sqlite3.connect('attendance.db')
    cursor = connection.cursor()
    cursor.execute('''
        SELECT s.full_name, ar.is_present
        FROM students s
        LEFT JOIN attendance_records ar ON s.id = ar.student_id AND ar.attendance_date = ?
        WHERE s.class_id = ?
    ''', (attendance_date_str, class_id))
    records = cursor.fetchall()
    connection.close()

    response = f"Посещаемость класса {class_code} на дату {attendance_date_str}:\n"
    response += "Имя студента | Присутствие\n"
    for student_name, is_present in records:
        if is_present is None:
            status = 'Не отмечен'
        elif is_present == 1:
            status = 'Присутствовал'
        else:
            status = 'Отсутствовал'
        response += f"{student_name} | {status}\n"

    await update.message.reply_text(response, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def show_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    instructions_text = (
        "Примеры использования команд:\n"
        "/createclass - Создать новый класс\n"
        "/enrollstudent - Добавить студента в класс\n"
        "/recordabsence - Отметить отсутствующих студентов на определенную дату\n"
        "/markpresent - Отметить присутствующих студентов на определенную дату\n"
        "/attendanceinfo - Получить информацию о посещаемости\n"
        "/showclasses - Показать все классы\n"
        "/showstudents - Показать всех студентов в указанном классе\n"
        "/cancel - Отменить текущую операцию"
    )
    await update.message.reply_text(instructions_text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    setup_database()
    app = Application.builder().token("7983934980:AAFf1OHm-HFv-qzA-1TalONiq0xaGWEGeWM").build()

    conv_create_class = ConversationHandler(
        entry_points=[CommandHandler("createclass", start_create_class)],
        states={
            CREATE_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_class)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    conv_enroll_student = ConversationHandler(
        entry_points=[CommandHandler("enrollstudent", start_enroll_student)],
        states={
            ENROLL_STUDENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enroll_student)],
            ENROLL_STUDENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enroll_student_name)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    conv_record_absence = ConversationHandler(
        entry_points=[CommandHandler("recordabsence", start_record_absence)],
        states={
            RECORD_ABSENCE_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, record_absence_class)],
            RECORD_ABSENCE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, record_absence_date)],
            RECORD_ABSENCE_NAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, record_absence_names)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    conv_mark_present = ConversationHandler(
        entry_points=[CommandHandler("markpresent", start_mark_present)],
        states={
            MARK_PRESENT_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, mark_present_class)],
            MARK_PRESENT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, mark_present_date)],
            MARK_PRESENT_NAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, mark_present_names)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    conv_show_students = ConversationHandler(
        entry_points=[CommandHandler("showstudents", show_students_start)],
        states={
            SHOW_STUDENTS_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_students_class)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    conv_attendance_info = ConversationHandler(
        entry_points=[CommandHandler("attendanceinfo", attendance_info_start)],
        states={
            ATTENDANCE_INFO_CLASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, attendance_info_class)],
            ATTENDANCE_INFO_DATE_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, attendance_info_date_select)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", greet_user))
    app.add_handler(conv_create_class)
    app.add_handler(conv_enroll_student)
    app.add_handler(conv_record_absence)
    app.add_handler(conv_mark_present)
    app.add_handler(conv_show_students)
    app.add_handler(conv_attendance_info)
    app.add_handler(CommandHandler("showclasses", show_classes))
    app.add_handler(CommandHandler("help", show_instructions))
    app.add_handler(CommandHandler("cancel", cancel))

    app.run_polling()

if __name__ == '__main__':
    main()

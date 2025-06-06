import logging
import random
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InputFile
from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Состояние сессии пользователей
user_sessions = {}

# Типы форматов
FORMAT_MARKED = 'marked'
FORMAT_NUMBERED = 'numbered'

# Обработка /start
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await message.answer("Привет! Отправь мне текстовый файл (.txt) с вопросами. "
                         "Формат:\n\n1) Вопрос с ответами:\nXAMPP командалық жолы\n- Кодты редакциялау\n+ Қызметтерді іске қосу және тоқтату\n"
                         "2) Или с номерами:\nҚайсысы HTML тегі?\n1) table\n2) bold\n3) css\n4) img\nПравильный ответ: 1\n\n"
                         "Я проведу тест, и ты получишь результат!")

# Загрузка файла
@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def handle_file(message: types.Message):
    document = message.document
    if not document.file_name.endswith('.txt'):
        await message.answer("Пожалуйста, отправь файл с расширением .txt.")
        return

    file_path = f"temp/{document.file_name}"
    await document.download(destination_file=file_path)

    with open(file_path, encoding='utf-8') as f:
        content = f.read()

    questions = parse_questions(content)

    if not questions:
        await message.answer("Не удалось распознать вопросы. Проверь формат.")
        return

    # Перемешиваем вопросы
    random.shuffle(questions)

    user_sessions[message.from_user.id] = {
        'questions': questions,
        'current': 0,
        'correct': 0
    }

    await send_question(message.from_user.id)


async def send_question(user_id):
    session = user_sessions[user_id]
    if session['current'] >= len(session['questions']):
        await bot.send_message(user_id, f"✅ Тест завершён! Правильных ответов: {session['correct']} из {len(session['questions'])}")
        del user_sessions[user_id]
        return

    q = session['questions'][session['current']]
    text = f"❓ {q['question']}\n\n"
    options = q['answers']
    random.shuffle(options)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for option in options:
        markup.add(option)
    session['shuffled'] = options
    await bot.send_message(user_id, text, reply_markup=markup)


@dp.message_handler()
async def answer_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions:
        await message.answer("Начни с /start и загрузи файл с вопросами.")
        return

    session = user_sessions[user_id]
    q = session['questions'][session['current']]
    correct = q['correct']

    if message.text.strip() == correct:
        session['correct'] += 1
        await message.answer("✅ Верно!")
    else:
        await message.answer(f"❌ Неверно! Правильный ответ: {correct}")

    session['current'] += 1
    await send_question(user_id)


def parse_questions(text):
    lines = text.strip().split('\n')
    questions = []
    buffer = []
    current_question = None
    current_format = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Новый вопрос (строка без маркеров)
        if not line.startswith(('-', '+', '1)', '2)', '3)', '4)', 'Правильный ответ')):
            if current_question and buffer:
                parsed = process_question(current_question, buffer, current_format)
                if parsed:
                    questions.append(parsed)
            current_question = line
            buffer = []
            current_format = None
        else:
            buffer.append(line)
            if any(line.startswith(x) for x in ['+', '-']):
                current_format = FORMAT_MARKED
            elif any(line.startswith(x) for x in ['1)', '2)', '3)', '4)']):
                current_format = FORMAT_NUMBERED

        i += 1

    # Последний вопрос
    if current_question and buffer:
        parsed = process_question(current_question, buffer, current_format)
        if parsed:
            questions.append(parsed)

    return questions


def process_question(question, lines, fmt):
    if fmt == FORMAT_MARKED:
        answers = []
        correct = ''
        for line in lines:
            if line.startswith('+'):
                correct = line[1:].strip()
                answers.append(correct)
            elif line.startswith('-'):
                answers.append(line[1:].strip())
        if correct:
            return {'question': question, 'answers': answers, 'correct': correct}
    elif fmt == FORMAT_NUMBERED:
        answers = []
        correct = ''
        for line in lines:
            if line.startswith('Правильный ответ'):
                correct_num = line.split(':')[-1].strip()
                try:
                    correct = next(ans[3:].strip() for ans in answers if ans.startswith(f"{correct_num})"))
                except:
                    return None
            else:
                answers.append(line)
        if correct:
            clean_answers = [ans[3:].strip() for ans in answers]
            return {'question': question, 'answers': clean_answers, 'correct': correct}
    return None

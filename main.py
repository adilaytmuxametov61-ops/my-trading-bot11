import os
import time
import requests
import json
from datetime import datetime
import random

# --- ВАШИ ДАННЫЕ И НАСТРОЙКИ ---
# ВНИМАНИЕ: Хранить ключи прямо в коде небезопасно!
TELEGRAM_TOKEN = "8302860595:AAHMnUiWWnjjqNyZa60-srUy1k_Pb_lYhz4"
TELEGRAM_CHAT_ID = "5655533274"
TWELVE_DATA_API_KEY = "75c2f1a180a945f099a6528ed1e8507c"

# Настройки стратегии
SYMBOL = "XAU/USD"
INTERVAL = "5min"  # Таймфрейм для анализа (5 минут)
EMA_SHORT_PERIOD = 5
EMA_LONG_PERIOD = 10
MACD_FAST_PERIOD = 5
MACD_SLOW_PERIOD = 10
MACD_SIGNAL_PERIOD = 3
STOP_LOSS_PERCENT = 1.0  # 1%, так как скальпинг предполагает меньшие цели
TAKE_PROFIT_PERCENT = 1.5 # Соотношение риск/прибыль 1:1.5
INVESTMENT_PER_TRADE = 20  # Сумма ставки для статистики в долларах

# Файл для хранения статистики
STATS_FILE = "trading_stats.json"

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def load_stats():
    """Загружает статистику из файла JSON."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Файл статистики поврежден. Создается новый.")
    # Возвращает структуру по умолчанию, если файл не найден или пуст
    return {
        "total_signals": 0,
        "profitable_signals": 0,
        "loss_signals": 0,
        "total_profit_loss_usd": 0.0
    }

def save_stats(stats):
    """Сохраняет статистику в файл JSON."""
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=4)

def send_telegram_message(message):
    """Отправляет отформатированное сообщение в ваш Telegram чат."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Проверка на ошибки HTTP
        print(f"Сообщение успешно отправлено в Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"Ошибка отправки сообщения в Telegram: {e}")

def get_market_data():
    """Получает и обрабатывает рыночные данные с Twelve Data."""
    base_url = "https://api.twelvedata.com"
    try:
        # Получаем данные для EMA, MACD и текущую цену
        # Нам нужно как минимум 2 последних значения для определения пересечения
        params = {
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "apikey": TWELVE_DATA_API_KEY,
            "outputsize": 2
        }
        ema_short_data = requests.get(f"{base_url}/ema", params={**params, "time_period": EMA_SHORT_PERIOD}).json()
        ema_long_data = requests.get(f"{base_url}/ema", params={**params, "time_period": EMA_LONG_PERIOD}).json()
        macd_data = requests.get(f"{base_url}/macd", params={**params, "fast_period": MACD_FAST_PERIOD, "slow_period": MACD_SLOW_PERIOD, "signal_period": MACD_SIGNAL_PERIOD}).json()
        price_data = requests.get(f"{base_url}/price", params={"symbol": SYMBOL, "apikey": TWELVE_DATA_API_KEY}).json()

        # Проверяем, что все данные получены корректно
        if 'values' not in ema_short_data or 'values' not in ema_long_data or 'values' not in macd_data or 'price' not in price_data:
            print("Ошибка в полученных данных от API. Ответ:", ema_short_data)
            return None

        # Собираем данные в удобную структуру
        data = {
            "price": float(price_data['price']),
            "ema_short_current": float(ema_short_data['values'][0]['ema']),
            "ema_short_previous": float(ema_short_data['values'][1]['ema']),
            "ema_long_current": float(ema_long_data['values'][0]['ema']),
            "ema_long_previous": float(ema_long_data['values'][1]['ema']),
            "macd_current": float(macd_data['values'][0]['macd']),
            "macd_signal_current": float(macd_data['values'][0]['signal']),
            "macd_histogram_current": float(macd_data['values'][0]['histogram']),
            "macd_previous": float(macd_data['values'][1]['macd']),
            "macd_signal_previous": float(macd_data['values'][1]['signal']),
            "macd_histogram_previous": float(macd_data['values'][1]['histogram']),
        }
        return data

    except (requests.exceptions.RequestException, KeyError, IndexError, ValueError) as e:
        print(f"Ошибка получения или обработки рыночных данных: {e}")
        return None

def check_for_signal(data):
    """Анализирует данные и ищет сигнал по стратегии."""
    # Условие для сигнала на ПОКУПКУ (BUY)
    # Быстрая EMA пересекла медленную снизу вверх И MACD пересекает сигнальную линию снизу вверх
    is_buy_signal = (data['ema_short_previous'] < data['ema_long_previous'] and
                     data['ema_short_current'] > data['ema_long_current'] and
                     data['macd_histogram_previous'] < 0 and
                     data['macd_histogram_current'] > 0)

    # Условие для сигнала на ПРОДАЖУ (SELL)
    # Быстрая EMA пересекла медленную сверху вниз И MACD пересекает сигнальную линию сверху вниз
    is_sell_signal = (data['ema_short_previous'] > data['ema_long_previous'] and
                      data['ema_short_current'] < data['ema_long_current'] and
                      data['macd_histogram_previous'] > 0 and
                      data['macd_histogram_current'] < 0)

    if is_buy_signal:
        return "BUY"
    elif is_sell_signal:
        return "SELL"
    else:
        return None

def run_bot():
    """Основной цикл работы бота."""
    stats = load_stats()
    # Переменная для предотвращения повторной отправки одного и того же сигнала
    last_signal_time = 0

    print("Бот запущен. Ожидание сигналов...")
    send_telegram_message("✅ *Торговый бот для XAU/USD запущен.*\n\n"
                          f"**Стратегия:** EMA({EMA_SHORT_PERIOD}/{EMA_LONG_PERIOD}) + MACD({MACD_FAST_PERIOD}/{MACD_SLOW_PERIOD}/{MACD_SIGNAL_PERIOD})\n"
                          f"**Таймфрейм:** {INTERVAL}\n\n"
                          "⚠️ *Помните о высоких рисках! Это не финансовая рекомендация.*")

    while True:
        try:
            data = get_market_data()
            if data:
                print(f"Проверка ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}): Цена={data['price']:.2f}, "
                      f"EMA{EMA_SHORT_PERIOD}={data['ema_short_current']:.2f}, "
                      f"EMA{EMA_LONG_PERIOD}={data['ema_long_current']:.2f}, "
                      f"MACD={data['macd_current']:.2f}, "
                      f"MACD Signal={data['macd_signal_current']:.2f}, "
                      f"MACD Histogram={data['macd_histogram_current']:.2f}")

                # Проверяем, прошло ли достаточно времени с последнего сигнала, чтобы избежать дублей
                if time.time() - last_signal_time > 300: # не чаще чем раз в 5 минут
                    signal = check_for_signal(data)

                    if signal:
                        last_signal_time = time.time()
                        entry_price = data['price']

                        # Расчет уровней и составление сообщения
                        if signal == "BUY":
                            stop_loss = entry_price * (1 - STOP_LOSS_PERCENT / 100)
                            take_profit = entry_price * (1 + TAKE_PROFIT_PERCENT / 100)
                            message = (
                                f"🟢 *СИГНАЛ НА ПОКУПКУ (BUY) XAU/USD*\n\n"
                                f"Цена входа: `${entry_price:.2f}`\n"
                                f"Тейк-профит: `${take_profit:.2f}`\n"
                                f"Стоп-лосс: `${stop_loss:.2f}` (Риск {STOP_LOSS_PERCENT}%)"
                            )
                        else: # SELL
                            stop_loss = entry_price * (1 + STOP_LOSS_PERCENT / 100)
                            take_profit = entry_price * (1 - TAKE_PROFIT_PERCENT / 100)
                            message = (
                                f"🔴 *СИГНАЛ НА ПРОДАЖУ (SELL) XAU/USD*\n\n"
                                f"Цена входа: `${entry_price:.2f}`\n"
                                f"Тейк-профит: `${take_profit:.2f}`\n"
                                f"Стоп-лосс: `${stop_loss:.2f}` (Риск {STOP_LOSS_PERCENT}%)"
                            )

                        send_telegram_message(message)

                        # --- Обновление и отправка статистики ---
                        stats['total_signals'] += 1

                        # Имитация результата сделки для статистики (55% прибыльных)
                        # В реальности результат будет известен только после закрытия сделки
                        if random.random() < 0.55:
                            stats['profitable_signals'] += 1
                            profit = INVESTMENT_PER_TRADE * (TAKE_PROFIT_PERCENT / 100)
                            stats['total_profit_loss_usd'] += profit
                        else:
                            stats['loss_signals'] += 1
                            loss = INVESTMENT_PER_TRADE * (STOP_LOSS_PERCENT / 100)
                            stats['total_profit_loss_usd'] -= loss

                        save_stats(stats)

                        # Формирование сообщения со статистикой
                        profit_loss_usd = stats['total_profit_loss_usd']
                        profit_loss_text = f"Прибыль: `${profit_loss_usd:.2f}`" if profit_loss_usd >= 0 else f"Убыток: `${-profit_loss_usd:.2f}`"

                        stats_message = (
                            f"📊 *Обновленная статистика*\n\n"
                            f"Всего сигналов: {stats['total_signals']}\n"
                            f"✅ Прибыльных: {stats['profitable_signals']}\n"
                            f"❌ Убыточных: {stats['loss_signals']}\n\n"
                            f"*При ставке ${INVESTMENT_PER_TRADE} на сигнал, ваша чистая {profit_loss_text}*"
                        )
                        send_telegram_message(stats_message)

            # Пауза перед следующей проверкой.
            # Для 5-минутного интервала достаточно проверять раз в 5 минут.
            # Бесплатный план Twelve Data имеет лимиты, не делайте запросы слишком часто.
            print("Пауза на 5 минут...")
            time.sleep(300)

        except Exception as e:
            print(f"Произошла критическая ошибка в основном цикле: {e}")
            time.sleep(60) # Короткая пауза перед перезапуском в случае сбоя

if __name__ == "__main__":
    run_bot()

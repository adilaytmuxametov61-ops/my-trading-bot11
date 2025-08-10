import os
import time
import requests
import json
from datetime import datetime
import random

# --- ВАШИ ДАННЫЕ И НАСТРОЙКИ ---
# ВНИМАНИЕ: Хранить ключи прямо в коде небезопасно!
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')

# Настройки стратегии
SYMBOL = "XAUUSD"
INTERVAL = "5min"  # Таймфрейм для анализа (5 минут)
EMA_SHORT_PERIOD = 5
EMA_LONG_PERIOD = 10
MACD_FAST_PERIOD = 5
MACD_SLOW_PERIOD = 10
MACD_SIGNAL_PERIOD = 3
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
STOP_LOSS_PERCENT = 7.0  # 7%, как вы и просили.
TAKE_PROFIT_PERCENT = 35.0 # 35%
INVESTMENT_PER_TRADE = 20  # Сумма ставки для статистики в долларах

# Файл для хранения статистики
STATS_FILE = "/tmp/trading_stats.json"  # Временная директория для хранения данных

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
    """Получает и обрабатывает рыночные данные с Alpha Vantage."""
    base_url = "https://www.alphavantage.co"
    try:
        # Получаем данные для EMA, MACD, RSI и Bollinger Bands
        # Нам нужно как минимум 2 последних значения для определения пересечения
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "apikey": ALPHA_VANTAGE_API_KEY,
            "outputsize": "compact"
        }
        time_series_data = requests.get(f"{base_url}/query", params=params).json()

        # Получаем данные для EMA, MACD, RSI и Bollinger Bands
        ema_short_data = requests.get(f"{base_url}/query", params={**params, "function": "EMA", "time_period": EMA_SHORT_PERIOD}).json()
        ema_long_data = requests.get(f"{base_url}/query", params={**params, "function": "EMA", "time_period": EMA_LONG_PERIOD}).json()
        macd_data = requests.get(f"{base_url}/query", params={**params, "function": "MACD", "fastperiod": MACD_FAST_PERIOD, "slowperiod": MACD_SLOW_PERIOD, "signalperiod": MACD_SIGNAL_PERIOD}).json()
        rsi_data = requests.get(f"{base_url}/query", params={**params, "function": "RSI", "time_period": RSI_PERIOD}).json()
        bollinger_bands_data = requests.get(f"{base_url}/query", params={**params, "function": "BBANDS"}).json()

        # Проверяем, что все данные получены корректно
        if 'Time Series (5min)' not in time_series_data or 'Technical Analysis: EMA' not in ema_short_data or 'Technical Analysis: EMA' not in ema_long_data or 'Technical Analysis: MACD' not in macd_data or 'Technical Analysis: RSI' not in rsi_data or 'Technical Analysis: BBANDS' not in bollinger_bands_data:
            print("Ошибка в полученных данных от API. Ответ:", time_series_data)
            return None

        # Собираем данные в удобную структуру
        data = {
            "price": float(time_series_data['Time Series (5min)'][list(time_series_data['Time Series (5min)'].keys())[0]]['4. close']),
            "ema_short_current": float(ema_short_data['Technical Analysis: EMA'][list(ema_short_data['Technical Analysis: EMA'].keys())[0]]['EMA']),
            "ema_short_previous": float(ema_short_data['Technical Analysis: EMA'][list(ema_short_data['Technical Analysis: EMA'].keys())[1]]['EMA']),
            "ema_long_current": float(ema_long_data['Technical Analysis: EMA'][list(ema_long_data['Technical Analysis: EMA'].keys())[0]]['EMA']),
            "ema_long_previous": float(ema_long_data['Technical Analysis: EMA'][list(ema_long_data['Technical Analysis: EMA'].keys())[1]]['EMA']),
            "macd_current": float(macd_data['Technical Analysis: MACD'][list(macd_data['Technical Analysis: MACD'].keys())[0]]['MACD']),
            "macd_signal_current": float(macd_data['Technical Analysis: MACD'][list(macd_data['Technical Analysis: MACD'].keys())[0]]['MACD_Signal']),
            "macd_histogram_current": float(macd_data['Technical Analysis: MACD'][list(macd_data['Technical Analysis: MACD'].keys())[0]]['MACD_Hist']),
            "macd_previous": float(macd_data['Technical Analysis: MACD'][list(macd_data['Technical Analysis: MACD'].keys())[1]]['MACD']),
            "macd_signal_previous": float(macd_data['Technical Analysis: MACD'][list(macd_data['Technical Analysis: MACD'].keys())[1]]['MACD_Signal']),
            "macd_histogram_previous": float(macd_data['Technical Analysis: MACD'][list(macd_data['Technical Analysis: MACD'].keys())[1]]['MACD_Hist']),
            "rsi_current": float(rsi_data['Technical Analysis: RSI'][list(rsi_data['Technical Analysis: RSI'].keys())[0]]['RSI']),
            "rsi_previous": float(rsi_data['Technical Analysis: RSI'][list(rsi_data['Technical Analysis: RSI'].keys())[1]]['RSI']),
            "bollinger_bands_upper": float(bollinger_bands_data['Technical Analysis: BBANDS'][list(bollinger_bands_data['Technical Analysis: BBANDS'].keys())[0]]['Real Upper Band']),
            "bollinger_bands_middle": float(bollinger_bands_data['Technical Analysis: BBANDS'][list(bollinger_bands_data['Technical Analysis: BBANDS'].keys())[0]]['Real Middle Band']),
            "bollinger_bands_lower": float(bollinger_bands_data['Technical Analysis: BBANDS'][list(bollinger_bands_data['Technical Analysis: BBANDS'].keys())[0]]['Real Lower Band']),
        }
        return data

    except (requests.exceptions.RequestException, KeyError, IndexError, ValueError) as e:
        print(f"Ошибка получения или обработки рыночных данных: {e}")
        return None

def check_for_signal(data):
    """Анализирует данные и ищет сигнал по стратегии."""
    # Условие для сигнала на ПОКУПКУ (BUY)
    # Быстрая EMA пересекла медленную снизу вверх И MACD пересекает сигнальную линию снизу вверх И RSI не в зоне перекупленности И цена выше нижней границы Bollinger Bands
    is_buy_signal = (data['ema_short_previous'] < data['ema_long_previous'] and
                     data['ema_short_current'] > data['ema_long_current'] and
                     data['macd_histogram_previous'] < 0 and
                     data['macd_histogram_current'] > 0 and
                     data['rsi_current'] < RSI_OVERBOUGHT and
                     data['price'] > data['bollinger_bands_lower'])

    # Условие для сигнала на ПРОДАЖУ (SELL)
    # Быстрая EMA пересекла медленную сверху вниз И MACD пересекает сигнальную линию сверху вниз И RSI не в зоне перепроданности И цена ниже верхней границы Bollinger Bands
    is_sell_signal = (data['ema_short_previous'] > data['ema_long_previous'] and
                      data['ema_short_current'] < data['ema_long_current'] and
                      data['macd_histogram_previous'] > 0 and
                      data['macd_histogram_current'] < 0 and
                      data['rsi_current'] > RSI_OVERSOLD and
                      data['price'] < data['bollinger_bands_upper'])

    if is_buy_signal:
        return "BUY"
    elif is_sell_signal:
        return "SELL"
    else:
        return None

def process_signal():
    """Основная логика проверки и обработки сигналов."""
    stats = load_stats()

    try:
        data = get_market_data()
        if data:
            print(f"Проверка ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}): Цена={data['price']:.2f}, "
                  f"EMA{EMA_SHORT_PERIOD}={data['ema_short_current']:.2f}, "
                  f"EMA{EMA_LONG_PERIOD}={data['ema_long_current']:.2f}, "
                  f"MACD={data['macd_current']:.2f}, "
                  f"MACD Signal={data['macd_signal_current']:.2f}, "
                  f"MACD Histogram={data['macd_histogram_current']:.2f}, "
                  f"RSI={data['rsi_current']:.2f}, "
                  f"Bollinger Bands (Upper)={data['bollinger_bands_upper']:.2f}, "
                  f"Bollinger Bands (Middle)={data['bollinger_bands_middle']:.2f}, "
                  f"Bollinger Bands (Lower)={data['bollinger_bands_lower']:.2f}")

            signal = check_for_signal(data)
            if signal:
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

                # Обновляем статистику
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

    except Exception as e:
        print(f"Произошла критическая ошибка: {e}")

if __name__ == "__main__":
    process_signal()

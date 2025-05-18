import requests
import pandas as pd
import asyncio
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = "7889785497:AAFPyYGdi-aCNZp-KbitYvQdpb9Te8ugowE"

# Estado global
monitoring = False
chat_id = None
pair = "BTCUSDT"
interval = "1m"
signal_history_file = "signal_history.txt"

bot = Bot(token=TELEGRAM_TOKEN)

# Obtener datos de Binance
def obtener_datos_binance(symbol, interval, limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    r = requests.get(url)
    data = r.json()
    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ])
    df["close"] = df["close"].astype(float)
    return df

# Análisis con indicadores
def analizar(df):
    bb_window = 12
    rsi_window = 14
    ema_window = 10

    bb = BollingerBands(close=df['close'], window=bb_window, window_dev=2)
    rsi = RSIIndicator(close=df['close'], window=rsi_window)
    ema = EMAIndicator(close=df['close'], window=ema_window)

    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    df['rsi'] = rsi.rsi()
    df['ema'] = ema.ema_indicator()

    ultima = df.iloc[-1]
    mensaje = None

    if ultima['close'] <= ultima['bb_lower'] and ultima['rsi'] <= 35 and ultima['close'] > ultima['ema']:
        mensaje = f"✅ SEÑAL COMPRA {pair}\nPrecio: {ultima['close']:.2f} USDT\nBanda Inferior + RSI bajo + Precio sobre EMA"
    elif ultima['close'] >= ultima['bb_upper'] and ultima['rsi'] >= 65 and ultima['close'] < ultima['ema']:
        mensaje = f"❌ SEÑAL VENTA {pair}\nPrecio: {ultima['close']:.2f} USDT\nBanda Superior + RSI alto + Precio bajo EMA"

    return mensaje

# Guardar señales en historial
def guardar_historial(mensaje):
    with open(signal_history_file, "a") as f:
        f.write(mensaje + "\n")

async def monitor_loop(context: ContextTypes.DEFAULT_TYPE):
    global monitoring, chat_id
    while monitoring:
        try:
            df = obtener_datos_binance(pair, interval)
            señal = analizar(df)

            ultimo_precio = df.iloc[-1]['close']

            if señal:
                guardar_historial(señal)
                await context.bot.send_message(chat_id=chat_id, text=señal)

            # Mensaje con el último precio cada vez que chequea
            await context.bot.send_message(chat_id=chat_id, text=f"📈 Último precio {pair}: {ultimo_precio:.2f} USDT")

            await asyncio.sleep(60)
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Error: {e}")
            await asyncio.sleep(60)
# Comando para iniciar monitoreo
async def monitorar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitoring, chat_id
    if monitoring:
        await update.message.reply_text("Ya estoy monitoreando señales.")
        return

    chat_id = update.effective_chat.id
    await update.message.reply_text(f"🤖 Bot activado. Monitoreando {pair} cada {interval}...")
    monitoring = True

    context.application.create_task(monitor_loop(context))

# Comando para detener monitoreo
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitoring
    if not monitoring:
        await update.message.reply_text("El bot ya está detenido.")
        return
    monitoring = False
    await update.message.reply_text("Bot detenido. No enviaré más señales.")

# Comando para cambiar par (activo)
async def setpair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global pair
    if len(context.args) != 1:
        await update.message.reply_text("Usa: /setpair BTCUSDT")
        return
    nuevo_par = context.args[0].upper()
    pair = nuevo_par
    await update.message.reply_text(f"Par cambiado a {pair}")

# Comando para cambiar intervalo
async def setinterval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global interval
    if len(context.args) != 1:
        await update.message.reply_text("Usa: /setinterval 1m (valores válidos: 1m,3m,5m,15m,30m,1h, etc.)")
        return
    nuevo_int = context.args[0]
    interval = nuevo_int
    await update.message.reply_text(f"Intervalo cambiado a {interval}")

# Comando para mostrar ayuda
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🤖 Comandos disponibles:\n"
        "/signal - Iniciar monitoreo de señales\n"
        "/stop - Detener monitoreo\n"
        "/setpair [PAR] - Cambiar par (ej: BTCUSDT, ETHUSDT)\n"
        "/setinterval [INTERVALO] - Cambiar intervalo (ej: 1m, 5m, 1h)\n"
        "/help - Mostrar esta ayuda\n"
    )
    await update.message.reply_text(texto)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("signal", monitorar))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("setpair", setpair))
    app.add_handler(CommandHandler("setinterval", setinterval))
    app.add_handler(CommandHandler("help", help_command))

    print("Bot arrancando...")
    app.run_polling()
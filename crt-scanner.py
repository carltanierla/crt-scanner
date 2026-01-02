import requests
import pandas as pd
import time
import json
from datetime import datetime
from colorama import Fore, Style, init

# Initialize color output
init(autoreset=True)

# --- CONFIGURATION ---
BASE_URL = "https://contract.mexc.co"
TIMEFRAMES = ["Min60", "Hour4"]         # MEXC API codes for 1h and 4h
CHECK_LIMIT = 800                       # Number of pairs to check
MIN_VOL_USDT = 500000                   # Volume filter
SCAN_INTERVAL = 900                     # 15 Minutes in seconds
# PASTE YOUR DISCORD WEBHOOK URL HERE vvv
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

def send_discord_alert(matches):
    """Sends a summary of matches to Discord via Webhook."""
    if not matches:
        return

    # Build the message content
    message_content = "**CRT Reversal Signals Detected** 🚨\n"
    message_content += f"Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for m in matches:
        emoji = "🔴" if m['type'] == "BEARISH" else "🟢"
        tf_emoji = "⏱️"
        # MEXC Futures Link
        link = f"https://futures.mexc.com/exchange/{m['symbol']}"
        message_content += f"{emoji} **{m['symbol']}** [{m['type']}]\n"
        message_content += f"{tf_emoji} Timeframe: {m['tf']}\n"
        message_content += f"🔗 [View Chart]({link})\n\n"

    payload = {
        "content": message_content,
        "username": "CRT Scanner Bot"
    }

    try:
        requests.post(WEBHOOK_URL, json=payload)
        print(f"{Fore.MAGENTA}>> Notification sent to Discord!{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Failed to send Discord alert: {e}")

def get_futures_symbols():
    """Fetch all active USDT-margined futures pairs."""
    try:
        url = f"{BASE_URL}/api/v1/contract/detail"
        response = requests.get(url, timeout=10).json()
        if not response.get('success'):
            return []
        
        symbols = []
        for item in response['data']:
            if item['quoteCoin'] == 'USDT' and item['state'] == 0:
                symbols.append(item['symbol'])
        return symbols
    except Exception as e:
        print(f"{Fore.RED}Error fetching symbols: {e}")
        return []

def get_klines(symbol, interval, limit=15):
    """Fetch OHLCV data."""
    try:
        url = f"{BASE_URL}/api/v1/contract/kline/{symbol}"
        params = {'interval': interval, 'limit': limit}
        response = requests.get(url, params=params, timeout=5).json()
        
        if not response.get('success'):
            return None
        
        data = response['data']
        df = pd.DataFrame({
            'time': data['time'],
            'open': data['open'],
            'high': data['high'],
            'low': data['low'],
            'close': data['close']
        }, dtype=float)
        
        return df
    except Exception:
        return None

def analyze_candle(row, recent_highs, recent_lows):
    """
    Analyzes a candle for CRT Reversal Patterns.
    """
    body = abs(row['open'] - row['close'])
    upper_wick = row['high'] - max(row['open'], row['close'])
    lower_wick = min(row['open'], row['close']) - row['low']
    total_range = row['high'] - row['low']
    
    if total_range == 0: return None

    # --- SCENARIO 1: BEARISH SHOOTING STAR ---
    # 1. Long Upper Wick (>= 2.5x body)
    # 2. Small Body (<= 30% of range)
    # 3. Close in bottom 30% (Bearish close)
    # 4. Sweep: High is the highest of recent candles
    is_shooting_star = (
        upper_wick >= (2.5 * body) and
        body <= (0.3 * total_range) and
        (row['close'] - row['low']) <= (0.3 * total_range) and
        row['high'] >= max(recent_highs)
    )

    if is_shooting_star:
        return "BEARISH"

    # --- SCENARIO 2: BULLISH HAMMER ---
    # 1. Long Lower Wick (>= 2.5x body)
    # 2. Small Body (<= 30% of range)
    # 3. Close in top 30% (Bullish close)
    # 4. Sweep: Low is the lowest of recent candles
    is_hammer = (
        lower_wick >= (2.5 * body) and
        body <= (0.3 * total_range) and
        (row['high'] - row['close']) <= (0.3 * total_range) and
        row['low'] <= min(recent_lows)
    )

    if is_hammer:
        return "BULLISH"

    return None

def run_screener():
    print(f"\n{Fore.CYAN}--- Starting Scan Cycle ---{Style.RESET_ALL}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    
    symbols = get_futures_symbols()
    matches = []

    count = 0
    for symbol in symbols:
        if CHECK_LIMIT and count >= CHECK_LIMIT:
            break
            
        time.sleep(0.05) 
        
        found_signal = False
        signal_type = ""
        tf_found = ""

        for timeframe in TIMEFRAMES:
            tf_str = "1H" if timeframe == "Min60" else "4H"
            
            df = get_klines(symbol, timeframe)
            if df is None or len(df) < 12:
                continue
            
            last_closed_candle = df.iloc[-2]
            recent_highs = df['high'].iloc[-12:-2]
            recent_lows = df['low'].iloc[-12:-2]
            
            signal = analyze_candle(last_closed_candle, recent_highs, recent_lows)
            
            if signal:
                found_signal = True
                signal_type = signal
                tf_found = tf_str
                break 
        
        if found_signal:
            color = Fore.RED if signal_type == "BEARISH" else Fore.GREEN
            print(f"{color}[{signal_type}] {symbol} {Fore.WHITE}| TF: {tf_found}")
            # Store match data for Discord
            matches.append({
                "symbol": symbol,
                "type": signal_type,
                "tf": tf_found
            })
        
        count += 1
        print(f"\rScanning {count}/{min(len(symbols), CHECK_LIMIT)}...", end="")

    print(f"\n{Fore.CYAN}Cycle Complete. Found {len(matches)} matches.{Style.RESET_ALL}")
    
    # Send alerts if matches found
    if matches and WEBHOOK_URL != "YOUR_DISCORD_WEBHOOK_URL_HERE":
        send_discord_alert(matches)
    elif matches and WEBHOOK_URL == "YOUR_DISCORD_WEBHOOK_URL_HERE":
        print(f"{Fore.YELLOW}Matches found, but Webhook URL is not set.{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        print(f"{Fore.GREEN}CRT Scanner initialized. Running every 15 minutes...{Style.RESET_ALL}")
        while True:
            run_screener()
            print(f"{Fore.YELLOW}Sleeping for 15 minutes...{Style.RESET_ALL}")
            time.sleep(SCAN_INTERVAL)
    except KeyboardInterrupt:
        print("\nScanner stopped by user.")

import ccxt
import pandas as pd
import requests
import os
from datetime import datetime

# --- CONFIGURATION ---
# We will load these from GitHub Secrets for security
WEBHOOK_URL = os.environ.get('WEBHOOK_URL') 
TIMEFRAMES = ['1h', '4h']
TOP_N_PAIRS = 50
RATIO_THRESHOLD = 0.6

# --- SCANNER LOGIC ---
def check_pattern(df):
    if len(df) < 3: return None
    c_prev = df.iloc[-3]
    c_signal = df.iloc[-2]

    # BEARISH (Green -> Red)
    if c_prev['close'] > c_prev['open'] and c_signal['close'] < c_signal['open']:
        if c_signal['high'] > c_prev['high'] and c_signal['close'] < c_prev['high']:
            sweep_wick = c_signal['high'] - max(c_signal['open'], c_signal['close'])
            prev_body = abs(c_prev['close'] - c_prev['open'])
            prev_wick = c_prev['high'] - c_prev['close']
            if (prev_body < sweep_wick * RATIO_THRESHOLD) or (prev_wick < sweep_wick * RATIO_THRESHOLD):
                return f"BEARISH 🔴 (Wick: {sweep_wick:.4f})"

    # BULLISH (Red -> Green)
    if c_prev['close'] < c_prev['open'] and c_signal['close'] > c_signal['open']:
        if c_signal['low'] < c_prev['low'] and c_signal['close'] > c_prev['low']:
            sweep_wick = min(c_signal['open'], c_signal['close']) - c_signal['low']
            prev_body = abs(c_prev['close'] - c_prev['open'])
            prev_wick = c_prev['close'] - c_prev['low']
            if (prev_body < sweep_wick * RATIO_THRESHOLD) or (prev_wick < sweep_wick * RATIO_THRESHOLD):
                return f"BULLISH 🟢 (Wick: {sweep_wick:.4f})"
    return None

def run_scan():
    print(f"🚀 Scanning Top {TOP_N_PAIRS} pairs...")
    exchange = ccxt.mexc({'options': {'defaultType': 'spot'}})
    
    try:
        tickers = exchange.fetch_tickers()
        valid_pairs = []
        for symbol, data in tickers.items():
            if '/USDT' in symbol and '3L' not in symbol and '3S' not in symbol:
                valid_pairs.append({'symbol': symbol, 'volume': data.get('quoteVolume', 0)})
        
        # Sort by volume and take top N
        sorted_pairs = sorted(valid_pairs, key=lambda x: x['volume'], reverse=True)[:TOP_N_PAIRS]
        pairs = [x['symbol'] for x in sorted_pairs]
        
        alerts = []
        for symbol in pairs:
            for tf in TIMEFRAMES:
                try:
                    ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=5)
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    pattern = check_pattern(df)
                    if pattern:
                        price = df.iloc[-2]['close']
                        alerts.append(f"**{symbol}** [{tf}]\n{pattern}\nPrice: `{price}`")
                except:
                    continue
        
        if alerts and WEBHOOK_URL:
            msg_content = "🚨 **MARKET SCAN** 🚨\n" + "\n----------------\n".join(alerts)
            # Send to Discord Webhook
            requests.post(WEBHOOK_URL, json={'content': msg_content[:2000]})
            print(f"✅ Sent {len(alerts)} alerts to Discord.")
        else:
            print("✅ Scan complete. No patterns found.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_scan()
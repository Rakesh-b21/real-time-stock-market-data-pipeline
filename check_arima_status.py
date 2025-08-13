#!/usr/bin/env python3
"""
ARIMA Status Checker - Check current ARIMA model status and data availability
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ml.arima_forecasting import MultiSymbolARIMAForecaster
from shared.database import db_manager
import pandas as pd

def check_available_data():
    """Check what stock data is available in the database"""
    print("🔍 Checking available stock data...")
    
    try:
        conn = db_manager.get_connection()
        
        # Check recent stock data
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.ticker_symbol, COUNT(*) as data_points, 
                       MIN(spr.trade_datetime) as earliest, MAX(spr.trade_datetime) as latest
                FROM stock_prices_realtime spr
                JOIN companies c ON spr.company_id = c.company_id
                WHERE spr.trade_datetime >= NOW() - INTERVAL '7 days'
                GROUP BY c.ticker_symbol
                ORDER BY data_points DESC
            """)
            
            results = cur.fetchall()
            
            if results:
                print("\n📊 Available Stock Data (Last 7 days):")
                print("-" * 60)
                for row in results:
                    ticker, count, earliest, latest = row
                    print(f"📈 {ticker:8} | {count:4} points | {earliest} → {latest}")
                    
                return [row[0] for row in results if row[1] >= 50]  # Return symbols with enough data
            else:
                print("❌ No recent stock data found in database")
                return []
                
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def test_arima_training(symbols_with_data):
    """Test ARIMA training with available data"""
    print("\n🔮 Testing ARIMA Training...")
    
    if not symbols_with_data:
        print("❌ No symbols with sufficient data for ARIMA training")
        return
    
    # Initialize ARIMA forecaster
    arima_forecaster = MultiSymbolARIMAForecaster()
    
    try:
        conn = db_manager.get_connection()
        
        for symbol in symbols_with_data[:3]:  # Test first 3 symbols
            print(f"\n📈 Testing {symbol}...")
            
            # Fetch recent price data
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT spr.current_price, spr.trade_datetime 
                    FROM stock_prices_realtime spr
                    JOIN companies c ON spr.company_id = c.company_id
                    WHERE c.ticker_symbol = %s 
                    AND spr.trade_datetime >= NOW() - INTERVAL '7 days'
                    ORDER BY spr.trade_datetime ASC
                    LIMIT 100
                """, (symbol,))
                
                price_data = cur.fetchall()
                
                if len(price_data) >= 50:
                    print(f"   ✅ Found {len(price_data)} data points")
                    
                    # Add price data to ARIMA forecaster
                    for price, timestamp in price_data:
                        arima_forecaster.add_price(symbol, float(price), pd.Timestamp(timestamp))
                    
                    # Try to generate forecast (this will trigger training)
                    print(f"   🔄 Attempting to train ARIMA model...")
                    try:
                        forecast = arima_forecaster.forecast_symbol(symbol, steps=5)
                        if forecast and 'forecasts' in forecast:
                            print(f"   ✅ ARIMA training successful!")
                            print(f"   📊 Forecast: {forecast['forecasts'][:3]}...")
                        else:
                            print(f"   ❌ ARIMA training failed - no forecast generated")
                    except Exception as e:
                        print(f"   ❌ ARIMA training failed: {e}")
                else:
                    print(f"   ❌ Insufficient data: {len(price_data)} points (need 50+)")
                    
    except Exception as e:
        print(f"❌ Error testing ARIMA: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def check_arima_models_status():
    """Check current ARIMA models status"""
    print("\n🔮 Checking ARIMA Models Status...")
    
    arima_forecaster = MultiSymbolARIMAForecaster()
    status = arima_forecaster.get_model_status()
    
    if status:
        print("\n📊 Current ARIMA Models:")
        print("-" * 50)
        for symbol, info in status.items():
            print(f"📈 {symbol:8} | Points: {info.get('data_points', 0):3} | "
                  f"Model: {'✅' if info.get('has_model', False) else '❌'}")
    else:
        print("❌ No ARIMA models currently active")

def main():
    """Main function to check ARIMA status"""
    print("🚀 ARIMA Status Checker")
    print("=" * 50)
    
    # Check available data
    symbols_with_data = check_available_data()
    
    # Check current ARIMA status
    check_arima_models_status()
    
    # Test ARIMA training if data is available
    if symbols_with_data:
        test_arima_training(symbols_with_data)
    else:
        print("\n💡 To get ARIMA working:")
        print("   1. Start the producer: python producer/producer.py")
        print("   2. Start analytics consumer: python analytics/analytics_consumer.py")
        print("   3. Wait for 50+ data points per symbol")
        print("   4. ARIMA models will train automatically")

if __name__ == "__main__":
    main()

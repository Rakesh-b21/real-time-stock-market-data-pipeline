import dash
from dash import dcc, html, Input, Output, callback_context
import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import os
from datetime import datetime, timedelta, date
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Dash app
app = dash.Dash(__name__, title="Stock Market Analytics Dashboard")
app.config.suppress_callback_exceptions = True

from shared.database import db_manager
from ml.arima_forecasting import MultiSymbolARIMAForecaster

# Initialize ARIMA forecaster
arima_forecaster = MultiSymbolARIMAForecaster()

def get_db_connection():
    """Get database connection using centralized manager"""
    try:
        return db_manager.get_connection()
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

# Helper to get max timestamp from realtime table
def get_latest_timestamp_realtime():
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute("SELECT MAX(trade_datetime) FROM stock_prices_realtime")
        result = cur.fetchone()
        conn.close()
        return result[0]
    except Exception as e:
        logger.error(f"Error fetching latest timestamp: {e}")
        return None

# Helper to get max timestamp from analytics table
def get_latest_timestamp_analytics():
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute("SELECT MAX(timestamp) FROM stock_analytics")
        result = cur.fetchone()
        return result[0]
    except Exception as e:
        logger.error(f"Error fetching latest analytics timestamp: {e}")
        return None

def fetch_stock_data(ticker_symbol=None, limit=100, time_window='now'):
    """Fetch stock price data from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()
        
        if time_window == 'max':
            latest_ts = get_latest_timestamp_realtime()
            if not latest_ts:
                return pd.DataFrame()
            query = """
            SELECT c.ticker_symbol, spr.current_price, spr.open_price, spr.high_price, 
                   spr.low_price, spr.volume, spr.trade_datetime as timestamp
            FROM stock_prices_realtime spr
            JOIN companies c ON spr.company_id = c.company_id
            WHERE spr.trade_datetime >= %s - INTERVAL '1 hour'
            """
            params = [latest_ts]
        else:
            query = """
            SELECT c.ticker_symbol, spr.current_price, spr.open_price, spr.high_price, 
                   spr.low_price, spr.volume, spr.trade_datetime as timestamp
            FROM stock_prices_realtime spr
            JOIN companies c ON spr.company_id = c.company_id
            WHERE spr.trade_datetime >= NOW() - INTERVAL '1 hour'
            """
            params = []
        
        if ticker_symbol:
            query += " AND c.ticker_symbol = %s"
            params.append(ticker_symbol)
        
        query += " ORDER BY spr.trade_datetime DESC LIMIT %s"
        params.append(limit)
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error fetching stock data: {e}")
        return pd.DataFrame()

def fetch_analytics_data(ticker_symbol=None, limit=100, time_window='now'):
    """Fetch analytics data from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()
        
        if time_window == 'max':
            latest_ts = get_latest_timestamp_analytics()
            if not latest_ts:
                return pd.DataFrame()
            query = """
            SELECT c.ticker_symbol, sa.timestamp, sa.current_price, sa.open_price, sa.high_price, 
                   sa.low_price, sa.volume, sa.rsi_14, sa.sma_20, sa.sma_50, sa.ema_12, sa.ema_26,
                   sa.bb_upper, sa.bb_middle, sa.bb_lower,
                   sa.macd, sa.macd_signal, sa.macd_histogram, sa.volatility,
                   sa.price_change_percent, sa.volume_change_percent
            FROM stock_analytics sa
            JOIN companies c ON sa.company_id = c.company_id
            WHERE sa.timestamp >= %s - INTERVAL '1 hour'
            """
            params = [latest_ts]
        else:
            query = """
            SELECT c.ticker_symbol, sa.timestamp, sa.current_price, sa.open_price, sa.high_price, 
                   sa.low_price, sa.volume, sa.rsi_14, sa.sma_20, sa.sma_50, sa.ema_12, sa.ema_26,
                   sa.bb_upper, sa.bb_middle, sa.bb_lower,
                   sa.macd, sa.macd_signal, sa.macd_histogram, sa.volatility,
                   sa.price_change_percent, sa.volume_change_percent
            FROM stock_analytics sa
            JOIN companies c ON sa.company_id = c.company_id
            WHERE sa.timestamp >= NOW() - INTERVAL '1 hour'
            """
            params = []
        
        if ticker_symbol:
            query += " AND c.ticker_symbol = %s"
            params.append(ticker_symbol)
        
        query += " ORDER BY sa.timestamp DESC LIMIT %s"
        params.append(limit)
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error fetching analytics data: {e}")
        return pd.DataFrame()

def fetch_alerts(limit=50):
    """Fetch recent alerts"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        query = """
        SELECT c.ticker_symbol, aa.alert_type, aa.indicator_value, aa.threshold_value, 
               aa.alert_message, aa.severity, aa.created_at
        FROM analytics_alerts aa
        JOIN companies c ON aa.company_id = c.company_id
        ORDER BY aa.created_at DESC
        LIMIT %s
        """
        df = pd.read_sql_query(query, conn, params=[limit])
        conn.close()
        return df.to_dict('records')
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return []

def fetch_predictions(ticker_symbol=None, limit=100, time_window='now'):
    """Fetch prediction data from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()
        
        if time_window == 'max':
            latest_ts = get_latest_timestamp_analytics()
            if not latest_ts:
                return pd.DataFrame()
            query = """
            SELECT c.ticker_symbol, p.predicted_date, p.predicted_price, p.confidence_score,
                   p.prediction_type, p.created_at
            FROM predictions p
            JOIN companies c ON p.company_id = c.company_id
            WHERE p.created_at >= %s - INTERVAL '1 hour'
            """
            params = [latest_ts]
        else:
            query = """
            SELECT c.ticker_symbol, p.predicted_date, p.predicted_price, p.confidence_score,
                   p.prediction_type, p.created_at
            FROM predictions p
            JOIN companies c ON p.company_id = c.company_id
            WHERE p.created_at >= NOW() - INTERVAL '1 hour'
            """
            params = []
        
        if ticker_symbol:
            query += " AND c.ticker_symbol = %s"
            params.append(ticker_symbol)
        
        query += " ORDER BY p.created_at DESC LIMIT %s"
        params.append(limit)
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error fetching predictions: {e}")
        return pd.DataFrame()

def fetch_arima_forecasts(ticker_symbol=None):
    """Fetch ARIMA forecasts from the forecaster"""
    try:
        if ticker_symbol and ticker_symbol != 'ALL':
            # Get forecast for specific symbol
            forecast_data = arima_forecaster.forecast_symbol(ticker_symbol, steps=5, confidence_level=0.95)
            if forecast_data:
                return {ticker_symbol: forecast_data}
            else:
                logger.info(f"No ARIMA forecast available for {ticker_symbol} - may need more data or model training")
                return {}
        else:
            # Get forecasts for all symbols
            forecasts = arima_forecaster.forecast_all_symbols(steps=5, confidence_level=0.95)
            # Filter out None/error results
            return {k: v for k, v in forecasts.items() if v and not isinstance(v, dict) or 'error' not in v}
        return {}
    except Exception as e:
        logger.error(f"Error fetching ARIMA forecasts: {e}")
        return {}

def get_arima_model_status():
    """Get status of all ARIMA models"""
    try:
        return arima_forecaster.get_model_status()
    except Exception as e:
        logger.error(f"Error getting ARIMA model status: {e}")
        return {}

def get_available_tickers():
    """Get list of available ticker symbols"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        query = "SELECT DISTINCT ticker_symbol FROM companies ORDER BY ticker_symbol"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df['ticker_symbol'].tolist()
    except Exception as e:
        logger.error(f"Error fetching tickers: {e}")
        return []

def create_price_chart(df, pred_df=None, arima_forecasts=None):
    """Create enhanced candlestick chart with volume, predictions, and ARIMA forecasts"""
    if df.empty:
        return go.Figure().add_annotation(
            text=" No data available - Start the pipeline to see real-time data",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
    
    # Create subplots with better spacing
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(' Stock Price with ARIMA Forecasts', ' Trading Volume'),
        row_heights=[0.7, 0.3]
    )
    
    # Group by ticker for multiple symbols
    for ticker in df['ticker_symbol'].unique():
        ticker_data = df[df['ticker_symbol'] == ticker].sort_values('timestamp')
        
        # Candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=ticker_data['timestamp'],
                open=ticker_data['open_price'],
                high=ticker_data['high_price'],
                low=ticker_data['low_price'],
                close=ticker_data['current_price'],
                name=f'{ticker} Price',
                increasing_line_color='#00cc96',
                decreasing_line_color='#ef553b'
            ), row=1, col=1
        )
        
        # Volume chart
        fig.add_trace(
            go.Bar(
                x=ticker_data['timestamp'],
                y=ticker_data['volume'],
                name=f'{ticker} Volume',
                marker_color='lightblue',
                opacity=0.7
            ), row=2, col=1
        )
        
        # Add ML predictions if available
        if pred_df is not None and not pred_df.empty:
            pred_ticker_data = pred_df[pred_df['ticker_symbol'] == ticker]
            if not pred_ticker_data.empty:
                fig.add_trace(
                    go.Scatter(
                        x=pred_ticker_data['timestamp'],
                        y=pred_ticker_data['predicted_price'],
                        mode='markers+lines',
                        name=f'{ticker} ML Predictions',
                        marker=dict(color='orange', size=8, symbol='diamond'),
                        line=dict(dash='dot', color='orange')
                    ), row=1, col=1
                )
        
        # Add ARIMA forecasts if available
        if arima_forecasts and ticker in arima_forecasts:
            forecast_data = arima_forecasts[ticker]
            if forecast_data and 'forecast' in forecast_data:
                # Get last actual price point for connection
                last_timestamp = ticker_data['timestamp'].iloc[-1]
                last_price = ticker_data['current_price'].iloc[-1]
                
                # Create forecast timestamps (assuming 1-hour intervals)
                import pandas as pd
                forecast_timestamps = pd.date_range(
                    start=last_timestamp + pd.Timedelta(hours=1),
                    periods=len(forecast_data['forecast']),
                    freq='H'
                )
                
                # Add forecast line
                forecast_x = [last_timestamp] + list(forecast_timestamps)
                forecast_y = [last_price] + list(forecast_data['forecast'])
                
                fig.add_trace(
                    go.Scatter(
                        x=forecast_x,
                        y=forecast_y,
                        mode='lines+markers',
                        name=f'{ticker} ARIMA Forecast',
                        line=dict(color='purple', width=3, dash='dash'),
                        marker=dict(color='purple', size=6)
                    ), row=1, col=1
                )
    
    # Update layout with modern styling
    fig.update_layout(
        title=dict(
            text=" Real-time Stock Analysis with ARIMA Forecasting",
            font=dict(size=20, color='#2c3e50')
        ),
        height=700,
        showlegend=True,
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family="Arial, sans-serif")
    )
    
    return fig

def create_technical_indicators_chart(df):
    """Create technical indicators chart"""
    if df.empty:
        return go.Figure()
    
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        subplot_titles=('RSI', 'Moving Averages', 'Bollinger Bands'),
        vertical_spacing=0.05
    )
    
    # RSI
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['rsi_14'],
            name='RSI',
            line=dict(color='purple')
        ),
        row=1, col=1
    )
    
    # Add RSI overbought/oversold lines
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=1, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=1, col=1)
    
    # Moving Averages
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['sma_20'],
            name='SMA 20',
            line=dict(color='blue')
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['sma_50'],
            name='SMA 50',
            line=dict(color='orange')
        ),
        row=2, col=1
    )
    
    # Bollinger Bands
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['bb_upper'],
            name='Upper Band',
            line=dict(color='gray', dash='dash')
        ),
        row=3, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['bb_lower'],
            name='Lower Band',
            line=dict(color='gray', dash='dash'),
            fill='tonexty'
        ),
        row=3, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['bb_middle'],
            name='Middle Band',
            line=dict(color='black')
        ),
        row=3, col=1
    )
    
    fig.update_layout(height=800, title='Technical Indicators')
    return fig

def create_volatility_chart(df):
    """Create volatility chart"""
    if df.empty:
        return go.Figure()
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['volatility'],
            name='Volatility',
            line=dict(color='red'),
            fill='tozeroy'
        )
    )
    
    fig.update_layout(
        title='Historical Volatility (20-period)',
        xaxis_title='Time',
        yaxis_title='Volatility',
        height=400
    )
    
    return fig

# Modern responsive app layout
app.layout = html.Div([
    # Meta tags for responsive design
    html.Meta(name="viewport", content="width=device-width, initial-scale=1"),
    
    # Header
    html.Div([
        html.H1(" Real-time Stock Market Analytics Dashboard", className="dashboard-title"),
        html.P("Advanced analytics with ARIMA forecasting and technical indicators", className="dashboard-subtitle")
    ], className="header-section"),
    
    # Control Panel
    html.Div([
        html.Div([
            html.Label(" Symbol", className="control-label"),
            dcc.Dropdown(
                id='symbol-dropdown',
                options=[
                    {'label': 'All Symbols', 'value': 'ALL'}
                ] + [
                    {'label': ticker, 'value': ticker} 
                    for ticker in get_available_tickers()
                ],
                value='ALL',
                className="control-dropdown"
            )
        ], className="control-group"),
        
        html.Div([
            html.Label("Time Window", className="control-label"),
            dcc.Dropdown(
                id='time-window-dropdown',
                options=[
                    {'label': 'Latest 1 hour (from now)', 'value': 'now'},
                    {'label': 'Latest 1 hour available in DB', 'value': 'max'}
                ],
                value='now',
                className="control-dropdown"
            )
        ], className="control-group"),
        
        html.Div([
            html.Label("Update Interval (seconds)", className="control-label"),
            dcc.Slider(
                id='interval-slider',
                min=5,
                max=60,
                step=5,
                value=10,
                marks={i: str(i) for i in range(5, 61, 10)},
                className="control-slider"
            )
        ], className="control-group"),
        
        html.Div([
            html.Button('Refresh Now', id='refresh-button', n_clicks=0, className="refresh-button")
        ], className="control-group")
    ], className="control-panel"),
    
    # Main Dashboard Grid
    html.Div([
        # Main Charts Section
        html.Div([
            dcc.Graph(id='price-chart', className="main-chart"),
            html.Div([
                html.Div([
                    dcc.Graph(id='technical-indicators-chart', className="secondary-chart")
                ], className="chart-half"),
                html.Div([
                    dcc.Graph(id='volatility-chart', className="secondary-chart")
                ], className="chart-half")
            ], className="charts-row")
        ], className="charts-section"),
        
        # Sidebar with Analytics
        html.Div([
            # ARIMA Model Status
            html.Div([
                html.H3("🔮 ARIMA Models", className="sidebar-title"),
                html.Div(id='arima-status', className="arima-status")
            ], className="sidebar-card"),
            
            # ARIMA Forecast Summary
            html.Div([
                html.H3("📈 Forecast Summary", className="sidebar-title"),
                html.Div(id='forecast-summary', className="forecast-summary")
            ], className="sidebar-card"),
            
            # Recent Alerts
            html.Div([
                html.H3("🚨 Recent Alerts", className="sidebar-title"),
                html.Div(id='alerts-table', className="alerts-container")
            ], className="sidebar-card"),
            
            # Live Statistics
            html.Div([
                html.H3("📊 Live Statistics", className="sidebar-title"),
                html.Div(id='summary-stats', className="stats-container")
            ], className="sidebar-card")
        ], className="sidebar")
    ], className="dashboard-grid"),
    
    # Hidden interval component for auto-refresh
    dcc.Interval(
        id='interval-component',
        interval=10*1000,  # in milliseconds
        n_intervals=0
    )
])

@app.callback(
    [Output('price-chart', 'figure'),
     Output('technical-indicators-chart', 'figure'),
     Output('volatility-chart', 'figure'),
     Output('alerts-table', 'children'),
     Output('summary-stats', 'children'),
     Output('arima-status', 'children'),
     Output('forecast-summary', 'children')],
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks'),
     Input('symbol-dropdown', 'value'),
     Input('interval-slider', 'value'),
     Input('time-window-dropdown', 'value')]
)
def update_dashboard(n_intervals, n_clicks, ticker_symbol, interval, time_window):
    """Enhanced dashboard update with ARIMA forecasting and modern analytics"""
    
    # Update interval based on slider
    if interval:
        ctx = callback_context
        if ctx.triggered:
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if trigger_id == 'interval-slider':
                return dash.no_update
    
    # Fetch data
    symbol_filter = None if ticker_symbol == 'ALL' else ticker_symbol
    stock_df = fetch_stock_data(symbol_filter, limit=1000, time_window=time_window)
    analytics_df = fetch_analytics_data(symbol_filter, limit=1000, time_window=time_window)
    pred_df = fetch_predictions(symbol_filter, limit=100, time_window=time_window)
    alerts = fetch_alerts(limit=20)
    
    # Fetch ARIMA forecasts and model status
    arima_forecasts = fetch_arima_forecasts(ticker_symbol)
    arima_status = get_arima_model_status()
    
    # Create enhanced charts with ARIMA integration
    price_fig = create_price_chart(stock_df, pred_df, arima_forecasts)
    tech_fig = create_technical_indicators_chart(analytics_df)
    vol_fig = create_volatility_chart(analytics_df)
    
    # Create modern alerts display
    alerts_table = []
    if alerts:
        for i, alert in enumerate(alerts[:10]):  # Show top 10 alerts
            severity_color = {
                'HIGH': '#e74c3c',
                'MEDIUM': '#f39c12', 
                'LOW': '#3498db'
            }.get(alert['severity'], '#95a5a6')
            
            alerts_table.append(
                html.Div([
                    html.Div([
                        html.Span(f"🚨 {alert['ticker_symbol']}", className="alert-symbol"),
                        html.Span(alert['severity'], className="alert-severity", 
                                style={'backgroundColor': severity_color})
                    ], className="alert-header"),
                    html.Div([
                        html.Strong(f"{alert['alert_type']}"),
                        html.Br(),
                        html.Span(f"Value: {alert['indicator_value']:.2f} | Threshold: {alert['threshold_value']:.2f}"),
                        html.Br(),
                        html.Small(alert['alert_message']),
                        html.Br(),
                        html.Small(f"⏰ {alert['created_at']}", className="alert-time")
                    ], className="alert-body")
                ], className="alert-item")
            )
    else:
        alerts_table.append(
            html.Div([
                html.P("✅ No recent alerts", className="no-alerts")
            ])
        )
    
    # Create enhanced summary stats
    summary_stats = []
    if not analytics_df.empty:
        latest = analytics_df.iloc[0]
        
        # Calculate additional metrics
        price_change = latest.get('price_change_percent', 0)
        price_color = '#00cc96' if price_change >= 0 else '#ef553b'
        
        summary_stats.extend([
            html.Div([
                html.Div([
                    html.H4(f"📊 {latest['ticker_symbol']}", className="stats-symbol"),
                    html.Div([
                        html.Span(f"${latest['current_price']:.2f}", className="current-price"),
                        html.Span(f"{price_change:+.2f}%", 
                                className="price-change", 
                                style={'color': price_color})
                    ], className="price-display")
                ], className="stats-header"),
                
                html.Div([
                    html.Div([
                        html.Span("RSI", className="metric-label"),
                        html.Span(f"{latest['rsi_14']:.1f}" if pd.notna(latest['rsi_14']) else "N/A", 
                                className="metric-value")
                    ], className="metric-row"),
                    
                    html.Div([
                        html.Span("Volatility", className="metric-label"),
                        html.Span(f"{latest['volatility']:.3f}" if pd.notna(latest['volatility']) else "N/A", 
                                className="metric-value")
                    ], className="metric-row"),
                    
                    html.Div([
                        html.Span("Volume", className="metric-label"),
                        html.Span(f"{latest.get('volume', 0):,.0f}", className="metric-value")
                    ], className="metric-row")
                ], className="metrics-grid")
            ])
        ])
    else:
        summary_stats.append(
            html.Div([
                html.P("📊 No analytics data available", className="no-data")
            ])
        )
    
    # Create ARIMA model status display
    arima_status_display = []
    if arima_status:
        for symbol, status in arima_status.items():
            model_color = '#00cc96' if status.get('is_fitted', False) else '#ef553b'
            arima_status_display.append(
                html.Div([
                    html.Div([
                        html.Span(f"📈 {symbol}", className="model-symbol"),
                        html.Span("●", style={'color': model_color, 'fontSize': '20px'})
                    ], className="model-header"),
                    html.Div([
                        html.Small(f"Order: {status.get('order', 'N/A')}", className="model-detail"),
                        html.Small(f"AIC: {status.get('aic', 'N/A'):.2f}" if status.get('aic') else "AIC: N/A", 
                                 className="model-detail"),
                        html.Small(f"Last Updated: {status.get('last_updated', 'Never')}", className="model-detail")
                    ], className="model-details")
                ], className="model-status-item")
            )
    else:
        arima_status_display.append(
            html.Div([
                html.P("🔮 No ARIMA models available", className="no-models")
            ])
        )
    
    # Create ARIMA forecast summary
    forecast_summary = []
    if arima_forecasts:
        for symbol, forecast_data in arima_forecasts.items():
            if forecast_data and 'forecast' in forecast_data:
                forecasts = forecast_data['forecast']
                confidence_intervals = forecast_data.get('confidence_intervals', [])
                
                # Calculate forecast trend
                trend = "📈" if len(forecasts) > 1 and forecasts[-1] > forecasts[0] else "📉"
                avg_forecast = sum(forecasts) / len(forecasts)
                
                forecast_summary.append(
                    html.Div([
                        html.Div([
                            html.Span(f"{trend} {symbol}", className="forecast-symbol"),
                            html.Span(f"${avg_forecast:.2f}", className="forecast-avg")
                        ], className="forecast-header"),
                        html.Div([
                            html.Small(f"Next 5 periods: ${forecasts[0]:.2f} → ${forecasts[-1]:.2f}", 
                                     className="forecast-range"),
                            html.Small(f"Confidence: ±{confidence_intervals[0][1] - forecasts[0]:.2f}" 
                                     if confidence_intervals else "Confidence: N/A", 
                                     className="forecast-confidence")
                        ], className="forecast-details")
                    ], className="forecast-item")
                )
    else:
        forecast_summary.append(
            html.Div([
                html.P("📈 No forecasts available", className="no-forecasts")
            ])
        )
    
    return price_fig, tech_fig, vol_fig, alerts_table, summary_stats, arima_status_display, forecast_summary

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)
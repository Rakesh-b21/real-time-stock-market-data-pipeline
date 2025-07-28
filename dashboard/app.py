import dash
from dash import dcc, html, Input, Output, callback_context
import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import psycopg2
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

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'database': os.getenv('POSTGRES_DB', 'stocks'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}

def get_db_connection():
    """Get database connection"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

# Helper to get max timestamp
def get_latest_timestamp(table):
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute(f"SELECT MAX(timestamp) FROM {table}")
        result = cur.fetchone()
        conn.close()
        return result[0]
    except Exception as e:
        logger.error(f"Error fetching latest timestamp: {e}")
        return None

def fetch_stock_data(symbol=None, limit=100, time_window='now'):
    """Fetch stock price data from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()
        if time_window == 'max':
            latest_ts = get_latest_timestamp('stock_prices')
            if not latest_ts:
                return pd.DataFrame()
            query = """
            SELECT symbol, current_price, open_price, high_price, low_price, volume, timestamp
            FROM stock_prices
            WHERE timestamp >= %s - INTERVAL '1 hour'
            """
            params = [latest_ts]
        else:
            query = """
            SELECT symbol, current_price, open_price, high_price, low_price, volume, timestamp
            FROM stock_prices
            WHERE timestamp >= NOW() - INTERVAL '1 hour'
            """
            params = []
        if symbol:
            query += " AND symbol = %s"
            params.append(symbol)
        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error fetching stock data: {e}")
        return pd.DataFrame()

def fetch_analytics_data(symbol=None, limit=100, time_window='now'):
    """Fetch analytics data from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()
        if time_window == 'max':
            latest_ts = get_latest_timestamp('stock_analytics')
            if not latest_ts:
                return pd.DataFrame()
            query = """
            SELECT symbol, timestamp, current_price, rsi_14, sma_20, sma_50, 
                   bollinger_upper, bollinger_lower, bollinger_middle,
                   macd_line, macd_signal, macd_histogram, volatility_20
            FROM stock_analytics
            WHERE timestamp >= %s - INTERVAL '1 hour'
            """
            params = [latest_ts]
        else:
            query = """
            SELECT symbol, timestamp, current_price, rsi_14, sma_20, sma_50, 
                   bollinger_upper, bollinger_lower, bollinger_middle,
                   macd_line, macd_signal, macd_histogram, volatility_20
            FROM stock_analytics
            WHERE timestamp >= NOW() - INTERVAL '1 hour'
            """
            params = []
        if symbol:
            query += " AND symbol = %s"
            params.append(symbol)
        query += " ORDER BY timestamp DESC LIMIT %s"
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
            return pd.DataFrame()
        
        query = """
        SELECT symbol, alert_type, alert_value, threshold_value, message, triggered_at
        FROM analytics_alerts
        WHERE triggered_at >= NOW() - INTERVAL '24 hours'
        ORDER BY triggered_at DESC LIMIT %s
        """
        
        df = pd.read_sql_query(query, conn, params=[limit])
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return pd.DataFrame()

def fetch_predictions(symbol=None, limit=100, time_window='now'):
    try:
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()
        if time_window == 'max':
            latest_ts = get_latest_timestamp('predictions')
            if not latest_ts:
                return pd.DataFrame()
            query = """
            SELECT symbol, timestamp, predicted_price
            FROM predictions
            WHERE timestamp >= %s - INTERVAL '1 hour'
            """
            params = [latest_ts]
        else:
            query = """
            SELECT symbol, timestamp, predicted_price
            FROM predictions
            WHERE timestamp >= NOW() - INTERVAL '1 hour'
            """
            params = []
        if symbol:
            query += " AND symbol = %s"
            params.append(symbol)
        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error fetching predictions: {e}")
        return pd.DataFrame()

def create_price_chart(df, pred_df=None):
    """Create candlestick chart with volume and overlay predictions if available"""
    if df.empty:
        return go.Figure()
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=('Stock Price', 'Volume'),
        row_width=[0.7, 0.3]
    )
    fig.add_trace(
        go.Candlestick(
            x=df['timestamp'],
            open=df['open_price'],
            high=df['high_price'],
            low=df['low_price'],
            close=df['current_price'],
            name='Price'
        ),
        row=1, col=1
    )
    if pred_df is not None and not pred_df.empty:
        fig.add_trace(
            go.Scatter(
                x=pred_df['timestamp'],
                y=pred_df['predicted_price'],
                mode='lines+markers',
                name='Predicted Price',
                line=dict(color='red', dash='dot')
            ),
            row=1, col=1
        )
    fig.add_trace(
        go.Bar(
            x=df['timestamp'],
            y=df['volume'],
            name='Volume',
            marker_color='lightblue'
        ),
        row=2, col=1
    )
    fig.update_layout(
        title='Real-time Stock Price Chart',
        xaxis_rangeslider_visible=False,
        height=600
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
            y=df['bollinger_upper'],
            name='Upper Band',
            line=dict(color='gray', dash='dash')
        ),
        row=3, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['bollinger_lower'],
            name='Lower Band',
            line=dict(color='gray', dash='dash'),
            fill='tonexty'
        ),
        row=3, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['bollinger_middle'],
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
            y=df['volatility_20'],
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

# App layout
app.layout = html.Div([
    html.H1("📈 Real-time Stock Market Analytics Dashboard", 
             style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': 30}),
    
    # Controls
    html.Div([
        html.Div([
            html.Label("Symbol:"),
            dcc.Dropdown(
                id='symbol-dropdown',
                options=[
                    {'label': 'All Symbols', 'value': 'ALL'},
                    {'label': 'AAPL', 'value': 'AAPL'},
                    {'label': 'MSFT', 'value': 'MSFT'},
                    {'label': 'GOOGL', 'value': 'GOOGL'},
                    {'label': 'AMZN', 'value': 'AMZN'},
                    {'label': 'TSLA', 'value': 'TSLA'}
                ],
                value='ALL',
                style={'width': '200px'}
            )
        ], style={'display': 'inline-block', 'marginRight': 20}),
        
        html.Div([
            html.Label("Time Window:"),
            dcc.Dropdown(
                id='time-window-dropdown',
                options=[
                    {'label': 'Latest 1 hour (from now)', 'value': 'now'},
                    {'label': 'Latest 1 hour available in DB', 'value': 'max'}
                ],
                value='now',
                style={'width': '300px'}
            )
        ], style={'display': 'inline-block', 'marginRight': 20}),
        
        html.Div([
            html.Label("Update Interval (seconds):"),
            dcc.Slider(
                id='interval-slider',
                min=5,
                max=60,
                step=5,
                value=10,
                marks={i: str(i) for i in range(5, 61, 10)}
            )
        ], style={'display': 'inline-block', 'marginRight': 20}),
        
        html.Div([
            html.Button('Refresh Now', id='refresh-button', n_clicks=0,
                       style={'backgroundColor': '#3498db', 'color': 'white', 'border': 'none', 'padding': '10px 20px'})
        ], style={'display': 'inline-block'})
    ], style={'textAlign': 'center', 'marginBottom': 30}),
    
    # Main content
    html.Div([
        # Price Chart
        html.Div([
            html.H3("📊 Stock Price Chart"),
            dcc.Graph(id='price-chart', style={'height': '600px'})
        ], style={'width': '100%', 'marginBottom': 30}),
        
        # Technical Indicators
        html.Div([
            html.H3("📈 Technical Indicators"),
            dcc.Graph(id='technical-indicators-chart', style={'height': '800px'})
        ], style={'width': '100%', 'marginBottom': 30}),
        
        # Volatility and Alerts
        html.Div([
            html.Div([
                html.H3("📉 Volatility"),
                dcc.Graph(id='volatility-chart', style={'height': '400px'})
            ], style={'width': '50%', 'display': 'inline-block'}),
            
            html.Div([
                html.H3("🚨 Recent Alerts"),
                html.Div(id='alerts-table', style={'height': '400px', 'overflowY': 'scroll'})
            ], style={'width': '50%', 'display': 'inline-block', 'verticalAlign': 'top'})
        ], style={'width': '100%', 'marginBottom': 30}),
        
        # Summary Statistics
        html.Div([
            html.H3("📋 Summary Statistics"),
            html.Div(id='summary-stats')
        ], style={'width': '100%'})
    ]),
    
    # Hidden div for storing data
    html.Div(id='data-store', style={'display': 'none'}),
    
    # Interval component for auto-refresh
    dcc.Interval(
        id='interval-component',
        interval=10*1000,  # 10 seconds
        n_intervals=0
    )
])

# Callbacks
@app.callback(
    [Output('price-chart', 'figure'),
     Output('technical-indicators-chart', 'figure'),
     Output('volatility-chart', 'figure'),
     Output('alerts-table', 'children'),
     Output('summary-stats', 'children')],
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks'),
     Input('symbol-dropdown', 'value'),
     Input('interval-slider', 'value'),
     Input('time-window-dropdown', 'value')]
)
def update_dashboard(n_intervals, n_clicks, symbol, interval, time_window):
    """Update dashboard with latest data"""
    
    # Update interval
    if interval:
        app.layout['interval-component'].interval = interval * 1000
    
    # Fetch data
    symbol_filter = None if symbol == 'ALL' else symbol
    stock_df = fetch_stock_data(symbol_filter, 100, time_window)
    analytics_df = fetch_analytics_data(symbol_filter, 100, time_window)
    pred_df = fetch_predictions(symbol_filter, 100, time_window)
    alerts_df = fetch_alerts(50)
    
    # Create charts
    price_fig = create_price_chart(stock_df, pred_df)
    tech_fig = create_technical_indicators_chart(analytics_df)
    vol_fig = create_volatility_chart(analytics_df)
    
    # Create alerts table
    alerts_table = []
    if not alerts_df.empty:
        for _, alert in alerts_df.iterrows():
            alerts_table.append(
                html.Div([
                    html.Strong(f"{alert['symbol']} - {alert['alert_type']}"),
                    html.Br(),
                    html.Span(f"Value: {alert['alert_value']:.2f} | Threshold: {alert['threshold_value']:.2f}"),
                    html.Br(),
                    html.Small(f"Time: {alert['triggered_at']}"),
                    html.Hr()
                ], style={'marginBottom': 10})
            )
    else:
        alerts_table.append(html.P("No recent alerts"))
    
    # Create summary statistics
    summary_stats = []
    if not analytics_df.empty:
        latest = analytics_df.iloc[0]
        summary_stats = [
            html.Div([
                html.H4("Latest Analytics"),
                html.P(f"Symbol: {latest['symbol']}"),
                html.P(f"Price: ${latest['current_price']:.2f}"),
                html.P(f"RSI: {latest['rsi_14']:.2f}" if pd.notna(latest['rsi_14']) else "RSI: N/A"),
                html.P(f"Volatility: {latest['volatility_20']:.4f}" if pd.notna(latest['volatility_20']) else "Volatility: N/A"),
                html.P(f"Last Update: {latest['timestamp']}")
            ])
        ]
    else:
        summary_stats = [html.P("No data available")]
    
    return price_fig, tech_fig, vol_fig, alerts_table, summary_stats
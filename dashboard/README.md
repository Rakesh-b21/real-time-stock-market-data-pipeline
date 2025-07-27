# 📊 Stock Market Analytics Dashboard

A real-time, interactive dashboard built with Dash and Plotly for visualizing stock market data, technical indicators, and analytics.

## 🚀 Features

### **Real-time Data Visualization**
- **Candlestick Charts** with volume bars
- **Technical Indicators** (RSI, Moving Averages, Bollinger Bands)
- **Volatility Charts** with historical trends
- **Live Alerts** display for RSI and volatility warnings

### **Interactive Controls**
- **Symbol Filter** - View specific stocks or all symbols
- **Update Interval** - Adjust refresh rate (5-60 seconds)
- **Manual Refresh** - Force update with button click

### **Data Sources**
- **Stock Prices** - Real-time price data from your pipeline
- **Technical Analytics** - Calculated indicators from analytics consumer
- **Alerts** - System-generated alerts for overbought/oversold conditions

## 🛠️ Installation & Setup

### **Prerequisites**
- Your stock market pipeline must be running
- PostgreSQL database with analytics data
- Python dependencies installed

### **Install Dependencies**
```bash
pip install -r requirements.txt
```

### **Start the Dashboard**
```bash
# Option 1: Use the launcher script
python start_dashboard.py

# Option 2: Run directly
python -m dashboard.app
```

### **Access Dashboard**
Open your browser and navigate to: **http://localhost:8050**

## 📈 Dashboard Components

### **1. Stock Price Chart**
- **Candlestick chart** showing OHLC data
- **Volume bars** below price chart
- **Real-time updates** as new data arrives

### **2. Technical Indicators**
- **RSI (Relative Strength Index)** with overbought/oversold lines
- **Moving Averages** (SMA 20, SMA 50)
- **Bollinger Bands** with upper/lower bands and middle line

### **3. Volatility Chart**
- **Historical volatility** over time
- **20-period volatility** calculation
- **Trend analysis** for risk assessment

### **4. Alerts Panel**
- **Recent alerts** from the analytics system
- **RSI alerts** (overbought > 70, oversold < 30)
- **Volatility alerts** for unusual price movements

### **5. Summary Statistics**
- **Latest analytics** for selected symbol
- **Current price** and key indicators
- **Last update timestamp**

## 🎛️ Controls

### **Symbol Dropdown**
- **All Symbols** - View aggregated data
- **Individual Stocks** - Focus on specific ticker
- **Real-time filtering** of all charts

### **Update Interval Slider**
- **5-60 seconds** refresh rate
- **Automatic updates** without page reload
- **Performance optimization** for different use cases

### **Refresh Button**
- **Manual refresh** when needed
- **Force update** of all charts
- **Immediate data fetch** from database

## 🔧 Configuration

### **Environment Variables**
The dashboard uses the same environment variables as your pipeline:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=stocks
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

### **Database Queries**
The dashboard queries these tables:
- `stock_prices` - Raw price data
- `stock_analytics` - Technical indicators
- `analytics_alerts` - System alerts

## 🚨 Troubleshooting

### **Dashboard Not Loading**
1. Check if PostgreSQL is running
2. Verify database connection settings
3. Ensure analytics data exists in database

### **No Data Displayed**
1. Check if your pipeline is running
2. Verify data is being inserted into database
3. Check database connection in logs

### **Charts Not Updating**
1. Verify auto-refresh is enabled
2. Check browser console for errors
3. Ensure database queries are working

## 🔮 Future Enhancements

### **Planned Features**
- **ML Predictions** visualization
- **Portfolio tracking** capabilities
- **Export functionality** for reports
- **User authentication** system
- **Mobile responsive** design

### **Advanced Analytics**
- **Correlation analysis** between stocks
- **Sector performance** comparisons
- **Risk metrics** and VaR calculations
- **Trading signals** and recommendations

## 📊 Performance Tips

### **Optimization**
- **Reduce update frequency** for better performance
- **Filter by specific symbols** to reduce data load
- **Use appropriate time ranges** for queries

### **Scaling**
- **Database indexing** for faster queries
- **Connection pooling** for multiple users
- **Caching** for frequently accessed data

## 🎯 Usage Examples

### **Trading Analysis**
1. Select specific stock symbol
2. Monitor RSI for entry/exit signals
3. Watch Bollinger Bands for volatility
4. Check alerts for immediate notifications

### **Market Overview**
1. Select "All Symbols"
2. Monitor overall market trends
3. Compare technical indicators across stocks
4. Track volatility patterns

### **Research Mode**
1. Set longer update intervals
2. Focus on specific time periods
3. Analyze historical patterns
4. Export data for further analysis

---

**Happy Trading! 📈** 
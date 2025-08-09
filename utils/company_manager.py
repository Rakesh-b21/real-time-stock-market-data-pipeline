"""
Company Management Module
Handles company and industry data operations for the enhanced schema
"""

import os
import logging
import json
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import yfinance as yf
from typing import Dict, List, Optional, Tuple
import uuid
from shared.database import db_manager

load_dotenv()

logger = logging.getLogger(__name__)

class CompanyManager:
    """Manages company and industry data operations"""
    
    def __init__(self):
        # DB config is centralized in shared.database
        pass
    
    def get_db_connection(self):
        """Get database connection using centralized manager"""
        try:
            return db_manager.get_connection()
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def get_or_create_industry(self, industry_name: str, description: str = None) -> str:
        """Get existing industry or create new one"""
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Try to get existing industry
                cur.execute(
                    "SELECT industry_id FROM industries WHERE industry_name = %s",
                    (industry_name,)
                )
                result = cur.fetchone()
                
                if result:
                    return str(result['industry_id'])
                
                # Create new industry
                industry_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO industries (industry_id, industry_name, description) VALUES (%s, %s, %s)",
                    (industry_id, industry_name, description)
                )
                conn.commit()
                logger.info(f"Created new industry: {industry_name}")
                return industry_id
                
        except Exception as e:
            logger.error(f"Error in get_or_create_industry: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_or_create_company(self, ticker_symbol: str, company_name: str = None) -> str:
        """Get existing company or create new one with basic info"""
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Try to get existing company
                cur.execute(
                    "SELECT company_id FROM companies WHERE ticker_symbol = %s",
                    (ticker_symbol,)
                )
                result = cur.fetchone()
                
                if result:
                    return str(result['company_id'])
                
                # Get company info from Yahoo Finance
                company_info = self._get_company_info_from_yahoo(ticker_symbol)
                
                # Get or create industry
                industry_name = company_info.get('industry', 'Other')
                industry_id = self.get_or_create_industry(industry_name)
                
                # Convert company_info to JSON string for JSONB storage
                additional_details_json = json.dumps(company_info) if company_info else None
                
                # Create new company
                company_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO companies (
                        company_id, industry_id, ticker_symbol, company_name, legal_name,
                        exchange, sector, country, city, website_url, description,
                        employees_count, additional_details
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    company_id, industry_id, ticker_symbol,
                    company_name or company_info.get('longName', ticker_symbol),
                    company_info.get('longName'),
                    company_info.get('exchange'),
                    company_info.get('sector'),
                    company_info.get('country'),
                    company_info.get('city'),
                    company_info.get('website'),
                    company_info.get('longBusinessSummary'),
                    company_info.get('fullTimeEmployees'),
                    additional_details_json
                ))
                conn.commit()
                logger.info(f"Created new company: {ticker_symbol} - {company_name or company_info.get('longName', ticker_symbol)}")
                return company_id
                
        except Exception as e:
            logger.error(f"Error in get_or_create_company: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _get_company_info_from_yahoo(self, ticker_symbol: str) -> Dict:
        """Get company information from Yahoo Finance"""
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            
            # Extract relevant information
            return {
                'longName': info.get('longName'),
                'shortName': info.get('shortName'),
                'exchange': info.get('exchange'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'country': info.get('country'),
                'city': info.get('city'),
                'website': info.get('website'),
                'longBusinessSummary': info.get('longBusinessSummary'),
                'fullTimeEmployees': info.get('fullTimeEmployees'),
                'marketCap': info.get('marketCap'),
                'enterpriseValue': info.get('enterpriseValue'),
                'trailingPE': info.get('trailingPE'),
                'forwardPE': info.get('forwardPE'),
                'priceToBook': info.get('priceToBook'),
                'debtToEquity': info.get('debtToEquity'),
                'returnOnEquity': info.get('returnOnEquity'),
                'returnOnAssets': info.get('returnOnAssets'),
                'revenueGrowth': info.get('revenueGrowth'),
                'earningsGrowth': info.get('earningsGrowth')
            }
        except Exception as e:
            logger.warning(f"Could not fetch company info for {ticker_symbol}: {e}")
            return {}
    
    def get_company_by_ticker(self, ticker_symbol: str) -> Optional[Dict]:
        """Get company information by ticker symbol"""
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT c.*, i.industry_name 
                    FROM companies c 
                    JOIN industries i ON c.industry_id = i.industry_id 
                    WHERE c.ticker_symbol = %s
                """, (ticker_symbol,))
                result = cur.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error in get_company_by_ticker: {e}")
            raise
        finally:
            conn.close()
    
    def get_all_companies(self) -> List[Dict]:
        """Get all companies with their industry information"""
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT c.*, i.industry_name 
                    FROM companies c 
                    JOIN industries i ON c.industry_id = i.industry_id 
                    ORDER BY c.ticker_symbol
                """)
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error in get_all_companies: {e}")
            raise
        finally:
            conn.close()
    
    def get_companies_by_industry(self, industry_name: str) -> List[Dict]:
        """Get all companies in a specific industry"""
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT c.*, i.industry_name 
                    FROM companies c 
                    JOIN industries i ON c.industry_id = i.industry_id 
                    WHERE i.industry_name = %s
                    ORDER BY c.ticker_symbol
                """, (industry_name,))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error in get_companies_by_industry: {e}")
            raise
        finally:
            conn.close()
    
    def update_company_info(self, ticker_symbol: str, **kwargs) -> bool:
        """Update company information"""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cur:
                # Build dynamic update query
                set_clauses = []
                values = []
                
                for key, value in kwargs.items():
                    if hasattr(self, f'_validate_{key}'):
                        value = getattr(self, f'_validate_{key}')(value)
                    set_clauses.append(f"{key} = %s")
                    values.append(value)
                
                if not set_clauses:
                    return False
                
                values.append(ticker_symbol)
                query = f"UPDATE companies SET {', '.join(set_clauses)} WHERE ticker_symbol = %s"
                
                cur.execute(query, values)
                conn.commit()
                
                if cur.rowcount > 0:
                    logger.info(f"Updated company info for {ticker_symbol}")
                    return True
                else:
                    logger.warning(f"Company {ticker_symbol} not found for update")
                    return False
                    
        except Exception as e:
            logger.error(f"Error in update_company_info: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_industry_statistics(self) -> Dict:
        """Get statistics about companies by industry"""
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        i.industry_name,
                        COUNT(c.company_id) as company_count,
                        COUNT(DISTINCT c.sector) as sector_count
                    FROM industries i
                    LEFT JOIN companies c ON i.industry_id = c.industry_id
                    GROUP BY i.industry_id, i.industry_name
                    ORDER BY company_count DESC
                """)
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error in get_industry_statistics: {e}")
            raise
        finally:
            conn.close()
    
    def bulk_create_companies(self, ticker_list: List[str]) -> Dict[str, str]:
        """Bulk create companies for a list of tickers"""
        results = {}
        
        for ticker in ticker_list:
            try:
                company_id = self.get_or_create_company(ticker)
                results[ticker] = company_id
                logger.info(f"Successfully processed {ticker}")
            except Exception as e:
                logger.error(f"Failed to process {ticker}: {e}")
                results[ticker] = None
        
        return results
    
    def get_latest_price(self, ticker_symbol: str) -> Optional[Dict]:
        """Get the latest real-time price for a company"""
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT r.*, c.ticker_symbol, c.company_name
                    FROM stock_prices_realtime r
                    JOIN companies c ON r.company_id = c.company_id
                    WHERE c.ticker_symbol = %s
                """, (ticker_symbol,))
                result = cur.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error in get_latest_price: {e}")
            raise
        finally:
            conn.close()
    
    def get_price_history(self, ticker_symbol: str, days: int = 30) -> List[Dict]:
        """Get historical price data for a company"""
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT h.*, c.ticker_symbol, c.company_name
                    FROM stock_prices_historical h
                    JOIN companies c ON h.company_id = c.company_id
                    WHERE c.ticker_symbol = %s AND h.is_current = TRUE
                    ORDER BY h.trade_date DESC
                    LIMIT %s
                """, (ticker_symbol, days))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error in get_price_history: {e}")
            raise
        finally:
            conn.close()

# Global instance for easy access
company_manager = CompanyManager() 
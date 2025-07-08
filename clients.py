"""
Database clients for Neo4j and Oracle with async support.
"""
import asyncio
import time
from typing import List, Dict, Any, Optional, Union
import logging
from contextlib import asynccontextmanager

import neo4j
import oracledb
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Async Neo4j database client."""
    
    def __init__(self):
        self.driver: Optional[AsyncDriver] = None
        self.uri = settings.neo4j_uri
        self.username = settings.neo4j_username
        self.password = settings.neo4j_password
        self.database = settings.neo4j_database
        
    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60.0
            )
            # Verify connectivity
            await self.driver.verify_connectivity()
            logger.info("Connected to Neo4j successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close the Neo4j connection."""
        if self.driver:
            await self.driver.close()
            logger.info("Disconnected from Neo4j")
    
    @asynccontextmanager
    async def get_session(self):
        """Get an async session with proper cleanup."""
        if not self.driver:
            await self.connect()
        
        session = self.driver.session(database=self.database)
        try:
            yield session
        finally:
            await session.close()
    
    async def query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        if parameters is None:
            parameters = {}
        
        start_time = time.time()
        
        try:
            async with self.get_session() as session:
                result = await session.run(cypher, parameters)
                records = await result.data()
                execution_time = time.time() - start_time
                
                logger.info(f"Neo4j query executed in {execution_time:.3f}s, returned {len(records)} records")
                return records
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            logger.error(f"Query: {cypher}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    async def execute_write(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a write transaction."""
        if parameters is None:
            parameters = {}
        
        start_time = time.time()
        
        try:
            async with self.get_session() as session:
                result = await session.execute_write(
                    lambda tx: tx.run(cypher, parameters)
                )
                execution_time = time.time() - start_time
                
                logger.info(f"Neo4j write transaction executed in {execution_time:.3f}s")
                return {"success": True, "execution_time": execution_time}
        except Exception as e:
            logger.error(f"Neo4j write transaction failed: {e}")
            logger.error(f"Query: {cypher}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    async def health_check(self) -> bool:
        """Check if the Neo4j connection is healthy."""
        try:
            await self.query("RETURN 1 as test")
            return True
        except Exception:
            return False


class OracleClient:
    """Async Oracle database client."""
    
    def __init__(self):
        self.pool: Optional[oracledb.ConnectionPool] = None
        self.dsn = settings.oracle_dsn
        self.username = settings.oracle_username
        self.password = settings.oracle_password
        
    async def connect(self) -> None:
        """Establish connection pool to Oracle."""
        try:
            # Initialize Oracle client with thick client support if enabled
            if settings.oracle_use_thick_client:
                if settings.oracle_lib_dir:
                    oracledb.init_oracle_client(lib_dir=settings.oracle_lib_dir)
                    logger.info(f"Initialized Oracle thick client with lib_dir: {settings.oracle_lib_dir}")
                else:
                    oracledb.init_oracle_client()
                    logger.info("Initialized Oracle thick client with default lib_dir")
            else:
                # Use thin client (default)
                logger.info("Using Oracle thin client")
            
            # Configure connection parameters based on authentication method
            pool_params = {
                "dsn": self.dsn,
                "min": 5,
                "max": 20,
                "increment": 5,
                "threaded": True,
                "getmode": oracledb.POOL_GETMODE_WAIT
            }
            
            if settings.oracle_use_kerberos:
                # Use external authentication (Kerberos)
                # No username/password needed for Kerberos authentication
                logger.info("Using Oracle Kerberos authentication")
            else:
                # Use username/password authentication
                pool_params["user"] = self.username
                pool_params["password"] = self.password
                logger.info(f"Using Oracle username/password authentication for user: {self.username}")
            
            # Create connection pool
            self.pool = oracledb.create_pool(**pool_params)
            
            logger.info("Connected to Oracle successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Oracle: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close the Oracle connection pool."""
        if self.pool:
            self.pool.close()
            logger.info("Disconnected from Oracle")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool with proper cleanup."""
        if not self.pool:
            await self.connect()
        
        connection = None
        try:
            # Get connection from pool (this might block, so we run it in executor)
            connection = await asyncio.get_event_loop().run_in_executor(
                None, self.pool.acquire
            )
            yield connection
        finally:
            if connection:
                await asyncio.get_event_loop().run_in_executor(
                    None, connection.close
                )
    
    async def query(self, sql: str, parameters: Optional[Dict[str, Any]] = None, fetch_size: int = 100) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results."""
        if parameters is None:
            parameters = {}
        
        start_time = time.time()
        
        try:
            async with self.get_connection() as connection:
                cursor = connection.cursor()
                cursor.arraysize = fetch_size
                
                # Execute query in executor to avoid blocking
                await asyncio.get_event_loop().run_in_executor(
                    None, cursor.execute, sql, parameters
                )
                
                # Fetch results
                rows = await asyncio.get_event_loop().run_in_executor(
                    None, cursor.fetchall
                )
                
                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # Convert to list of dictionaries
                results = [dict(zip(columns, row)) for row in rows]
                
                execution_time = time.time() - start_time
                
                logger.info(f"Oracle query executed in {execution_time:.3f}s, returned {len(results)} records")
                return results
        except Exception as e:
            logger.error(f"Oracle query failed: {e}")
            logger.error(f"Query: {sql}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    async def execute_ddl(self, sql: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute DDL/DML statements."""
        if parameters is None:
            parameters = {}
        
        start_time = time.time()
        
        try:
            async with self.get_connection() as connection:
                cursor = connection.cursor()
                
                # Execute statement in executor
                await asyncio.get_event_loop().run_in_executor(
                    None, cursor.execute, sql, parameters
                )
                
                # Commit the transaction
                await asyncio.get_event_loop().run_in_executor(
                    None, connection.commit
                )
                
                execution_time = time.time() - start_time
                
                logger.info(f"Oracle DDL/DML executed in {execution_time:.3f}s")
                return {"success": True, "execution_time": execution_time}
        except Exception as e:
            logger.error(f"Oracle DDL/DML failed: {e}")
            logger.error(f"Query: {sql}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    async def health_check(self) -> bool:
        """Check if the Oracle connection is healthy."""
        try:
            await self.query("SELECT 1 FROM DUAL")
            return True
        except Exception:
            return False


# Global client instances
neo4j_client = Neo4jClient()
oracle_client = OracleClient()


async def initialize_clients() -> None:
    """Initialize all database clients."""
    await neo4j_client.connect()
    await oracle_client.connect()


async def shutdown_clients() -> None:
    """Shutdown all database clients."""
    await neo4j_client.disconnect()
    await oracle_client.disconnect()


async def health_check_all() -> Dict[str, str]:
    """Check health of all database connections."""
    health_status = {}
    
    try:
        neo4j_healthy = await neo4j_client.health_check()
        health_status["neo4j"] = "healthy" if neo4j_healthy else "unhealthy"
    except Exception:
        health_status["neo4j"] = "error"
    
    try:
        oracle_healthy = await oracle_client.health_check()
        health_status["oracle"] = "healthy" if oracle_healthy else "unhealthy"
    except Exception:
        health_status["oracle"] = "error"
    
    return health_status 
"""
Schema introspection functions to analyze Oracle database schema and store it in Neo4j.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from clients import neo4j_client, oracle_client
from schemas import SchemaNode, SchemaRelationship, SchemaGraph
from fuzzywuzzy import fuzz
import asyncio

logger = logging.getLogger(__name__)


class SchemaIntrospector:
    """Handles schema introspection and Neo4j storage."""
    
    def __init__(self):
        self.neo4j = neo4j_client
        self.oracle = oracle_client
    
    async def introspect_oracle_schema(self, schema_name: Optional[str] = None) -> SchemaGraph:
        """Introspect Oracle database schema and return structured representation."""
        logger.info(f"Starting schema introspection for schema: {schema_name or 'all'}")
        
        nodes = []
        relationships = []
        
        # Get database information
        db_node = SchemaNode(
            id="database",
            type="database",
            name="oracle_db",
            properties={"description": "Oracle Database"}
        )
        nodes.append(db_node)
        
        # Get tables
        tables = await self._get_tables(schema_name)
        table_nodes = []
        
        for table in tables:
            table_id = f"table_{table['TABLE_NAME']}"
            table_node = SchemaNode(
                id=table_id,
                type="table",
                name=table['TABLE_NAME'],
                properties={
                    "schema": table['OWNER'],
                    "table_type": table.get('TABLE_TYPE', 'TABLE'),
                    "comments": table.get('COMMENTS', ''),
                    "num_rows": table.get('NUM_ROWS', 0)
                }
            )
            nodes.append(table_node)
            table_nodes.append(table_node)
            
            # Add HAS_TABLE relationship
            relationships.append(SchemaRelationship(
                source_id="database",
                target_id=table_id,
                type="HAS_TABLE"
            ))
        
        # Get columns for each table
        for table_node in table_nodes:
            table_name = table_node.name
            columns = await self._get_columns(table_name, schema_name)
            
            for column in columns:
                column_id = f"column_{table_name}_{column['COLUMN_NAME']}"
                column_node = SchemaNode(
                    id=column_id,
                    type="column",
                    name=column['COLUMN_NAME'],
                    properties={
                        "table": table_name,
                        "data_type": column['DATA_TYPE'],
                        "data_length": column.get('DATA_LENGTH', 0),
                        "data_precision": column.get('DATA_PRECISION'),
                        "data_scale": column.get('DATA_SCALE'),
                        "nullable": column['NULLABLE'] == 'Y',
                        "default_value": column.get('DATA_DEFAULT'),
                        "comments": column.get('COMMENTS', ''),
                        "is_primary_key": False,  # Will be updated later
                        "is_foreign_key": False   # Will be updated later
                    }
                )
                nodes.append(column_node)
                
                # Add HAS_COLUMN relationship
                relationships.append(SchemaRelationship(
                    source_id=table_node.id,
                    target_id=column_id,
                    type="HAS_COLUMN"
                ))
        
        # Get primary keys
        primary_keys = await self._get_primary_keys(schema_name)
        for pk in primary_keys:
            column_id = f"column_{pk['TABLE_NAME']}_{pk['COLUMN_NAME']}"
            # Update the column node properties
            for node in nodes:
                if node.id == column_id:
                    node.properties["is_primary_key"] = True
                    break
        
        # Get foreign keys
        foreign_keys = await self._get_foreign_keys(schema_name)
        for fk in foreign_keys:
            source_column_id = f"column_{fk['TABLE_NAME']}_{fk['COLUMN_NAME']}"
            target_column_id = f"column_{fk['R_TABLE_NAME']}_{fk['R_COLUMN_NAME']}"
            
            # Mark columns as foreign keys
            for node in nodes:
                if node.id == source_column_id:
                    node.properties["is_foreign_key"] = True
                    break
            
            # Add foreign key relationship
            relationships.append(SchemaRelationship(
                source_id=source_column_id,
                target_id=target_column_id,
                type="HAS_FOREIGN_KEY",
                properties={
                    "constraint_name": fk['CONSTRAINT_NAME'],
                    "r_constraint_name": fk['R_CONSTRAINT_NAME']
                }
            ))
        
        logger.info(f"Schema introspection complete. Found {len(nodes)} nodes and {len(relationships)} relationships")
        return SchemaGraph(nodes=nodes, relationships=relationships)
    
    async def _get_tables(self, schema_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tables from Oracle database."""
        query = """
        SELECT 
            t.OWNER,
            t.TABLE_NAME,
            t.TABLESPACE_NAME,
            t.NUM_ROWS,
            tc.COMMENTS,
            'TABLE' as TABLE_TYPE
        FROM ALL_TABLES t
        LEFT JOIN ALL_TAB_COMMENTS tc ON t.OWNER = tc.OWNER AND t.TABLE_NAME = tc.TABLE_NAME
        WHERE t.OWNER NOT IN ('SYS', 'SYSTEM', 'CTXSYS', 'DBSNMP', 'OUTLN', 'WMSYS')
        """
        
        parameters = {}
        if schema_name:
            query += " AND t.OWNER = :schema_name"
            parameters["schema_name"] = schema_name.upper()
        
        query += " ORDER BY t.OWNER, t.TABLE_NAME"
        
        return await self.oracle.query(query, parameters)
    
    async def _get_columns(self, table_name: str, schema_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all columns for a specific table."""
        query = """
        SELECT 
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.DATA_LENGTH,
            c.DATA_PRECISION,
            c.DATA_SCALE,
            c.NULLABLE,
            c.DATA_DEFAULT,
            c.COLUMN_ID,
            cc.COMMENTS
        FROM ALL_TAB_COLUMNS c
        LEFT JOIN ALL_COL_COMMENTS cc ON c.OWNER = cc.OWNER 
            AND c.TABLE_NAME = cc.TABLE_NAME 
            AND c.COLUMN_NAME = cc.COLUMN_NAME
        WHERE c.TABLE_NAME = :table_name
        """
        
        parameters = {"table_name": table_name.upper()}
        if schema_name:
            query += " AND c.OWNER = :schema_name"
            parameters["schema_name"] = schema_name.upper()
        
        query += " ORDER BY c.COLUMN_ID"
        
        return await self.oracle.query(query, parameters)
    
    async def _get_primary_keys(self, schema_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all primary key constraints."""
        query = """
        SELECT 
            c.CONSTRAINT_NAME,
            c.TABLE_NAME,
            cc.COLUMN_NAME,
            cc.POSITION
        FROM ALL_CONSTRAINTS c
        JOIN ALL_CONS_COLUMNS cc ON c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME 
            AND c.OWNER = cc.OWNER
        WHERE c.CONSTRAINT_TYPE = 'P'
        """
        
        parameters = {}
        if schema_name:
            query += " AND c.OWNER = :schema_name"
            parameters["schema_name"] = schema_name.upper()
        
        query += " ORDER BY c.TABLE_NAME, cc.POSITION"
        
        return await self.oracle.query(query, parameters)
    
    async def _get_foreign_keys(self, schema_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all foreign key constraints."""
        query = """
        SELECT 
            c.CONSTRAINT_NAME,
            c.TABLE_NAME,
            cc.COLUMN_NAME,
            c.R_CONSTRAINT_NAME,
            rc.TABLE_NAME as R_TABLE_NAME,
            rcc.COLUMN_NAME as R_COLUMN_NAME
        FROM ALL_CONSTRAINTS c
        JOIN ALL_CONS_COLUMNS cc ON c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME 
            AND c.OWNER = cc.OWNER
        JOIN ALL_CONSTRAINTS rc ON c.R_CONSTRAINT_NAME = rc.CONSTRAINT_NAME
        JOIN ALL_CONS_COLUMNS rcc ON rc.CONSTRAINT_NAME = rcc.CONSTRAINT_NAME 
            AND rc.OWNER = rcc.OWNER
        WHERE c.CONSTRAINT_TYPE = 'R'
        """
        
        parameters = {}
        if schema_name:
            query += " AND c.OWNER = :schema_name"
            parameters["schema_name"] = schema_name.upper()
        
        query += " ORDER BY c.TABLE_NAME, cc.COLUMN_NAME"
        
        return await self.oracle.query(query, parameters)
    
    async def store_schema_in_neo4j(self, schema: SchemaGraph) -> None:
        """Store the schema graph in Neo4j."""
        logger.info("Storing schema in Neo4j")
        
        # Clear existing schema
        await self.neo4j.query("MATCH (n) DETACH DELETE n")
        
        # Create nodes
        for node in schema.nodes:
            query = """
            CREATE (n:SchemaNode {
                id: $id,
                type: $type,
                name: $name,
                properties: $properties
            })
            """
            await self.neo4j.query(query, {
                "id": node.id,
                "type": node.type,
                "name": node.name,
                "properties": node.properties
            })
        
        # Create relationships
        for rel in schema.relationships:
            query = """
            MATCH (source {id: $source_id})
            MATCH (target {id: $target_id})
            CREATE (source)-[r:RELATIONSHIP {
                type: $type,
                properties: $properties
            }]->(target)
            """
            await self.neo4j.query(query, {
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "type": rel.type,
                "properties": rel.properties
            })
        
        logger.info(f"Schema stored in Neo4j: {len(schema.nodes)} nodes, {len(schema.relationships)} relationships")
    
    async def find_relevant_schema(self, query_text: str, similarity_threshold: float = 0.6) -> List[Dict[str, Any]]:
        """Find relevant tables and columns based on query text using fuzzy matching."""
        logger.info(f"Finding relevant schema for query: {query_text}")
        
        # Get all tables and columns from Neo4j
        cypher_query = """
        MATCH (db:SchemaNode {type: 'database'})-[:RELATIONSHIP {type: 'HAS_TABLE'}]->(table:SchemaNode {type: 'table'})
        MATCH (table)-[:RELATIONSHIP {type: 'HAS_COLUMN'}]->(column:SchemaNode {type: 'column'})
        RETURN table.name as table_name, 
               collect({name: column.name, properties: column.properties}) as columns
        """
        
        schema_data = await self.neo4j.query(cypher_query)
        
        relevant_tables = []
        query_words = query_text.lower().split()
        
        for table_data in schema_data:
            table_name = table_data['table_name']
            columns = table_data['columns']
            
            # Check table name similarity
            max_table_score = 0
            for word in query_words:
                score = fuzz.ratio(word.lower(), table_name.lower()) / 100.0
                max_table_score = max(max_table_score, score)
            
            # Check column name similarity
            relevant_columns = []
            for column in columns:
                column_name = column['name']
                max_column_score = 0
                
                for word in query_words:
                    score = fuzz.ratio(word.lower(), column_name.lower()) / 100.0
                    max_column_score = max(max_column_score, score)
                
                if max_column_score >= similarity_threshold:
                    relevant_columns.append({
                        "name": column_name,
                        "score": max_column_score,
                        "properties": column['properties']
                    })
            
            # Include table if it has relevant columns or name matches
            if max_table_score >= similarity_threshold or relevant_columns:
                relevant_tables.append({
                    "table_name": table_name,
                    "table_score": max_table_score,
                    "columns": relevant_columns
                })
        
        # Sort by relevance
        relevant_tables.sort(key=lambda x: x['table_score'], reverse=True)
        
        logger.info(f"Found {len(relevant_tables)} relevant tables")
        return relevant_tables
    
    async def get_schema_context(self, table_names: List[str]) -> Dict[str, Any]:
        """Get complete schema context for specified tables including relationships."""
        logger.info(f"Getting schema context for tables: {table_names}")
        
        # Get tables, columns, and relationships
        cypher_query = """
        MATCH (table:SchemaNode {type: 'table'})
        WHERE table.name IN $table_names
        MATCH (table)-[:RELATIONSHIP {type: 'HAS_COLUMN'}]->(column:SchemaNode {type: 'column'})
        OPTIONAL MATCH (column)-[fk:RELATIONSHIP {type: 'HAS_FOREIGN_KEY'}]->(ref_column:SchemaNode {type: 'column'})
        OPTIONAL MATCH (ref_column)<-[:RELATIONSHIP {type: 'HAS_COLUMN'}]-(ref_table:SchemaNode {type: 'table'})
        RETURN table.name as table_name,
               collect(DISTINCT {
                   name: column.name,
                   properties: column.properties,
                   foreign_keys: collect(DISTINCT {
                       ref_table: ref_table.name,
                       ref_column: ref_column.name,
                       constraint: fk.properties
                   })
               }) as columns
        """
        
        result = await self.neo4j.query(cypher_query, {"table_names": table_names})
        
        schema_context = {
            "tables": result,
            "relationships": []
        }
        
        # Get inter-table relationships
        for table_data in result:
            for column in table_data['columns']:
                for fk in column['foreign_keys']:
                    if fk['ref_table'] and fk['ref_table'] in table_names:
                        schema_context["relationships"].append({
                            "from_table": table_data['table_name'],
                            "from_column": column['name'],
                            "to_table": fk['ref_table'],
                            "to_column": fk['ref_column']
                        })
        
        logger.info(f"Schema context retrieved for {len(result)} tables")
        return schema_context


# Global instance
schema_introspector = SchemaIntrospector() 
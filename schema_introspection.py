"""
Schema introspection functions to analyze Oracle database schema and store it in Neo4j.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from clients import neo4j_client, oracle_client
from schemas import SchemaNode, SchemaRelationship, SchemaGraph
from fuzzywuzzy import fuzz
from config import settings
import asyncio

logger = logging.getLogger(__name__)


class SchemaIntrospector:
    """Handles schema introspection and Neo4j storage."""
    
    def __init__(self):
        self.neo4j = neo4j_client
        self.oracle = oracle_client
    
    async def introspect_oracle_schema(
        self, 
        schema_name: Optional[str] = None, 
        database_name: Optional[str] = None
    ) -> SchemaGraph:
        """Introspect Oracle database schema and return structured representation."""
        # Use provided database name or default
        if database_name is None:
            database_name = settings.default_database_name
        
        logger.info(f"Starting schema introspection for database: {database_name}, schema: {schema_name or 'all'}")
        
        nodes = []
        relationships = []
        
        # Get database information with parameterized name
        database_id = f"database_{database_name}"
        db_node = SchemaNode(
            id=database_id,
            type="database",
            name=database_name,
            properties={
                "description": f"Oracle Database: {database_name}",
                "database_type": "Oracle",
                "schema_filter": schema_name or "all_schemas",
                "introspection_timestamp": None  # Will be set during storage
            }
        )
        nodes.append(db_node)
        
        # Get tables
        tables = await self._get_tables(schema_name)
        table_nodes = []
        
        for table in tables:
            table_id = f"{database_name}_table_{table['TABLE_NAME']}"
            table_node = SchemaNode(
                id=table_id,
                type="table",
                name=table['TABLE_NAME'],
                properties={
                    "database": database_name,
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
                source_id=database_id,
                target_id=table_id,
                type="HAS_TABLE"
            ))
        
        # Get columns for each table
        for table_node in table_nodes:
            table_name = table_node.name
            columns = await self._get_columns(table_name, schema_name)
            
            for column in columns:
                column_id = f"{database_name}_column_{table_name}_{column['COLUMN_NAME']}"
                column_node = SchemaNode(
                    id=column_id,
                    type="column",
                    name=column['COLUMN_NAME'],
                    properties={
                        "database": database_name,
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
            column_id = f"{database_name}_column_{pk['TABLE_NAME']}_{pk['COLUMN_NAME']}"
            # Update the column node properties
            for node in nodes:
                if node.id == column_id:
                    node.properties["is_primary_key"] = True
                    break
        
        # Get foreign keys
        foreign_keys = await self._get_foreign_keys(schema_name)
        for fk in foreign_keys:
            source_column_id = f"{database_name}_column_{fk['TABLE_NAME']}_{fk['COLUMN_NAME']}"
            target_column_id = f"{database_name}_column_{fk['R_TABLE_NAME']}_{fk['R_COLUMN_NAME']}"
            
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
                    "r_constraint_name": fk['R_CONSTRAINT_NAME'],
                    "inferred": False
                }
            ))
        
        # Infer additional foreign key relationships from naming conventions (if enabled)
        inferred_relationships = []
        if settings.enable_fk_inference:
            inferred_relationships = await self._infer_foreign_keys_from_naming(nodes, relationships)
            
            # Add inferred relationships and update column properties
            for rel in inferred_relationships:
                relationships.append(rel)
                # Mark source column as foreign key
                for node in nodes:
                    if node.id == rel.source_id:
                        node.properties["is_foreign_key"] = True
                        break
        
        logger.info(f"Schema introspection complete. Found {len(nodes)} nodes and {len(relationships)} relationships")
        if settings.enable_fk_inference:
            logger.info(f"Inferred {len(inferred_relationships)} additional foreign key relationships from naming conventions")
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
    
    async def _infer_foreign_keys_from_naming(self, nodes: List[SchemaNode], existing_relationships: List[SchemaRelationship]) -> List[SchemaRelationship]:
        """Infer foreign key relationships from column naming conventions."""
        logger.info("Inferring foreign key relationships from naming conventions")
        
        # Extract table names and column information
        table_names = []
        column_info = {}  # {table_name: [column_nodes]}
        
        for node in nodes:
            if node.type == "table":
                table_names.append(node.name)
                column_info[node.name] = []
            elif node.type == "column":
                table_name = node.properties.get("table")
                if table_name not in column_info:
                    column_info[table_name] = []
                column_info[table_name].append(node)
        
        # Get existing foreign key relationships to avoid duplicates
        existing_fk_pairs = set()
        for rel in existing_relationships:
            if rel.type == "HAS_FOREIGN_KEY":
                existing_fk_pairs.add((rel.source_id, rel.target_id))
        
        inferred_relationships = []
        
        # Common foreign key naming patterns
        fk_patterns = [
            "{table}_ID",
            "ID_{table}",
            "{table}_KEY",
            "{table}_FK",
            "{table}ID",  # No underscore
            "ID{table}"   # No underscore
        ]
        
        # For each table's columns
        for table_name, columns in column_info.items():
            for column in columns:
                column_name = column.name  # Keep original case
                
                # Check each naming pattern
                for pattern in fk_patterns:
                    # Check if column matches any pattern (case-insensitive)
                    if self._matches_fk_pattern(column_name, pattern):
                        # Extract the potential table reference from column name
                        potential_table_refs = self._extract_table_references(column_name, pattern)
                        
                                                 # Find matching tables using fuzzy matching
                         for ref in potential_table_refs:
                             matched_table = self._find_matching_table(ref, table_names, settings.fk_inference_similarity_threshold)
                             if matched_table and matched_table != table_name:
                                # Find the primary key column of the matched table
                                pk_column = self._find_primary_key_column(matched_table, column_info)
                                if pk_column:
                                    source_id = column.id
                                    target_id = pk_column.id
                                    
                                    # Check if this relationship already exists
                                    if (source_id, target_id) not in existing_fk_pairs:
                                        inferred_relationships.append(SchemaRelationship(
                                            source_id=source_id,
                                            target_id=target_id,
                                            type="HAS_FOREIGN_KEY",
                                            properties={
                                                "constraint_name": f"INFERRED_{table_name}_{column_name}",
                                                "inferred": True,
                                                "inference_method": "naming_convention",
                                                "pattern_used": pattern,
                                                "confidence": self._calculate_confidence(ref, matched_table)
                                            }
                                        ))
                                        existing_fk_pairs.add((source_id, target_id))
                                        logger.debug(f"Inferred FK: {table_name}.{column_name} -> {matched_table}.{pk_column.name}")
        
        logger.info(f"Inferred {len(inferred_relationships)} foreign key relationships from naming conventions")
        return inferred_relationships
    
    def _matches_fk_pattern(self, column_name: str, pattern: str) -> bool:
        """Check if a column name matches a foreign key pattern (case-insensitive)."""
        if "{table}" not in pattern:
            return False
        
        # Convert to uppercase for case-insensitive comparison
        column_upper = column_name.upper()
        pattern_upper = pattern.upper()
        
        # Convert pattern to regex-like check
        if pattern_upper.startswith("{TABLE}"):
            suffix = pattern_upper.replace("{TABLE}", "")
            return column_upper.endswith(suffix) and len(column_upper) > len(suffix)
        elif pattern_upper.endswith("{TABLE}"):
            prefix = pattern_upper.replace("{TABLE}", "")
            return column_upper.startswith(prefix) and len(column_upper) > len(prefix)
        else:
            # Pattern has {table} in middle
            parts = pattern_upper.split("{TABLE}")
            if len(parts) == 2:
                prefix, suffix = parts
                return column_upper.startswith(prefix) and column_upper.endswith(suffix) and len(column_upper) > len(prefix) + len(suffix)
        
        return False
    
    def _extract_table_references(self, column_name: str, pattern: str) -> List[str]:
        """Extract potential table references from a column name using the pattern (case-insensitive)."""
        references = []
        
        # Work with uppercase for pattern matching but preserve original case where possible
        column_upper = column_name.upper()
        pattern_upper = pattern.upper()
        
        if pattern_upper.startswith("{TABLE}"):
            suffix = pattern_upper.replace("{TABLE}", "")
            if column_upper.endswith(suffix):
                # Extract the reference part, preserving original case
                ref_length = len(column_name) - len(suffix)
                ref = column_name[:ref_length] if suffix else column_name
                references.append(ref)
        elif pattern_upper.endswith("{TABLE}"):
            prefix = pattern_upper.replace("{TABLE}", "")
            if column_upper.startswith(prefix):
                # Extract the reference part, preserving original case
                ref = column_name[len(prefix):] if prefix else column_name
                references.append(ref)
        else:
            # Pattern has {table} in middle
            parts = pattern_upper.split("{TABLE}")
            if len(parts) == 2:
                prefix, suffix = parts
                if column_upper.startswith(prefix) and column_upper.endswith(suffix):
                    # Extract the reference part, preserving original case
                    start_idx = len(prefix)
                    end_idx = len(column_name) - len(suffix) if suffix else len(column_name)
                    ref = column_name[start_idx:end_idx]
                    references.append(ref)
        
        return [ref for ref in references if ref]  # Remove empty strings
    
    def _find_matching_table(self, reference: str, table_names: List[str], min_similarity: float = 0.7) -> Optional[str]:
        """Find the best matching table name using fuzzy matching (case-insensitive)."""
        best_match = None
        best_score = 0
        
        for table_name in table_names:
            # Direct match (case-insensitive)
            if reference.upper() == table_name.upper():
                return table_name
            
            # Fuzzy match (case-insensitive)
            score = fuzz.ratio(reference.upper(), table_name.upper()) / 100.0
            if score > best_score and score >= min_similarity:
                best_score = score
                best_match = table_name
            
            # Check if reference is a substring of table name (for abbreviations)
            if reference.upper() in table_name.upper() and len(reference) >= 3:
                substring_score = len(reference) / len(table_name)
                if substring_score > 0.3:  # At least 30% of table name
                    adjusted_score = score * 1.2  # Boost score for substring matches
                    if adjusted_score > best_score and adjusted_score >= min_similarity:
                        best_score = adjusted_score
                        best_match = table_name
        
        return best_match
    
    def _find_primary_key_column(self, table_name: str, column_info: Dict[str, List[SchemaNode]]) -> Optional[SchemaNode]:
        """Find the primary key column for a table (case-insensitive matching)."""
        if table_name not in column_info:
            return None
        
        # First, look for explicitly marked primary key columns
        for column in column_info[table_name]:
            if column.properties.get("is_primary_key"):
                return column
        
        # If no explicit PK, look for common PK naming patterns (case-insensitive)
        pk_patterns = ["ID", f"{table_name}_ID", f"ID_{table_name}", f"{table_name}ID"]
        
        for pattern in pk_patterns:
            for column in column_info[table_name]:
                if column.name.upper() == pattern.upper():
                    return column
        
        # If still no match, return the first column (as a fallback)
        if column_info[table_name]:
            return column_info[table_name][0]
        
        return None
    
    def _calculate_confidence(self, reference: str, matched_table: str) -> float:
        """Calculate confidence score for the inferred relationship (case-insensitive)."""
        # Base confidence on fuzzy match score (case-insensitive)
        confidence = fuzz.ratio(reference.upper(), matched_table.upper()) / 100.0
        
        # Boost confidence for exact matches (case-insensitive)
        if reference.upper() == matched_table.upper():
            confidence = 1.0
        
        # Boost confidence for substring matches (abbreviations)
        elif reference.upper() in matched_table.upper():
            confidence = min(confidence * 1.1, 1.0)
        
        return round(confidence, 2)
    
    async def store_schema_in_neo4j(self, schema: SchemaGraph, database_name: Optional[str] = None) -> None:
        """Store the schema graph in Neo4j."""
        if database_name is None:
            database_name = settings.default_database_name
            
        logger.info(f"Storing schema for database '{database_name}' in Neo4j")
        
        try:
            # Clear existing schema for this specific database if multiple databases are not supported
            if not settings.support_multiple_databases:
                logger.info("Clearing all existing schema data (single database mode)")
                await self.neo4j.query("MATCH (n) DETACH DELETE n")
            else:
                # Clear only this database's schema in multi-database mode
                logger.info(f"Clearing existing schema for database '{database_name}' (multi-database mode)")
                await self.neo4j.query(
                    "MATCH (n) WHERE n.database = $database_name OR n.id STARTS WITH $db_prefix DETACH DELETE n",
                    {"database_name": database_name, "db_prefix": f"database_{database_name}"}
                )
            
            # Add timestamp to database node
            import datetime
            for node in schema.nodes:
                if node.type == "database":
                    node.properties["introspection_timestamp"] = datetime.datetime.utcnow().isoformat()
        
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
            
            # Check table name similarity (case-insensitive)
            max_table_score = 0
            for word in query_words:
                score = fuzz.ratio(word.lower(), table_name.lower()) / 100.0
                max_table_score = max(max_table_score, score)
            
            # Check column name similarity (case-insensitive)
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
    
    async def get_inferred_relationships(self) -> List[Dict[str, Any]]:
        """Get all inferred foreign key relationships from Neo4j."""
        cypher_query = """
        MATCH (source:SchemaNode)-[r:RELATIONSHIP {type: 'HAS_FOREIGN_KEY'}]->(target:SchemaNode)
        WHERE r.properties.inferred = true
        MATCH (source_table:SchemaNode)-[:RELATIONSHIP {type: 'HAS_COLUMN'}]->(source)
        MATCH (target_table:SchemaNode)-[:RELATIONSHIP {type: 'HAS_COLUMN'}]->(target)
        RETURN {
            source_table: source_table.name,
            source_column: source.name,
            target_table: target_table.name,
            target_column: target.name,
            confidence: r.properties.confidence,
            pattern_used: r.properties.pattern_used,
            constraint_name: r.properties.constraint_name
        } as relationship
        ORDER BY relationship.confidence DESC
        """
        
        results = await self.neo4j.query(cypher_query)
        return [result['relationship'] for result in results]
    
    async def validate_inferred_relationships(self) -> Dict[str, Any]:
        """Validate and provide statistics on inferred relationships."""
        inferred_rels = await self.get_inferred_relationships()
        
        stats = {
            "total_inferred": len(inferred_rels),
            "high_confidence": len([r for r in inferred_rels if r['confidence'] >= 0.9]),
            "medium_confidence": len([r for r in inferred_rels if 0.7 <= r['confidence'] < 0.9]),
            "low_confidence": len([r for r in inferred_rels if r['confidence'] < 0.7]),
            "by_pattern": {}
        }
        
        # Count by pattern
        for rel in inferred_rels:
            pattern = rel['pattern_used']
            if pattern not in stats["by_pattern"]:
                stats["by_pattern"][pattern] = 0
            stats["by_pattern"][pattern] += 1
        
        return {
            "statistics": stats,
            "relationships": inferred_rels
        }


# Global instance
schema_introspector = SchemaIntrospector() 
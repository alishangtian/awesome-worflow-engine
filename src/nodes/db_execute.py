"""数据库执行节点"""

from typing import Dict, Any
import aiomysql
from .base import BaseNode

class DbExecuteNode(BaseNode):
    """数据库执行节点（MySQL）- 用于INSERT/UPDATE/DELETE等操作"""
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        host = str(params["host"])
        port = int(params.get("port", 3306))
        user = str(params["user"])
        password = str(params["password"])
        database = str(params["database"])
        statement = str(params["statement"])
        parameters = params.get("parameters", ())
        auto_commit = bool(params.get("auto_commit", True))
        
        try:
            pool = await aiomysql.create_pool(
                host=host,
                port=port,
                user=user,
                password=password,
                db=database,
                autocommit=auto_commit
            )
            
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(statement, parameters)
                    
                    if not auto_commit:
                        await conn.commit()
                        
                    return {
                        "result": "success",
                        "rows_affected": cursor.rowcount,
                        "last_row_id": cursor.lastrowid,
                        "statement": statement
                    }
                    
        except Exception as e:
            if not auto_commit and 'conn' in locals():
                await conn.rollback()
            raise ValueError(f"数据库执行失败: {str(e)}")
        finally:
            pool.close()
            await pool.wait_closed()

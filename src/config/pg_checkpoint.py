"""
Centralised Postgres checkpointer initialisation for every graph.

Usage (inside agent core.py):
    from src.config.pg_checkpoint import checkpointer
    ...
    compiled = builder.compile(checkpointer=checkpointer)
"""

from __future__ import annotations

import os, logging, psycopg, atexit
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global pool reference for cleanup
_pool = None

def _cleanup_pool():
    """Cleanup function to properly close the pool on exit."""
    global _pool
    if _pool:
        try:
            _pool.close()
        except Exception:
            pass

# Register cleanup function
atexit.register(_cleanup_pool)

def _get_database_url() -> str:
    """Get database URL from environment variables."""
    return os.getenv("DATABASE_URL")

# ── 1️⃣  Environment & logging ────────────────────────────────────────────────
DATABASE_URL = _get_database_url()
if not DATABASE_URL:
    logging.critical("DATABASE_URL environment variable not set → persistence disabled")
    checkpointer: PostgresSaver | None = None
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("ecla_agent")

    # ── 2️⃣  Connection-pool with improved error handling ─────────────────────
    try:
        # Parse connection string and add connection stability settings
        conn_params = {
            "connect_timeout": 5,  # Shorter timeout to fail faster
            "row_factory": dict_row,
            "prepare_threshold": None,  # Disables server-side PREPARE
            "keepalives_idle": 30,  # TCP keepalive settings
            "keepalives_interval": 10,
            "keepalives_count": 3,
        }

        # Add SSL settings for remote connections
        if "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
            # Require SSL for hosted databases (e.g., Supabase)
            conn_params["sslmode"] = "require"

        def _make_pool() -> ConnectionPool:
            return ConnectionPool(
                conninfo=DATABASE_URL,
                max_size=8,   # Reduced pool size for better connection management
                min_size=1,   # Maintain minimum connections
                max_idle=180, # Close idle connections after 3 minutes
                max_lifetime=1800,  # Recycle connections after 30 minutes
                kwargs=conn_params,
            )

        _pool = _make_pool()
        
        # Test the connection pool
        with _pool.connection(timeout=10) as test_conn:
            test_conn.execute("SELECT 1")
            
        logger.info("Postgres connection pool ready with improved error handling")

        # ── 3️⃣  PostgresSaver initialisation (with resiliency wrapper) ───────
        class ResilientPostgresSaver:
            """Thin wrapper around PostgresSaver that resets the pool and retries on OperationalError."""
            def __init__(self, pool_factory, pool):
                self._pool_factory = pool_factory
                self._pool = pool
                self._saver = PostgresSaver(pool)

            def _reset_pool(self):
                try:
                    self._pool.close()
                except Exception:
                    pass
                self._pool = self._pool_factory()
                self._saver = PostgresSaver(self._pool)
                logger.info("PostgresSaver pool reset after OperationalError")

            def put(self, *args, **kwargs):
                for attempt in (1, 2):
                    try:
                        return self._saver.put(*args, **kwargs)
                    except (psycopg.OperationalError,) as e:
                        logger.warning(f"Checkpoint put failed (attempt {attempt}/2): {e}")
                        self._reset_pool()
                # Final attempt will raise if it fails again
                return self._saver.put(*args, **kwargs)

            def get(self, *args, **kwargs):
                for attempt in (1, 2):
                    try:
                        return self._saver.get(*args, **kwargs)
                    except (psycopg.OperationalError,) as e:
                        logger.warning(f"Checkpoint get failed (attempt {attempt}/2): {e}")
                        self._reset_pool()
                return self._saver.get(*args, **kwargs)

            # Delegate any other attributes/methods to the underlying saver
            def __getattr__(self, name):
                return getattr(self._saver, name)

        checkpointer = ResilientPostgresSaver(_make_pool, _pool)
        logger.info("PostgresSaver attached to pool (resilient)")

        # ── 4️⃣  Create checkpoints table (idempotent) ───────────────────────
        try:
            # Use autocommit mode for setup to allow CREATE INDEX CONCURRENTLY
            setup_conn_params = conn_params.copy()
            setup_conn_params["autocommit"] = True  # Enable autocommit for setup
            
            setup_conn = psycopg.connect(DATABASE_URL, **setup_conn_params)
            setup_checkpointer = PostgresSaver(setup_conn)
            setup_checkpointer.setup()
            setup_conn.close()
            
            logger.info("Checkpoint table verified / created with autocommit mode")
        except psycopg.errors.DuplicateColumn as dup_col_err:
            # Handle case where schema is already up-to-date (e.g., task_path column already exists)
            if "task_path" in str(dup_col_err):
                logger.info("Checkpoint schema already up-to-date (task_path column exists)")
            else:
                logger.warning(f"Duplicate column error (non-task_path): {dup_col_err}")
                # Still continue since the checkpointer should work
        except (psycopg.OperationalError, TimeoutError) as db_err:
            logger.error("DB setup failed: %s", db_err, exc_info=True)
            # Try to recreate the pool once
            try:
                _pool.close()
                _pool = ConnectionPool(
                    conninfo=DATABASE_URL,
                    max_size=4,  # Even smaller pool for retry
                    min_size=1,
                    kwargs=conn_params,
                )
                checkpointer = PostgresSaver(_pool)
                
                # Retry setup with autocommit
                retry_conn_params = conn_params.copy()
                retry_conn_params["autocommit"] = True
                retry_conn = psycopg.connect(DATABASE_URL, **retry_conn_params)
                retry_checkpointer = PostgresSaver(retry_conn)
                
                try:
                    retry_checkpointer.setup()
                    logger.info("Checkpoint table setup successful on retry with autocommit")
                except psycopg.errors.DuplicateColumn as retry_dup_col_err:
                    if "task_path" in str(retry_dup_col_err):
                        logger.info("Checkpoint schema already up-to-date on retry (task_path column exists)")
                    else:
                        logger.warning(f"Duplicate column error on retry: {retry_dup_col_err}")
                
                retry_conn.close()
                
            except Exception:
                logger.error("Retry failed, disabling checkpointer")
                checkpointer = None
    except Exception as pool_err:
        logging.critical("Failed to create Postgres pool: %s", pool_err, exc_info=True)
        checkpointer = None

print(f"✅ pg_checkpoint loaded – persistence: {'ON' if checkpointer else 'OFF'}") 